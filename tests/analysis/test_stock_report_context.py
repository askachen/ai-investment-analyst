from decimal import Decimal

import pandas as pd

from ai_investment_analyst.analysis import stock_report
from ai_investment_analyst.analysis.stock_report import (
    FinancialSummary,
    PricePoint,
    RevenuePoint,
    StockReportContext,
    build_report_facts,
    candidate_market_tickers,
    load_market_context_from_yfinance,
)


def test_build_report_facts_derives_rating_and_risk_flags():
    context = StockReportContext(
        ticker="2330",
        latest=PricePoint(trading_date="2026-04-21", close_price=Decimal("850"), source_code="yfinance"),
        recent_prices=[
            PricePoint(trading_date="2026-04-21", close_price=Decimal("850"), source_code="yfinance"),
            PricePoint(trading_date="2026-04-20", close_price=Decimal("840"), source_code="yfinance"),
            PricePoint(trading_date="2026-04-17", close_price=Decimal("830"), source_code="yfinance"),
            PricePoint(trading_date="2026-04-16", close_price=Decimal("820"), source_code="yfinance"),
            PricePoint(trading_date="2026-04-15", close_price=Decimal("800"), source_code="yfinance"),
            PricePoint(trading_date="2026-04-14", close_price=Decimal("790"), source_code="yfinance"),
            PricePoint(trading_date="2026-04-13", close_price=Decimal("780"), source_code="yfinance"),
            PricePoint(trading_date="2026-04-10", close_price=Decimal("770"), source_code="yfinance"),
            PricePoint(trading_date="2026-04-09", close_price=Decimal("760"), source_code="yfinance"),
            PricePoint(trading_date="2026-04-08", close_price=Decimal("750"), source_code="yfinance"),
        ],
        latest_revenue=RevenuePoint(
            revenue_period="2026-03-01",
            revenue=Decimal("210000000000"),
            revenue_month_change_percent=Decimal("8.5"),
            revenue_year_change_percent=Decimal("22.3"),
        ),
        latest_financial_summary=FinancialSummary(
            report_date="2025-12-31",
            revenue=Decimal("650000000000"),
            net_income=Decimal("260000000000"),
            eps=Decimal("10.25"),
        ),
    )

    facts = build_report_facts(context)

    assert facts.rating == "偏多"
    assert "近 5 日漲幅" in facts.price_observation
    assert "月營收年增" in facts.fundamental_observation
    assert "本益比" in facts.valuation_observation
    assert "合理價區間" in facts.valuation_range
    assert facts.valuation_label in {"偏高", "合理", "偏低"}
    assert "評價" in facts.conclusion
    assert facts.key_points
    assert facts.risk_flags


def test_candidate_market_tickers_adds_tw_alias_for_numeric_symbols():
    assert candidate_market_tickers("2330") == ["2330", "2330.TW"]
    assert candidate_market_tickers("AAPL") == ["AAPL"]


def test_load_market_context_from_yfinance_leaves_monthly_revenue_change_unknown(monkeypatch):
    history = pd.DataFrame(
        {"Close": [100.0, 101.0, 102.5]},
        index=pd.to_datetime(["2026-04-01", "2026-04-02", "2026-04-03"]),
    )

    class FakeTicker:
        info = {
            "totalRevenue": 123456789,
            "netIncomeToCommon": 9876543,
            "trailingEps": 12.34,
            "revenueGrowth": 0.351,
        }

        def history(self, period: str, interval: str, auto_adjust: bool):
            assert period == "1mo"
            assert interval == "1d"
            assert auto_adjust is False
            return history

    monkeypatch.setattr(stock_report.yf, "Ticker", lambda ticker: FakeTicker())

    context = load_market_context_from_yfinance("2330")

    assert context.latest_revenue is not None
    assert context.latest_revenue.revenue_year_change_percent == Decimal("35.100")
    assert context.latest_revenue.revenue_month_change_percent is None
