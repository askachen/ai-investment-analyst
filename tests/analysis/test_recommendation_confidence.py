from ai_investment_analyst.analysis.data_quality import DataQualityDomain, StockDataQuality
from ai_investment_analyst.analysis.recommendation_confidence import derive_recommendation_confidence


def test_derive_recommendation_confidence_caps_report_confidence_by_data_quality():
    quality = StockDataQuality(
        overall_status='partial',
        confidence_label='中高',
        completeness_pct=75,
        domains=[DataQualityDomain('price', '價格', 'fresh', '價格新鮮。')],
        warnings=['月營收可用但不完整。'],
    )

    confidence = derive_recommendation_confidence(quality, report_confidence='高')

    assert confidence.score == 70
    assert confidence.level == '中'
    assert '資料完整度 75%' in confidence.evidence_rules
    assert '月營收可用但不完整。' in confidence.warnings


def test_derive_recommendation_confidence_penalizes_missing_core_signals_and_risks():
    quality = StockDataQuality(
        overall_status='missing',
        confidence_label='低',
        completeness_pct=35,
        domains=[DataQualityDomain('financial', '財報', 'missing', '缺少財報摘要資料。')],
        warnings=['缺少財報摘要資料。'],
    )

    confidence = derive_recommendation_confidence(
        quality,
        report_confidence='中高',
        has_core_signals=False,
        has_clear_risk_factors=False,
    )

    assert confidence.score == 0
    assert confidence.level == '低'
    assert any('缺少足夠核心訊號' in warning for warning in confidence.warnings)
    assert any('風險因子揭露不足' in warning for warning in confidence.warnings)


def test_derive_recommendation_confidence_is_conservative_without_data_quality():
    confidence = derive_recommendation_confidence(None, report_confidence='中高')

    assert confidence.score == 58
    assert confidence.level == '中'
    assert any('尚未取得資料新鮮度' in warning for warning in confidence.warnings)
