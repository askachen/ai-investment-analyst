from decimal import Decimal

from ai_investment_analyst.analysis.fundamental_factors import (
    FundamentalFactorInputs,
    normalize_fundamental_factors,
)


def test_normalize_fundamental_factors_scores_profitability_cash_flow_and_leverage():
    result = normalize_fundamental_factors(
        FundamentalFactorInputs(
            gross_margin_pct=Decimal('55'),
            operating_margin_pct=Decimal('42'),
            net_margin_pct=Decimal('38'),
            roe_pct=Decimal('28'),
            roa_pct=Decimal('18'),
            operating_cash_flow=Decimal('900'),
            capital_expenditure=Decimal('-350'),
            total_debt=Decimal('1200'),
            equity=Decimal('6000'),
            revenue_growth_yoy_pct=Decimal('30'),
            eps_revision_pct=Decimal('8'),
        )
    )

    assert result.composite_score == Decimal('86.88')
    assert result.factor_scores['profitability'].score == Decimal('100.00')
    assert result.factor_scores['cash_flow'].score == Decimal('61.11')
    assert result.factor_scores['leverage'].score == Decimal('88.00')
    assert result.factor_scores['trend'].score == Decimal('95.00')
    assert result.missing_factors == []
    assert any('獲利能力' in summary for summary in result.evidence_summary)


def test_normalize_fundamental_factors_penalizes_missing_data():
    result = normalize_fundamental_factors(
        FundamentalFactorInputs(
            net_margin_pct=Decimal('12'),
            revenue_growth_yoy_pct=Decimal('5'),
        )
    )

    assert result.composite_score == Decimal('25.11')
    assert result.factor_scores['profitability'].status == 'partial'
    assert result.factor_scores['cash_flow'].status == 'missing'
    assert result.factor_scores['leverage'].status == 'missing'
    assert result.factor_scores['trend'].status == 'partial'
    assert 'cash_flow' in result.missing_factors
    assert 'leverage' in result.missing_factors


def test_normalize_fundamental_factors_clamps_weak_or_negative_inputs():
    result = normalize_fundamental_factors(
        FundamentalFactorInputs(
            gross_margin_pct=Decimal('-5'),
            operating_margin_pct=Decimal('-10'),
            net_margin_pct=Decimal('-20'),
            roe_pct=Decimal('-12'),
            roa_pct=Decimal('-8'),
            operating_cash_flow=Decimal('-100'),
            capital_expenditure=Decimal('-100'),
            total_debt=Decimal('900'),
            equity=Decimal('100'),
            revenue_growth_yoy_pct=Decimal('-30'),
            eps_revision_pct=Decimal('-15'),
        )
    )

    assert result.composite_score == Decimal('0.00')
    assert all(score.score == Decimal('0.00') for score in result.factor_scores.values())
    assert any('槓桿偏高' in summary for summary in result.evidence_summary)
