from ai_investment_analyst.analysis.sector_templates import get_sector_template, resolve_sector_template


def test_get_sector_template_for_semiconductor_focuses_on_cycle_and_capex():
    template = get_sector_template('semiconductor')

    assert template.key == 'semiconductor'
    assert template.label == '半導體'
    assert '毛利率' in template.core_metrics
    assert '資本支出' in template.core_metrics
    assert 'PE multiple' in template.valuation_methods
    assert '產業循環反轉' in template.risk_prompts
    assert template.evidence_checklist[0] == '先確認營收年增與月增是否同步改善。'


def test_resolve_sector_template_maps_taiwan_keywords_and_defaults_to_general():
    assert resolve_sector_template('台積電', industry='半導體製造').key == 'semiconductor'
    assert resolve_sector_template('金融控股', industry='銀行').key == 'financial'
    assert resolve_sector_template('Unknown Co', industry='未知產業').key == 'general'


def test_get_sector_template_returns_sector_specific_prompt_blocks():
    template = get_sector_template('financial')

    prompt = template.to_prompt_block()

    assert '產業模板：金融' in prompt
    assert '利差' in prompt
    assert '逾放比' in prompt
    assert 'PB/ROE' in prompt
    assert '信用風險' in prompt
