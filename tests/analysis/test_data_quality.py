from datetime import date
from decimal import Decimal

from ai_investment_analyst.analysis.data_quality import assess_stock_report_data_quality
from ai_investment_analyst.analysis.stock_report import (
    FinancialSummary,
    PricePoint,
    RevenuePoint,
    StockReportContext,
)


def test_assess_stock_report_data_quality_marks_complete_recent_data_as_fresh():
    context = StockReportContext(
        ticker='2330',
        latest=PricePoint(trading_date='2026-05-09', close_price=Decimal('850'), source_code='twse'),
        recent_prices=[],
        latest_revenue=RevenuePoint(
            revenue_period='2026-04-01',
            revenue=Decimal('100'),
            revenue_month_change_percent=Decimal('3'),
            revenue_year_change_percent=Decimal('20'),
        ),
        latest_financial_summary=FinancialSummary(
            report_date='2026-03-31',
            revenue=Decimal('1000'),
            net_income=Decimal('200'),
            eps=Decimal('5'),
        ),
    )

    quality = assess_stock_report_data_quality(context, as_of=date(2026, 5, 10))

    assert quality.overall_status == 'fresh'
    assert quality.confidence_label == '高'
    assert quality.completeness_pct == 100
    assert quality.warnings == []


def test_assess_stock_report_data_quality_surfaces_stale_and_missing_domains():
    context = StockReportContext(
        ticker='2454',
        latest=PricePoint(trading_date='2026-04-20', close_price=Decimal('1200'), source_code='twse'),
        recent_prices=[],
        latest_revenue=None,
        latest_financial_summary=FinancialSummary(
            report_date='2025-09-30',
            revenue=Decimal('1000'),
            net_income=None,
            eps=Decimal('8'),
        ),
    )

    quality = assess_stock_report_data_quality(context, as_of=date(2026, 5, 10))

    assert quality.overall_status == 'missing'
    assert quality.confidence_label == '低'
    assert quality.completeness_pct < 70
    assert [domain.status for domain in quality.domains] == ['stale', 'missing', 'stale']
    assert any('缺少月營收資料' in warning for warning in quality.warnings)


def test_assess_stock_report_data_quality_treats_live_market_fallback_as_partial_evidence():
    context = StockReportContext(
        ticker='AAPL',
        latest=PricePoint(trading_date='live-info', close_price=Decimal('210'), source_code='yfinance-live'),
        recent_prices=[],
        latest_revenue=RevenuePoint(
            revenue_period='live-info',
            revenue=Decimal('100'),
            revenue_month_change_percent=None,
            revenue_year_change_percent=Decimal('8'),
        ),
        latest_financial_summary=FinancialSummary(
            report_date='live-info',
            revenue=Decimal('1000'),
            net_income=Decimal('200'),
            eps=Decimal('6'),
        ),
    )

    quality = assess_stock_report_data_quality(context, as_of=date(2026, 5, 10))

    assert quality.overall_status == 'partial'
    assert quality.confidence_label == '中高'
    assert any(domain.key == 'revenue' and domain.status == 'partial' for domain in quality.domains)
