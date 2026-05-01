from decimal import Decimal

from ai_investment_analyst.analysis.stock_report import (
    FinancialSummary,
    PricePoint,
    RevenuePoint,
    StockReportContext,
)
from ai_investment_analyst.analysis.daily_screener import generate_daily_screening


def make_context(
    ticker: str,
    close_price: str,
    recent_prices: list[str],
    revenue_yoy_pct: str,
    revenue_mom_pct: str,
    eps: str,
) -> StockReportContext:
    return StockReportContext(
        ticker=ticker,
        latest=PricePoint(trading_date="2026-04-21", close_price=Decimal(close_price), source_code="test"),
        recent_prices=[
            PricePoint(trading_date=f"2026-04-{21-index:02d}", close_price=Decimal(value), source_code="test")
            for index, value in enumerate(recent_prices)
        ],
        latest_revenue=RevenuePoint(
            revenue_period="2026-03-01",
            revenue=Decimal("1000000000"),
            revenue_month_change_percent=Decimal(revenue_mom_pct),
            revenue_year_change_percent=Decimal(revenue_yoy_pct),
        ),
        latest_financial_summary=FinancialSummary(
            report_date="2025-12-31",
            revenue=Decimal("3000000000"),
            net_income=Decimal("500000000"),
            eps=Decimal(eps),
        ),
    )


def test_generate_daily_screening_scores_and_persists_snapshot():
    contexts = {
        "2330": make_context("2330", "850", ["850", "840", "830", "820", "800", "790", "780", "770", "760", "750"], "22.3", "8.5", "10.25"),
        "2454": make_context("2454", "1200", ["1200", "1185", "1170", "1160", "1156.07", "1148", "1136", "1125", "1116", "1117.32"], "14.0", "2.0", "8.8"),
    }
    saved = {}

    snapshot = generate_daily_screening(
        ticker_loader=lambda: ["2330", "2454"],
        context_loader=lambda ticker: contexts[ticker],
        volume_loader=lambda ticker: {"2330": 42000000, "2454": 12000000}[ticker],
        pb_ratio_loader=lambda ticker: {"2330": Decimal("4.8"), "2454": Decimal("5.2")}[ticker],
        snapshot_saver=lambda snapshot: saved.setdefault('snapshot', snapshot),
    )

    assert snapshot.run_date
    assert snapshot.results[0].ticker == '2330'
    assert snapshot.results[0].rank == 1
    assert saved['snapshot'].results[1].ticker == '2454'


def test_generate_daily_screening_uses_market_fallback_when_db_loader_fails():
    fallback_context = make_context(
        '2330',
        '850',
        ["850", "840", "830", "820", "800", "790", "780", "770", "760", "750"],
        '22.3',
        '8.5',
        '10.25',
    )

    snapshot = generate_daily_screening(
        ticker_loader=lambda: ['2330'],
        context_loader=lambda ticker: (_ for _ in ()).throw(RuntimeError('db down')),
        market_context_loader=lambda ticker: fallback_context,
        volume_loader=lambda ticker: 42000000,
        pb_ratio_loader=lambda ticker: Decimal('4.8'),
        snapshot_saver=lambda snapshot: snapshot,
    )

    assert snapshot.results[0].ticker == '2330'
