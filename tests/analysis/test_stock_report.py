from decimal import Decimal

from ai_investment_analyst.analysis.stock_report import (
    FinancialSummary,
    PricePoint,
    RevenuePoint,
    StockReportContext,
    build_report_facts,
    render_fallback_report,
)
from ai_investment_analyst.analysis.news import NewsItem


def make_context() -> StockReportContext:
    return StockReportContext(
        ticker="2330",
        latest=PricePoint(trading_date="2026-04-21", close_price=Decimal("850"), source_code="yfinance"),
        recent_prices=[
            PricePoint(trading_date="2026-04-21", close_price=Decimal("850"), source_code="yfinance"),
            PricePoint(trading_date="2026-04-20", close_price=Decimal("840"), source_code="yfinance"),
            PricePoint(trading_date="2026-04-17", close_price=Decimal("830"), source_code="yfinance"),
            PricePoint(trading_date="2026-04-16", close_price=Decimal("825"), source_code="yfinance"),
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


def test_generate_stock_report_includes_analyst_sections():
    facts = build_report_facts(make_context())
    news_items = [
        NewsItem(
            title="AI demand remains strong",
            publisher="Reuters",
            link="https://example.com/news-1",
            published_at="2026-04-21T08:00:00Z",
            summary="Large customers continue to increase AI server orders.",
        )
    ]

    report = render_fallback_report("2330", facts, news_items)

    assert "【個股分析報告】2330" in report
    assert "投資評級" in report
    assert "重點摘要" in report
    assert "價格與技術面觀察" in report
    assert "基本面觀察" in report
    assert "估值觀察" in report
    assert "評價標籤" in report
    assert "合理價區間" in report
    assert "新聞與市場催化" in report
    assert "利多催化" in report
    assert "中性觀察" in report
    assert "潛在風險" in report
    assert "風險提示" in report
    assert "結論" in report
    assert "分析師觀點" in report
    assert "投資建議" in report
    assert "一句話投資主軸" in report
    assert "財務摘要表" in report
    assert "目標價推導" in report
    assert "Bull Case" in report
    assert "Base Case" in report
    assert "Bear Case" in report


def test_build_report_facts_produces_financial_snapshot_and_scenarios():
    facts = build_report_facts(make_context())

    assert "營收" in facts.financial_snapshot[0]
    assert "EPS" in " ".join(facts.financial_snapshot)
    assert "目標價" in facts.target_price_summary
    assert "AI" in facts.thesis
    assert facts.bull_case
    assert facts.base_case
    assert facts.bear_case
