from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable

from ai_investment_analyst.analysis.stock_report import StockReportContext, _valuation_eps_ttm, load_stock_report_context
from ai_investment_analyst.db.connection import get_connection


ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")
DEFAULT_FACTOR_WEIGHTS = {
    "momentum": Decimal("0.25"),
    "revenue": Decimal("0.30"),
    "quality": Decimal("0.15"),
    "valuation": Decimal("0.20"),
    "liquidity": Decimal("0.10"),
}


@dataclass(frozen=True)
class ScreeningCandidate:
    ticker: str
    close_price: Decimal
    price_5d_change_pct: Decimal
    price_10d_change_pct: Decimal
    average_volume_5d: int | None
    revenue_yoy_pct: Decimal
    revenue_mom_pct: Decimal | None
    eps: Decimal
    pe_ratio: Decimal
    pb_ratio: Decimal | None = None


@dataclass(frozen=True)
class ScreeningCriteria:
    min_revenue_yoy_pct: Decimal = ZERO
    min_eps: Decimal = ZERO
    max_pe_ratio: Decimal = Decimal("999")
    min_average_volume_5d: int = 0


@dataclass(frozen=True)
class StrategyProfile:
    key: str
    label: str
    description: str
    weights: dict[str, Decimal] = field(default_factory=lambda: DEFAULT_FACTOR_WEIGHTS.copy())
    criteria: ScreeningCriteria = field(default_factory=ScreeningCriteria)


@dataclass(frozen=True)
class RankedCandidate:
    candidate: ScreeningCandidate
    passed: bool
    total_score: Decimal
    factor_scores: dict[str, Decimal]
    reasons: list[str]


STRATEGY_PROFILES = {
    "balanced": StrategyProfile(
        key="balanced",
        label="平衡多因子",
        description="兼顧盤面、營收、品質、估值與流動性，適合做每日預設榜單。",
        weights=DEFAULT_FACTOR_WEIGHTS.copy(),
    ),
    "growth": StrategyProfile(
        key="growth",
        label="成長動能",
        description="提高營收成長與價格動能權重，較偏中期成長股輪動。",
        weights={
            "momentum": Decimal("0.30"),
            "revenue": Decimal("0.35"),
            "quality": Decimal("0.15"),
            "valuation": Decimal("0.10"),
            "liquidity": Decimal("0.10"),
        },
    ),
    "value": StrategyProfile(
        key="value",
        label="價值穩健",
        description="提高估值與品質權重，偏好獲利穩定且評價較合理的標的。",
        weights={
            "momentum": Decimal("0.10"),
            "revenue": Decimal("0.05"),
            "quality": Decimal("0.20"),
            "valuation": Decimal("0.55"),
            "liquidity": Decimal("0.10"),
        },
    ),
    "flow": StrategyProfile(
        key="flow",
        label="流動性強勢",
        description="提高盤面與流動性權重，較偏短中線強勢股與成交量擴張。",
        weights={
            "momentum": Decimal("0.35"),
            "revenue": Decimal("0.20"),
            "quality": Decimal("0.10"),
            "valuation": Decimal("0.10"),
            "liquidity": Decimal("0.25"),
        },
    ),
}


def list_strategy_profiles() -> list[StrategyProfile]:
    return list(STRATEGY_PROFILES.values())


def get_strategy_profile(strategy: str | StrategyProfile | None = None) -> StrategyProfile:
    if isinstance(strategy, StrategyProfile):
        return strategy
    if strategy and strategy in STRATEGY_PROFILES:
        return STRATEGY_PROFILES[strategy]
    return STRATEGY_PROFILES["balanced"]


def _quantize_2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _clamp_score(value: Decimal) -> Decimal:
    return max(ZERO, min(ONE_HUNDRED, _quantize_2(value)))


def _pct_change(new: Decimal | None, old: Decimal | None) -> Decimal | None:
    if new is None or old in (None, ZERO):
        return None
    return _quantize_2(((new - old) / old) * ONE_HUNDRED)


def _momentum_score(candidate: ScreeningCandidate) -> Decimal:
    raw = (candidate.price_5d_change_pct * Decimal("6")) + (candidate.price_10d_change_pct * Decimal("4"))
    return _clamp_score(raw)


def _revenue_score(candidate: ScreeningCandidate) -> Decimal:
    revenue_mom_pct = candidate.revenue_mom_pct or ZERO
    raw = (candidate.revenue_yoy_pct * Decimal("3")) + (revenue_mom_pct * Decimal("4")) + Decimal("20")
    return _clamp_score(raw)


def _quality_score(candidate: ScreeningCandidate) -> Decimal:
    if candidate.eps <= ZERO:
        return ZERO
    # EPS is an absolute per-share amount and is not comparable across stocks
    # with different price levels or share bases. Treat positive TTM EPS as a
    # quality gate here; valuation attractiveness is handled by PE/PB below.
    return Decimal("70.00")


def _valuation_score(candidate: ScreeningCandidate) -> Decimal:
    pe_component = ONE_HUNDRED - (candidate.pe_ratio * Decimal("2.5"))
    if candidate.pb_ratio is None:
        return _clamp_score(pe_component)
    pb_component = ONE_HUNDRED - (candidate.pb_ratio * Decimal("8"))
    return _clamp_score((pe_component * Decimal("0.7")) + (pb_component * Decimal("0.3")))


def _liquidity_score(candidate: ScreeningCandidate) -> Decimal:
    if candidate.average_volume_5d in (None, 0) or candidate.average_volume_5d < 0:
        return ZERO
    raw = Decimal(candidate.average_volume_5d) / Decimal("500000")
    return _clamp_score(raw)


def _factor_scores(candidate: ScreeningCandidate) -> dict[str, Decimal]:
    return {
        "momentum": _momentum_score(candidate),
        "revenue": _revenue_score(candidate),
        "quality": _quality_score(candidate),
        "valuation": _valuation_score(candidate),
        "liquidity": _liquidity_score(candidate),
    }


def calculate_total_score(
    factor_scores: dict[str, Decimal],
    weights: dict[str, Decimal] | None = None,
) -> Decimal:
    effective_weights = weights or DEFAULT_FACTOR_WEIGHTS
    total = ZERO
    for key, weight in effective_weights.items():
        total += factor_scores.get(key, ZERO) * weight
    return _quantize_2(total)


def _build_reasons(candidate: ScreeningCandidate) -> list[str]:
    revenue_reason = (
        f"月營收年增 {_quantize_2(candidate.revenue_yoy_pct)}%，月增 {_quantize_2(candidate.revenue_mom_pct)}%。"
        if candidate.revenue_mom_pct is not None
        else f"月營收年增 {_quantize_2(candidate.revenue_yoy_pct)}%，月營收 MoM 資料尚缺。"
    )
    liquidity_reason = (
        f"近 5 日平均量 {candidate.average_volume_5d:,} 股，流動性可支撐中期觀察。"
        if candidate.average_volume_5d is not None and candidate.average_volume_5d > 0
        else "近 5 日成交量資料尚缺，目前流動性分數先以保守方式處理。"
    )
    reasons = [
        f"近 5 日漲幅 {_quantize_2(candidate.price_5d_change_pct)}%，近 10 日漲幅 {_quantize_2(candidate.price_10d_change_pct)}%，動能維持正向。"
        if candidate.price_10d_change_pct >= ZERO
        else f"近 10 日動能 {_quantize_2(candidate.price_10d_change_pct)}%，短線仍需觀察。",
        revenue_reason,
        f"EPS {_quantize_2(candidate.eps)} 元，獲利維持正值。"
        if candidate.eps > ZERO
        else f"EPS {_quantize_2(candidate.eps)} 元，獲利動能不足。",
        f"本益比 {_quantize_2(candidate.pe_ratio)} 倍，估值仍在可比較區間內。",
        liquidity_reason,
    ]
    if candidate.pb_ratio is None:
        reasons.append("PB 資料尚缺，目前估值分數先以 PE 為主。")
    else:
        reasons.append(f"股價淨值比 {_quantize_2(candidate.pb_ratio)} 倍，可輔助確認估值位置。")
    return reasons


def _passes(candidate: ScreeningCandidate, criteria: ScreeningCriteria) -> bool:
    average_volume_5d = candidate.average_volume_5d or 0
    return (
        candidate.revenue_yoy_pct >= criteria.min_revenue_yoy_pct
        and candidate.eps >= criteria.min_eps
        and candidate.pe_ratio <= criteria.max_pe_ratio
        and average_volume_5d >= criteria.min_average_volume_5d
    )


def _latest_average_volume_5d_from_db(ticker: str) -> int | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT ROUND(AVG(volume))
            FROM (
                SELECT pdc.volume
                FROM price_daily_canonical pdc
                JOIN symbols s ON s.id = pdc.symbol_id
                WHERE s.ticker = %s AND pdc.volume IS NOT NULL
                ORDER BY pdc.trading_date DESC
                LIMIT 5
            ) recent
            """,
            (ticker,),
        )
        row = cur.fetchone()
    if not row or row[0] is None:
        return None
    return int(row[0])


def load_screener_candidates(
    tickers: list[str],
    context_loader: Callable[[str], StockReportContext] = load_stock_report_context,
    volume_loader: Callable[[str], int | None] = _latest_average_volume_5d_from_db,
    pb_ratio_loader: Callable[[str], Decimal | None] | None = None,
) -> list[ScreeningCandidate]:
    candidates: list[ScreeningCandidate] = []
    for ticker in tickers:
        context = context_loader(ticker)
        if not context.latest or context.latest.close_price is None:
            continue
        if not context.latest_revenue:
            continue
        if context.latest_revenue.revenue_year_change_percent is None:
            continue
        eps = _valuation_eps_ttm(context.latest_financial_summary)
        if eps in (None, ZERO):
            continue
        if len(context.recent_prices) < 10:
            continue

        price_5d_change_pct = _pct_change(context.latest.close_price, context.recent_prices[4].close_price)
        price_10d_change_pct = _pct_change(context.latest.close_price, context.recent_prices[9].close_price)
        if price_5d_change_pct is None or price_10d_change_pct is None:
            continue

        pe_ratio = _quantize_2(context.latest.close_price / eps)
        pb_ratio = pb_ratio_loader(ticker) if pb_ratio_loader is not None else None
        candidates.append(
            ScreeningCandidate(
                ticker=ticker,
                close_price=context.latest.close_price,
                price_5d_change_pct=price_5d_change_pct,
                price_10d_change_pct=price_10d_change_pct,
                average_volume_5d=volume_loader(ticker),
                revenue_yoy_pct=_quantize_2(context.latest_revenue.revenue_year_change_percent or ZERO),
                revenue_mom_pct=_quantize_2(context.latest_revenue.revenue_month_change_percent)
                if context.latest_revenue.revenue_month_change_percent is not None
                else None,
                eps=_quantize_2(eps),
                pe_ratio=pe_ratio,
                pb_ratio=_quantize_2(pb_ratio) if pb_ratio is not None else None,
            )
        )
    return candidates


def score_candidates(
    candidates: list[ScreeningCandidate],
    criteria: ScreeningCriteria | None = None,
    strategy: str | StrategyProfile | None = None,
) -> list[RankedCandidate]:
    strategy_profile = get_strategy_profile(strategy)
    criteria = criteria or strategy_profile.criteria
    ranked: list[RankedCandidate] = []
    for candidate in candidates:
        factor_scores = _factor_scores(candidate)
        total_score = calculate_total_score(factor_scores, strategy_profile.weights)
        ranked.append(
            RankedCandidate(
                candidate=candidate,
                passed=_passes(candidate, criteria),
                total_score=total_score,
                factor_scores=factor_scores,
                reasons=_build_reasons(candidate),
            )
        )

    return sorted(
        [item for item in ranked if item.passed],
        key=lambda item: (item.total_score, item.factor_scores["momentum"], item.candidate.ticker),
        reverse=True,
    )


def render_screening_results(ranked_candidates: list[RankedCandidate], limit: int | None = None) -> str:
    if not ranked_candidates:
        return "AI Investment Analyst Screener\n\n目前沒有符合條件的候選名單。"

    selected = ranked_candidates[:limit] if limit is not None else ranked_candidates
    lines = [
        "AI Investment Analyst Screener",
        "",
        f"候選數量：{len(selected)}",
        "",
    ]
    for index, ranked in enumerate(selected, start=1):
        factor_summary = (
            f"動能 {ranked.factor_scores['momentum']}/100｜"
            f"營收 {ranked.factor_scores['revenue']}/100｜"
            f"品質 {ranked.factor_scores['quality']}/100｜"
            f"估值 {ranked.factor_scores['valuation']}/100｜"
            f"流動性 {ranked.factor_scores['liquidity']}/100"
        )
        lines.extend(
            [
                f"{index}. {ranked.candidate.ticker}｜總分 {ranked.total_score}",
                factor_summary,
                *[f"- {reason}" for reason in ranked.reasons],
                "",
            ]
        )
    return "\n".join(lines).rstrip()
