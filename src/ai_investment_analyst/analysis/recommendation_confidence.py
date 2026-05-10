from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ai_investment_analyst.analysis.data_quality import StockDataQuality

ConfidenceLevel = Literal['高', '中高', '中', '中低', '低']


@dataclass(frozen=True)
class RecommendationConfidence:
    level: ConfidenceLevel
    score: int
    evidence_rules: list[str]
    warnings: list[str]


def _base_score_from_report_confidence(report_confidence: str | None) -> int:
    normalized = (report_confidence or '').strip()
    return {
        '高': 90,
        '中高': 78,
        '中': 65,
        '中低': 48,
        '低': 35,
    }.get(normalized, 55)


def _level_from_score(score: int) -> ConfidenceLevel:
    if score >= 85:
        return '高'
    if score >= 72:
        return '中高'
    if score >= 58:
        return '中'
    if score >= 42:
        return '中低'
    return '低'


def derive_recommendation_confidence(
    data_quality: StockDataQuality | None,
    *,
    report_confidence: str | None = None,
    has_clear_risk_factors: bool = True,
    has_core_signals: bool = True,
) -> RecommendationConfidence:
    """Convert report evidence into an explicit confidence score and display rules."""
    score = _base_score_from_report_confidence(report_confidence)
    evidence_rules: list[str] = []
    warnings: list[str] = []

    if data_quality is None:
        score -= 20
        warnings.append('尚未取得資料新鮮度與完整度評估，推薦信心需保守解讀。')
    else:
        score = min(score, data_quality.completeness_pct)
        evidence_rules.append(f'資料完整度 {data_quality.completeness_pct}%')
        evidence_rules.append(f'資料信心 {data_quality.confidence_label}')
        warnings.extend(data_quality.warnings)
        if data_quality.overall_status in {'missing', 'stale'}:
            score -= 15
            warnings.append('資料狀態不足以支撐高信心推薦。')
        elif data_quality.overall_status == 'partial':
            score -= 5

    if not has_core_signals:
        score -= 20
        warnings.append('缺少足夠核心訊號，暫不應給高信心結論。')
    else:
        evidence_rules.append('具備核心價格 / 基本面訊號')

    if not has_clear_risk_factors:
        score -= 10
        warnings.append('風險因子揭露不足，信心需下修。')
    else:
        evidence_rules.append('已揭露主要風險因子')

    score = max(0, min(100, score))
    return RecommendationConfidence(
        level=_level_from_score(score),
        score=score,
        evidence_rules=evidence_rules,
        warnings=warnings,
    )
