from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from ai_investment_analyst.analysis.stock_report import StockReportContext

QualityStatus = Literal['fresh', 'partial', 'stale', 'missing', 'unknown']


@dataclass(frozen=True)
class DataQualityDomain:
    key: str
    label: str
    status: QualityStatus
    message: str
    observed_at: str | None = None


@dataclass(frozen=True)
class StockDataQuality:
    overall_status: QualityStatus
    confidence_label: str
    completeness_pct: int
    domains: list[DataQualityDomain]
    warnings: list[str]


def _parse_date(value: str | None) -> date | None:
    if not value or value == 'live-info':
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def _age_days(value: str | None, as_of: date) -> int | None:
    parsed = _parse_date(value)
    if parsed is None:
        return None
    return max((as_of - parsed).days, 0)


def _status_rank(status: QualityStatus) -> int:
    return {
        'fresh': 4,
        'partial': 3,
        'stale': 2,
        'unknown': 1,
        'missing': 0,
    }[status]


def _price_quality(context: StockReportContext, as_of: date) -> DataQualityDomain:
    if context.latest is None:
        return DataQualityDomain('price', '價格', 'missing', '缺少可用價格資料。')
    age = _age_days(context.latest.trading_date, as_of)
    if context.latest.source_code == 'yfinance-live' or context.latest.trading_date == 'live-info':
        return DataQualityDomain('price', '價格', 'fresh', '使用即時市場備援資料。', context.latest.trading_date)
    if age is None:
        return DataQualityDomain('price', '價格', 'unknown', '價格日期格式無法判讀。', context.latest.trading_date)
    if age <= 3:
        return DataQualityDomain('price', '價格', 'fresh', f'價格資料 {age} 天內更新。', context.latest.trading_date)
    if age <= 7:
        return DataQualityDomain('price', '價格', 'partial', f'價格資料已 {age} 天未更新，仍可參考但需留意。', context.latest.trading_date)
    return DataQualityDomain('price', '價格', 'stale', f'價格資料已 {age} 天未更新。', context.latest.trading_date)


def _revenue_quality(context: StockReportContext, as_of: date) -> DataQualityDomain:
    revenue = context.latest_revenue
    if revenue is None:
        return DataQualityDomain('revenue', '月營收', 'missing', '缺少月營收資料。')
    if revenue.revenue_period == 'live-info':
        status = 'partial' if revenue.revenue_year_change_percent is not None else 'unknown'
        return DataQualityDomain('revenue', '月營收', status, '使用市場摘要資料，非正式月營收明細。', revenue.revenue_period)
    age = _age_days(revenue.revenue_period, as_of)
    if age is None:
        return DataQualityDomain('revenue', '月營收', 'unknown', '月營收期間無法判讀。', revenue.revenue_period)
    if age <= 45 and revenue.revenue_year_change_percent is not None:
        return DataQualityDomain('revenue', '月營收', 'fresh', f'月營收資料約 {age} 天內。', revenue.revenue_period)
    if age <= 75:
        return DataQualityDomain('revenue', '月營收', 'partial', '月營收可用，但 YoY/MoM 或時效性不完整。', revenue.revenue_period)
    return DataQualityDomain('revenue', '月營收', 'stale', f'月營收資料已 {age} 天未更新。', revenue.revenue_period)


def _financial_quality(context: StockReportContext, as_of: date) -> DataQualityDomain:
    summary = context.latest_financial_summary
    if summary is None:
        return DataQualityDomain('financial', '財報', 'missing', '缺少財報摘要資料。')
    if summary.report_date == 'live-info':
        return DataQualityDomain('financial', '財報', 'partial', '使用市場摘要財務資料，非完整財報明細。', summary.report_date)
    age = _age_days(summary.report_date, as_of)
    if age is None:
        return DataQualityDomain('financial', '財報', 'unknown', '財報日期無法判讀。', summary.report_date)
    key_fields = [summary.revenue, summary.net_income, summary.eps]
    has_all_key_fields = all(value is not None for value in key_fields)
    if age <= 130 and has_all_key_fields:
        return DataQualityDomain('financial', '財報', 'fresh', f'財報摘要約 {age} 天內且欄位完整。', summary.report_date)
    if age <= 190:
        return DataQualityDomain('financial', '財報', 'partial', '財報摘要可用，但欄位或時效性不完整。', summary.report_date)
    return DataQualityDomain('financial', '財報', 'stale', f'財報摘要已 {age} 天未更新。', summary.report_date)


def assess_stock_report_data_quality(context: StockReportContext, *, as_of: date | None = None) -> StockDataQuality:
    as_of = as_of or date.today()
    domains = [
        _price_quality(context, as_of),
        _revenue_quality(context, as_of),
        _financial_quality(context, as_of),
    ]
    score = sum(_status_rank(domain.status) for domain in domains)
    max_score = len(domains) * _status_rank('fresh')
    completeness_pct = round((score / max_score) * 100) if max_score else 0
    worst_rank = min(_status_rank(domain.status) for domain in domains)

    if worst_rank >= _status_rank('fresh'):
        overall_status: QualityStatus = 'fresh'
        confidence_label = '高'
    elif worst_rank >= _status_rank('partial'):
        overall_status = 'partial'
        confidence_label = '中高'
    elif any(domain.status == 'missing' for domain in domains):
        overall_status = 'missing'
        confidence_label = '低'
    else:
        overall_status = 'stale'
        confidence_label = '中低'

    warnings = [domain.message for domain in domains if domain.status in {'partial', 'stale', 'missing', 'unknown'}]
    return StockDataQuality(
        overall_status=overall_status,
        confidence_label=confidence_label,
        completeness_pct=completeness_pct,
        domains=domains,
        warnings=warnings,
    )
