from decimal import Decimal

from ai_investment_analyst.analysis.news import NewsItem
from ai_investment_analyst.analysis.stock_report import (
    FinancialSummary,
    PricePoint,
    RevenuePoint,
    StockReportContext,
    generate_stock_report,
)


class FakeClient:
    def __init__(self, text=None, should_fail=False):
        self.text = text
        self.should_fail = should_fail

    def generate_report(self, ticker, facts, news_items):
        if self.should_fail:
            raise RuntimeError("llm unavailable")
        return self.text or f"【個股分析報告】{ticker}\n投資評級：偏多"


def make_context():
    return StockReportContext(
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


def test_generate_stock_report_uses_llm_when_available():
    report = generate_stock_report(
        "2330",
        context_loader=lambda ticker: make_context(),
        news_fetcher=lambda ticker, count=3: [NewsItem(title="AI demand strong", publisher="Reuters", link="https://example.com", published_at="2026-04-21T08:00:00Z", summary="Orders remain robust")],
        report_client=FakeClient(text="【個股分析報告】2330\n投資評級：偏多\n結論：維持正向"),
    )

    assert "結論：維持正向" in report


def test_generate_stock_report_falls_back_when_llm_fails():
    report = generate_stock_report(
        "2330",
        context_loader=lambda ticker: make_context(),
        news_fetcher=lambda ticker, count=3: [NewsItem(title="AI demand strong", publisher="Reuters", link="https://example.com", published_at="2026-04-21T08:00:00Z", summary="Orders remain robust")],
        report_client=FakeClient(should_fail=True),
        news_translator=lambda items: [NewsItem(title="AI 需求強勁", publisher=items[0].publisher, link=items[0].link, published_at=items[0].published_at, summary="訂單持續成長")],
    )

    assert "重點摘要" in report
    assert "風險提示" in report
    assert "AI 需求強勁" in report
    assert "訂單持續成長" in report


def test_generate_stock_report_uses_market_fallback_when_db_loader_fails():
    report = generate_stock_report(
        "2330",
        context_loader=lambda ticker: (_ for _ in ()).throw(RuntimeError("db down")),
        market_context_loader=lambda ticker: make_context(),
        news_fetcher=lambda ticker, count=3: [],
        report_client=FakeClient(should_fail=True),
    )

    assert "【個股分析報告】2330" in report
    assert "投資評級" in report
