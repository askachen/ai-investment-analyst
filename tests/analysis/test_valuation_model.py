from decimal import Decimal

from ai_investment_analyst.analysis.valuation_model import ValuationInputs, estimate_intrinsic_value


def test_estimate_intrinsic_value_blends_pe_pb_and_growth_methods():
    result = estimate_intrinsic_value(
        ValuationInputs(
            current_price=Decimal('100'),
            eps_ttm=Decimal('8'),
            book_value_per_share=Decimal('50'),
            revenue_growth_yoy_pct=Decimal('18'),
            roe_pct=Decimal('20'),
            sector_pe_median=Decimal('16'),
            market_pe_median=Decimal('14'),
        )
    )

    assert result.label == '偏低估'
    assert result.blended_target_price == Decimal('125.80')
    assert result.fair_value_range == (Decimal('113.22'), Decimal('138.38'))
    assert result.margin_of_safety_pct == Decimal('25.80')
    assert result.method_prices['pe_multiple'] == Decimal('128.00')
    assert result.method_prices['pb_roe'] == Decimal('100.00')
    assert result.method_prices['peg_growth'] == Decimal('144.00')
    assert result.missing_methods == []
    assert any('PE multiple' in item for item in result.evidence_summary)


def test_estimate_intrinsic_value_marks_missing_methods_but_keeps_pe_anchor():
    result = estimate_intrinsic_value(
        ValuationInputs(
            current_price=Decimal('120'),
            eps_ttm=Decimal('6'),
            market_pe_median=Decimal('15'),
        )
    )

    assert result.label == '偏高估'
    assert result.blended_target_price == Decimal('90.00')
    assert result.margin_of_safety_pct == Decimal('-25.00')
    assert result.method_prices == {'pe_multiple': Decimal('90.00')}
    assert result.missing_methods == ['pb_roe', 'peg_growth']
    assert result.confidence_label == '低'


def test_estimate_intrinsic_value_flags_expensive_growth_mismatch():
    result = estimate_intrinsic_value(
        ValuationInputs(
            current_price=Decimal('200'),
            eps_ttm=Decimal('5'),
            book_value_per_share=Decimal('40'),
            revenue_growth_yoy_pct=Decimal('5'),
            roe_pct=Decimal('8'),
            sector_pe_median=Decimal('15'),
        )
    )

    assert result.label == '偏高估'
    assert result.blended_target_price == Decimal('49.25')
    assert result.margin_of_safety_pct == Decimal('-75.38')
    assert any('成長估值' in item for item in result.evidence_summary)
