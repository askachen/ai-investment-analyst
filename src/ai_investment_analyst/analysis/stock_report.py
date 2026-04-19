from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

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
            SELECT mr.revenue_period, mr.revenue
            FROM monthly_revenues mr
            JOIN symbols s ON s.id = mr.symbol_id
            WHERE s.ticker = %s
            ORDER BY mr.revenue_period DESC
            LIMIT 13
            """,
            (ticker,),
        )
        revenue_rows = cur.fetchall()

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
    if revenue_rows:
        latest_period = revenue_rows[0][0].isoformat()
        latest_value = revenue_rows[0][1]
        previous_month_value = revenue_rows[1][1] if len(revenue_rows) >= 2 else None
        previous_year_value = revenue_rows[12][1] if len(revenue_rows) >= 13 else None

        revenue_month_change_percent = None
        revenue_year_change_percent = None
        if latest_value is not None and previous_month_value not in (None, Decimal("0")):
            revenue_month_change_percent = ((latest_value - previous_month_value) / previous_month_value) * Decimal("100")
        if latest_value is not None and previous_year_value not in (None, Decimal("0")):
            revenue_year_change_percent = ((latest_value - previous_year_value) / previous_year_value) * Decimal("100")

        latest_revenue = RevenuePoint(
            revenue_period=latest_period,
            revenue=latest_value,
            revenue_month_change_percent=revenue_month_change_percent,
            revenue_year_change_percent=revenue_year_change_percent,
        )

    return StockReportContext(ticker=ticker, latest=latest, recent_prices=points, latest_revenue=latest_revenue)


def _quantize_2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _pct_change(new: Decimal | None, old: Decimal | None) -> str:
    if new is None or old in (None, Decimal("0")):
        return "N/A"
    change = ((new - old) / old) * Decimal("100")
    return f"{_quantize_2(change)}%"


def _fmt_price(value: Decimal | None) -> str:
    return "N/A" if value is None else f"{_quantize_2(value)}"


def _fmt_percent(value: Decimal | None) -> str:
    return "N/A" if value is None else f"{_quantize_2(value)}%"


def _fmt_revenue_in_100m(value: Decimal | None) -> str:
    if value is None:
        return "N/A"
    amount = value / Decimal("100000000")
    return f"{_quantize_2(amount)} 億元"


def _revenue_trend_text(revenue: RevenuePoint | None) -> str:
    if not revenue:
        return "尚無月營收資料。"
    mom = revenue.revenue_month_change_percent
    yoy = revenue.revenue_year_change_percent
    if mom is None and yoy is None:
        return "月營收資料已取得，但目前還無法完整估算月增與年增。"
    if (mom is not None and mom > 0) and (yoy is not None and yoy > 0):
        return "最新月營收同時呈現月增與年增，顯示基本面動能偏正向。"
    if (mom is not None and mom < 0) and (yoy is not None and yoy < 0):
        return "最新月營收同時呈現月減與年減，基本面動能轉弱需特別留意。"
    return "最新月營收的月增與年增方向不一致，建議搭配更多基本面資料一起判讀。"


def generate_stock_report(ticker: str) -> str:
    context = load_stock_report_context(ticker)
    if not context.latest:
        return f"找不到 {ticker} 的 canonical 價格資料。"

    latest = context.latest
    previous_5 = context.recent_prices[4] if len(context.recent_prices) >= 5 else None
    previous_10 = context.recent_prices[9] if len(context.recent_prices) >= 10 else None

    report_lines = [
        f"【個股分析報告】{ticker}",
        "",
        "一、價格概況",
        f"- 最新收盤價：{_fmt_price(latest.close_price)}（{latest.trading_date}）",
        f"- 採用資料來源：{latest.source_code}",
        f"- 近 5 筆價格變化：{_pct_change(latest.close_price, previous_5.close_price if previous_5 else None)}",
        f"- 近 10 筆價格變化：{_pct_change(latest.close_price, previous_10.close_price if previous_10 else None)}",
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
                "",
                "二、月營收觀察",
                f"- 最新月營收期間：{revenue.revenue_period}",
                f"- 最新月營收：{_fmt_revenue_in_100m(revenue.revenue)}",
                f"- 月增率（MoM）：{_fmt_percent(revenue.revenue_month_change_percent)}",
                f"- 年增率（YoY）：{_fmt_percent(revenue.revenue_year_change_percent)}",
                f"- 營收趨勢判讀：{_revenue_trend_text(revenue)}",
            ]
        )

    report_lines.extend(
        [
            "",
            "三、結論",
            "- 目前這是第一版個股分析報告，主要依據 canonical 價格資料與最新月營收生成。",
            "- 若再加入財報、新聞與法人籌碼，報告的判讀深度會再提升一個層級。",
        ]
    )
    return "\n".join(report_lines)
