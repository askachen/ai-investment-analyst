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
class StockReportContext:
    ticker: str
    latest: PricePoint | None
    recent_prices: list[PricePoint]


def load_stock_report_context(ticker: str, limit: int = 10) -> StockReportContext:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                s.ticker,
                pdc.trading_date,
                pdc.close_price,
                ds.code AS source_code
            FROM price_daily_canonical pdc
            JOIN symbols s ON s.id = pdc.symbol_id
            JOIN data_sources ds ON ds.id = pdc.data_source_id
            WHERE s.ticker = %s
            ORDER BY pdc.trading_date DESC
            LIMIT %s
            """,
            (ticker, limit),
        )
        rows = cur.fetchall()

    points = [
        PricePoint(
            trading_date=row[1].isoformat(),
            close_price=row[2],
            source_code=row[3],
        )
        for row in rows
    ]
    latest = points[0] if points else None
    return StockReportContext(ticker=ticker, latest=latest, recent_prices=points)


def _pct_change(new: Decimal | None, old: Decimal | None) -> str:
    if new is None or old in (None, Decimal("0")):
        return "N/A"
    change = ((new - old) / old) * Decimal("100")
    return f"{change:.2f}%"


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

    report_lines.extend(
        [
            "- 分析說明：",
            "  目前這是第一版報告，主要根據 canonical 價格資料生成。",
            "  後續可再加入月營收、財報、新聞與法人資料，讓報告更完整。",
        ]
    )
    return "\n".join(report_lines)
