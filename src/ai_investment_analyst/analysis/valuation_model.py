from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

ValuationLabel = Literal['偏低估', '合理', '偏高估', '資料不足']
ConfidenceLabel = Literal['高', '中', '低']

ZERO = Decimal('0')


@dataclass(frozen=True)
class ValuationInputs:
    current_price: Decimal | None
    eps_ttm: Decimal | None = None
    book_value_per_share: Decimal | None = None
    revenue_growth_yoy_pct: Decimal | None = None
    roe_pct: Decimal | None = None
    sector_pe_median: Decimal | None = None
    market_pe_median: Decimal | None = None


@dataclass(frozen=True)
class ValuationEstimate:
    label: ValuationLabel
    blended_target_price: Decimal | None
    fair_value_range: tuple[Decimal, Decimal] | None
    margin_of_safety_pct: Decimal | None
    confidence_label: ConfidenceLabel
    method_prices: dict[str, Decimal] = field(default_factory=dict)
    missing_methods: list[str] = field(default_factory=list)
    evidence_summary: list[str] = field(default_factory=list)


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _clamp(value: Decimal, lower: Decimal, upper: Decimal) -> Decimal:
    return max(lower, min(upper, value))


def _positive(value: Decimal | None) -> bool:
    return value is not None and value > ZERO


def _fair_pe(inputs: ValuationInputs) -> Decimal:
    return inputs.sector_pe_median or inputs.market_pe_median or Decimal('18')


def _pe_multiple_price(inputs: ValuationInputs) -> Decimal | None:
    if not _positive(inputs.eps_ttm):
        return None
    return _q2(inputs.eps_ttm * _fair_pe(inputs))


def _pb_roe_price(inputs: ValuationInputs) -> Decimal | None:
    if not _positive(inputs.book_value_per_share) or inputs.roe_pct is None:
        return None
    fair_pb = _clamp(inputs.roe_pct / Decimal('10'), Decimal('0.5'), Decimal('4.0'))
    return _q2(inputs.book_value_per_share * fair_pb)


def _peg_growth_price(inputs: ValuationInputs) -> Decimal | None:
    if not _positive(inputs.eps_ttm) or inputs.revenue_growth_yoy_pct is None:
        return None
    growth_pe = _clamp(inputs.revenue_growth_yoy_pct, Decimal('5'), Decimal('35'))
    return _q2(inputs.eps_ttm * growth_pe)


def _label_from_margin(margin_pct: Decimal | None) -> ValuationLabel:
    if margin_pct is None:
        return '資料不足'
    if margin_pct >= Decimal('15'):
        return '偏低估'
    if margin_pct <= Decimal('-15'):
        return '偏高估'
    return '合理'


def _confidence_from_methods(method_count: int) -> ConfidenceLabel:
    if method_count >= 3:
        return '高'
    if method_count == 2:
        return '中'
    return '低'


def estimate_intrinsic_value(inputs: ValuationInputs) -> ValuationEstimate:
    method_prices: dict[str, Decimal] = {}
    missing_methods: list[str] = []
    evidence_summary: list[str] = []

    pe_price = _pe_multiple_price(inputs)
    if pe_price is None:
        missing_methods.append('pe_multiple')
        evidence_summary.append('PE multiple：缺少正 EPS，無法建立本益比錨點。')
    else:
        method_prices['pe_multiple'] = pe_price
        evidence_summary.append(f'PE multiple：使用公平本益比 {_q2(_fair_pe(inputs))} 倍推估 {pe_price}。')

    pb_price = _pb_roe_price(inputs)
    if pb_price is None:
        missing_methods.append('pb_roe')
        evidence_summary.append('PB/ROE：缺少每股淨值或 ROE，暫不納入。')
    else:
        method_prices['pb_roe'] = pb_price
        evidence_summary.append(f'PB/ROE：依 ROE 對應合理 PB 推估 {pb_price}。')

    peg_price = _peg_growth_price(inputs)
    if peg_price is None:
        missing_methods.append('peg_growth')
        evidence_summary.append('成長估值：缺少 EPS 或成長率，暫不納入 PEG。')
    else:
        method_prices['peg_growth'] = peg_price
        evidence_summary.append(f'成長估值：依營收成長率對應合理 PE 推估 {peg_price}。')

    if not method_prices:
        return ValuationEstimate(
            label='資料不足',
            blended_target_price=None,
            fair_value_range=None,
            margin_of_safety_pct=None,
            confidence_label='低',
            method_prices=method_prices,
            missing_methods=missing_methods,
            evidence_summary=evidence_summary,
        )

    preferred_weights = {
        'pe_multiple': Decimal('0.45'),
        'pb_roe': Decimal('0.25'),
        'peg_growth': Decimal('0.30'),
    }
    available_weight = sum(preferred_weights[key] for key in method_prices)
    blended = sum(method_prices[key] * (preferred_weights[key] / available_weight) for key in method_prices)
    blended_target = _q2(blended)
    fair_range = (_q2(blended_target * Decimal('0.90')), _q2(blended_target * Decimal('1.10')))

    margin_pct = None
    if _positive(inputs.current_price):
        margin_pct = _q2(((blended_target - inputs.current_price) / inputs.current_price) * Decimal('100'))

    return ValuationEstimate(
        label=_label_from_margin(margin_pct),
        blended_target_price=blended_target,
        fair_value_range=fair_range,
        margin_of_safety_pct=margin_pct,
        confidence_label=_confidence_from_methods(len(method_prices)),
        method_prices=method_prices,
        missing_methods=missing_methods,
        evidence_summary=evidence_summary,
    )
