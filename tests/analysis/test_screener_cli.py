from decimal import Decimal

from ai_investment_analyst.analysis.stock_report import (
    FinancialSummary,
    PricePoint,
    RevenuePoint,
    StockReportContext,
)
from ai_investment_analyst.cli.screener import run_screener_cli


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


def test_run_screener_cli_renders_ranked_report():
    contexts = {
        "2330": make_context(
            ticker="2330",
            close_price="850",
            recent_prices=["850", "840", "830", "820", "800", "790", "780", "770", "760", "750"],
            revenue_yoy_pct="22.3",
            revenue_mom_pct="8.5",
            eps="10.25",
        ),
        "2454": make_context(
            ticker="2454",
            close_price="1200",
            recent_prices=["1200", "1185", "1170", "1160", "1156.07", "1148", "1136", "1125", "1116", "1117.32"],
            revenue_yoy_pct="14.0",
            revenue_mom_pct="2.0",
            eps="8.8",
        ),
    }

    report = run_screener_cli(
        ["2330", "2454"],
        context_loader=lambda ticker: contexts[ticker],
        volume_loader=lambda ticker: {"2330": 42000000, "2454": 12000000}[ticker],
        pb_ratio_loader=lambda ticker: {"2330": Decimal("4.8"), "2454": Decimal("5.2")}[ticker],
    )

    assert "AI Investment Analyst Screener" in report
    assert "1. 2330" in report
    assert "2. 2454" in report
    assert "總分" in report


def test_run_screener_cli_applies_filter_arguments():
    contexts = {
        "2330": make_context(
            ticker="2330",
            close_price="850",
            recent_prices=["850", "840", "830", "820", "800", "790", "780", "770", "760", "750"],
            revenue_yoy_pct="22.3",
            revenue_mom_pct="8.5",
            eps="10.25",
        ),
        "1101": make_context(
            ticker="1101",
            close_price="42",
            recent_prices=["42", "42.5", "43", "43.2", "43.5", "44", "44.5", "45", "45.5", "46"],
            revenue_yoy_pct="3.1",
            revenue_mom_pct="-1.2",
            eps="2.1",
        ),
    }

    report = run_screener_cli(
        ["--min-revenue-yoy", "5", "2330", "1101"],
        context_loader=lambda ticker: contexts[ticker],
        volume_loader=lambda ticker: {"2330": 42000000, "1101": 8000000}[ticker],
        pb_ratio_loader=lambda ticker: {"2330": Decimal("4.8"), "1101": Decimal("1.3")}[ticker],
    )

    assert "1. 2330" in report
    assert "1101" not in report


def test_run_screener_cli_falls_back_when_primary_context_loader_fails():
    fallback_context = make_context(
        ticker="2330",
        close_price="850",
        recent_prices=["850", "840", "830", "820", "800", "790", "780", "770", "760", "750"],
        revenue_yoy_pct="22.3",
        revenue_mom_pct="8.5",
        eps="10.25",
    )

    report = run_screener_cli(
        ["2330"],
        context_loader=lambda ticker: (_ for _ in ()).throw(RuntimeError("db down")),
        market_context_loader=lambda ticker: fallback_context,
        volume_loader=lambda ticker: 42000000,
        pb_ratio_loader=lambda ticker: Decimal("4.8"),
    )

    assert "1. 2330" in report
