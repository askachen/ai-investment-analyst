from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

FactorStatus = Literal['fresh', 'partial', 'missing']

ZERO = Decimal('0')
ONE_HUNDRED = Decimal('100')


@dataclass(frozen=True)
class FundamentalFactorInputs:
    gross_margin_pct: Decimal | None = None
    operating_margin_pct: Decimal | None = None
    net_margin_pct: Decimal | None = None
    roe_pct: Decimal | None = None
    roa_pct: Decimal | None = None
    operating_cash_flow: Decimal | None = None
    capital_expenditure: Decimal | None = None
    total_debt: Decimal | None = None
    equity: Decimal | None = None
    revenue_growth_yoy_pct: Decimal | None = None
    eps_revision_pct: Decimal | None = None


@dataclass(frozen=True)
class FundamentalFactorScore:
    key: str
    label: str
    score: Decimal
    status: FactorStatus
    evidence: str


@dataclass(frozen=True)
class FundamentalFactorResult:
    composite_score: Decimal
    factor_scores: dict[str, FundamentalFactorScore]
    missing_factors: list[str] = field(default_factory=list)
    evidence_summary: list[str] = field(default_factory=list)


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _clamp(value: Decimal) -> Decimal:
    return _q2(max(ZERO, min(ONE_HUNDRED, value)))


def _average(values: list[Decimal]) -> Decimal:
    if not values:
        return ZERO
    return sum(values, ZERO) / Decimal(len(values))


def _score_pct(value: Decimal | None, excellent_at: Decimal, *, floor_at: Decimal = ZERO) -> Decimal | None:
    if value is None:
        return None
    if excellent_at == floor_at:
        return ONE_HUNDRED if value >= excellent_at else ZERO
    raw = ((value - floor_at) / (excellent_at - floor_at)) * ONE_HUNDRED
    return _clamp(raw)


def _status_from_present(present: int, expected: int) -> FactorStatus:
    if present == 0:
        return 'missing'
    if present < expected:
        return 'partial'
    return 'fresh'


def _profitability_score(inputs: FundamentalFactorInputs) -> FundamentalFactorScore:
    components = [
        _score_pct(inputs.gross_margin_pct, Decimal('50')),
        _score_pct(inputs.operating_margin_pct, Decimal('35')),
        _score_pct(inputs.net_margin_pct, Decimal('30')),
        _score_pct(inputs.roe_pct, Decimal('25')),
        _score_pct(inputs.roa_pct, Decimal('15')),
    ]
    present = [component for component in components if component is not None]
    status = _status_from_present(len(present), len(components))
    score = _clamp(_average(present)) if present else ZERO
    evidence = '獲利能力：毛利率、營益率、淨利率、ROE/ROA 綜合評分。' if present else '獲利能力資料不足。'
    return FundamentalFactorScore('profitability', '獲利能力', score, status, evidence)


def _cash_flow_score(inputs: FundamentalFactorInputs) -> FundamentalFactorScore:
    if inputs.operating_cash_flow is None:
        return FundamentalFactorScore('cash_flow', '現金流品質', ZERO, 'missing', '營業現金流資料不足。')
    if inputs.operating_cash_flow <= ZERO:
        return FundamentalFactorScore('cash_flow', '現金流品質', ZERO, 'fresh', '營業現金流為負，現金流品質偏弱。')
    capex = abs(inputs.capital_expenditure) if inputs.capital_expenditure is not None else ZERO
    free_cash_flow = inputs.operating_cash_flow - capex
    conversion = (free_cash_flow / inputs.operating_cash_flow) * ONE_HUNDRED
    score = _clamp(conversion)
    status = 'fresh' if inputs.capital_expenditure is not None else 'partial'
    evidence = f'現金流品質：自由現金流轉換率約 {_q2(conversion)}%。'
    return FundamentalFactorScore('cash_flow', '現金流品質', score, status, evidence)


def _leverage_score(inputs: FundamentalFactorInputs) -> FundamentalFactorScore:
    if inputs.total_debt is None or inputs.equity is None or inputs.equity <= ZERO:
        return FundamentalFactorScore('leverage', '槓桿風險', ZERO, 'missing', '負債與權益資料不足。')
    debt_to_equity = inputs.total_debt / inputs.equity
    score = _clamp(ONE_HUNDRED - (debt_to_equity * Decimal('60')))
    evidence = f'槓桿風險：D/E 約 {_q2(debt_to_equity)}，分數越高代表槓桿越低。'
    if score <= Decimal('25'):
        evidence += ' 槓桿偏高，需提高風險折扣。'
    return FundamentalFactorScore('leverage', '槓桿風險', score, 'fresh', evidence)


def _trend_score(inputs: FundamentalFactorInputs) -> FundamentalFactorScore:
    components = [
        _score_pct(inputs.revenue_growth_yoy_pct, Decimal('25'), floor_at=Decimal('-20')),
        _score_pct(inputs.eps_revision_pct, Decimal('10'), floor_at=Decimal('-10')),
    ]
    present = [component for component in components if component is not None]
    status = _status_from_present(len(present), len(components))
    score = _clamp(_average(present)) if present else ZERO
    evidence = '趨勢修正：營收年增與 EPS 預估修正方向。' if present else '趨勢修正資料不足。'
    return FundamentalFactorScore('trend', '趨勢修正', score, status, evidence)


def normalize_fundamental_factors(inputs: FundamentalFactorInputs) -> FundamentalFactorResult:
    factor_scores = {
        'profitability': _profitability_score(inputs),
        'cash_flow': _cash_flow_score(inputs),
        'leverage': _leverage_score(inputs),
        'trend': _trend_score(inputs),
    }
    weights = {
        'profitability': Decimal('0.35'),
        'cash_flow': Decimal('0.25'),
        'leverage': Decimal('0.20'),
        'trend': Decimal('0.20'),
    }
    composite = sum((factor_scores[key].score * weight for key, weight in weights.items()), ZERO)
    missing_factors = [key for key, score in factor_scores.items() if score.status == 'missing']
    evidence_summary = [score.evidence for score in factor_scores.values()]
    return FundamentalFactorResult(
        composite_score=_q2(composite),
        factor_scores=factor_scores,
        missing_factors=missing_factors,
        evidence_summary=evidence_summary,
    )
