from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ai_investment_analyst.db.connection import get_connection


@dataclass(frozen=True)
class PricePoint:
    trading_date: str
    close_price: Decimal | None
    source_code: str | None


@dataclass(frozen=True)
class RevenuePoint:
    revenue_period: str
    revenue: Decimal | None
    revenue_month_change_percent: Decimal | None
    revenue_year_change_percent: Decimal | None


@dataclass(frozen=True)
class StockReportContext:
    ticker: str
    latest: PricePoint | None
    recent_prices: list[PricePoint]
    latest_revenue: RevenuePoint | None


def load_stock_report_context(ticker: str, limit: int = 10) -> StockReportContext:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.ticker, pdc.trading_date, pdc.close_price, ds.code AS source_code
            FROM price_daily_canonical pdc
            JOIN symbols s ON s.id = pdc.symbol_id
            JOIN data_sources ds ON ds.id = pdc.data_source_id
            WHERE s.ticker = %s
            ORDER BY pdc.trading_date DESC
            LIMIT %s
            """,
            (ticker, limit),
        )
        price_rows = cur.fetchall()

        cur.execute(
            """
            SELECT mr.revenue_period, mr.revenue, mr.revenue_month_change_percent, mr.revenue_year_change_percent
            FROM monthly_revenues mr
            JOIN symbols s ON s.id = mr.symbol_id
            WHERE s.ticker = %s
            ORDER BY mr.revenue_period DESC
            LIMIT 1
            """,
            (ticker,),
        )
        revenue_row = cur.fetchone()

    points = [
        PricePoint(
            trading_date=row[1].isoformat(),
            close_price=row[2],
            source_code=row[3],
        )
        for row in price_rows
    ]
    latest = points[0] if points else None
    latest_revenue = None
    if revenue_row:
        latest_revenue = RevenuePoint(
            revenue_period=revenue_row[0].isoformat(),
            revenue=revenue_row[1],
            revenue_month_change_percent=revenue_row[2],
            revenue_year_change_percent=revenue_row[3],
        )
    return StockReportContext(ticker=ticker, latest=latest, recent_prices=points, latest_revenue=latest_revenue)


def _pct_change(new: Decimal | None, old: Decimal | None) -> str:
    if new is None or old in (None, Decimal("0")):
        return "N/A"
    change = ((new - old) / old) * Decimal("100")
    return f"{change:.2f}%"


def _fmt_decimal(value: Decimal | None) -> str:
    return "N/A" if value is None else f"{value}"


def generate_stock_report(ticker: str) -> str:
    context = load_stock_report_context(ticker)
    if not context.latest:
        return f"找不到 {ticker} 的 canonical 價格資料。"

    latest = context.latest
    previous_5 = context.recent_prices[4] if len(context.recent_prices) >= 5 else None
    previous_10 = context.recent_prices[9] if len(context.recent_prices) >= 10 else None

    report_lines = [
        f"個股分析報告：{ticker}",
        f"- 最新收盤：{latest.close_price}（{latest.trading_date}）",
        f"- 採用來源：{latest.source_code}",
        f"- 近 5 筆變化：{_pct_change(latest.close_price, previous_5.close_price if previous_5 else None)}",
        f"- 近 10 筆變化：{_pct_change(latest.close_price, previous_10.close_price if previous_10 else None)}",
    ]

    if len(context.recent_prices) >= 3:
        closes = [p.close_price for p in context.recent_prices[:3] if p.close_price is not None]
        if len(closes) == 3:
            if closes[0] >= closes[1] >= closes[2]:
                trend = "短線偏強"
            elif closes[0] <= closes[1] <= closes[2]:
                trend = "短線偏弱"
            else:
                trend = "短線震盪"
            report_lines.append(f"- 近三日趨勢：{trend}")

    if context.latest_revenue:
        revenue = context.latest_revenue
        report_lines.extend(
            [
                f"- 最新月營收期間：{revenue.revenue_period}",
                f"- 最新月營收：{_fmt_decimal(revenue.revenue)}",
                f"- 月增率：{_fmt_decimal(revenue.revenue_month_change_percent)}%",
                f"- 年增率：{_fmt_decimal(revenue.revenue_year_change_percent)}%",
            ]
        )

    report_lines.extend(
        [
            "- 分析說明：",
            "  目前這是第一版報告，主要根據 canonical 價格資料與最新月營收生成。",
            "  後續可再加入財報、新聞與法人資料，讓報告更完整。",
        ]
    )
    return "\n".join(report_lines)
