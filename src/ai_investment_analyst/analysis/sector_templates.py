from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SectorTemplate:
    key: str
    label: str
    core_metrics: list[str] = field(default_factory=list)
    valuation_methods: list[str] = field(default_factory=list)
    catalyst_prompts: list[str] = field(default_factory=list)
    risk_prompts: list[str] = field(default_factory=list)
    evidence_checklist: list[str] = field(default_factory=list)

    def to_prompt_block(self) -> str:
        def render_list(title: str, items: list[str]) -> list[str]:
            return [title, *[f'- {item}' for item in items]]

        lines = [f'產業模板：{self.label}']
        lines.extend(render_list('核心指標', self.core_metrics))
        lines.extend(render_list('估值方法', self.valuation_methods))
        lines.extend(render_list('催化因素', self.catalyst_prompts))
        lines.extend(render_list('風險檢查', self.risk_prompts))
        lines.extend(render_list('證據檢核', self.evidence_checklist))
        return '\n'.join(lines)


SECTOR_TEMPLATES: dict[str, SectorTemplate] = {
    'general': SectorTemplate(
        key='general',
        label='通用',
        core_metrics=['營收成長', 'EPS', '毛利率', '現金流', '負債水準'],
        valuation_methods=['PE multiple', 'PB/ROE', 'PEG/growth'],
        catalyst_prompts=['營收趨勢改善', '產品或訂單催化', '法人預估上修'],
        risk_prompts=['需求轉弱', '成本上升', '評價修正'],
        evidence_checklist=['先確認價格、營收、財報資料是否完整。', '再檢查估值是否已反映成長預期。'],
    ),
    'semiconductor': SectorTemplate(
        key='semiconductor',
        label='半導體',
        core_metrics=['營收年增/月增', '毛利率', '產能利用率', '資本支出', '庫存天數', '先進製程/產品組合'],
        valuation_methods=['PE multiple', 'PEG/growth', 'EV/EBITDA', 'PB/ROE'],
        catalyst_prompts=['AI/HPC 需求', '先進製程放量', '報價改善', '庫存去化完成', '主要客戶拉貨'],
        risk_prompts=['產業循環反轉', '客戶砍單', '毛利率下滑', '資本支出回收期拉長', '地緣政治風險'],
        evidence_checklist=['先確認營收年增與月增是否同步改善。', '檢查毛利率是否支撐高估值。', '確認資本支出與產能利用率沒有背離。'],
    ),
    'financial': SectorTemplate(
        key='financial',
        label='金融',
        core_metrics=['利差', 'ROE', '資本適足率', '逾放比', '呆帳覆蓋率', '股利穩定度'],
        valuation_methods=['PB/ROE', '股利殖利率', 'PE multiple'],
        catalyst_prompts=['升息或利差擴大', '資產品質改善', '股利政策優於預期', '手續費收入成長'],
        risk_prompts=['信用風險', '逾放比上升', '殖利率曲線不利', '金融市場評價損失', '監理資本要求提高'],
        evidence_checklist=['先確認利差與資產品質方向。', '用 PB/ROE 而非單純 PE 作為主要估值錨。', '檢查股利是否由可持續盈餘支撐。'],
    ),
    'consumer': SectorTemplate(
        key='consumer',
        label='消費',
        core_metrics=['同店銷售', '毛利率', '存貨週轉', '通路擴張', '品牌定價力'],
        valuation_methods=['PE multiple', 'PEG/growth', 'FCF yield'],
        catalyst_prompts=['新品週期', '通路展店', '原物料成本下降', '促銷效率改善'],
        risk_prompts=['消費需求轉弱', '庫存去化壓力', '競爭促銷', '匯率與原物料成本'],
        evidence_checklist=['先確認營收成長是否來自量價同步。', '檢查毛利率是否被促銷侵蝕。'],
    ),
}

KEYWORD_TO_SECTOR = {
    '半導體': 'semiconductor',
    '晶圓': 'semiconductor',
    'IC': 'semiconductor',
    '封測': 'semiconductor',
    '金融': 'financial',
    '銀行': 'financial',
    '保險': 'financial',
    '證券': 'financial',
    '消費': 'consumer',
    '零售': 'consumer',
    '食品': 'consumer',
    '品牌': 'consumer',
}


def get_sector_template(sector: str | None) -> SectorTemplate:
    key = (sector or 'general').strip().lower()
    return SECTOR_TEMPLATES.get(key, SECTOR_TEMPLATES['general'])


def resolve_sector_template(company_name: str | None = None, industry: str | None = None) -> SectorTemplate:
    haystack = f'{company_name or ""} {industry or ""}'
    for keyword, sector_key in KEYWORD_TO_SECTOR.items():
        if keyword in haystack:
            return get_sector_template(sector_key)
    return get_sector_template('general')
