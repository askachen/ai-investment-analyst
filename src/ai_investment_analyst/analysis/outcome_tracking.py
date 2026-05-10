from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ScreeningPick:
    strategy_key: str
    run_date: str | date
    ticker: str
    rank: int
    entry_price: Decimal


@dataclass(frozen=True)
class PriceObservation:
    trading_date: str | date
    close_price: Decimal


@dataclass(frozen=True)
class PickOutcome:
    strategy_key: str
    run_date: str
    ticker: str
    rank: int
    entry_price: Decimal
    target_date: str
    forward_date: str | None
    forward_close: Decimal | None
    forward_return_pct: Decimal | None
    is_hit: bool | None


@dataclass(frozen=True)
class StrategyOutcomeSummary:
    strategy_key: str
    horizon_days: int
    hit_threshold_pct: Decimal
    evaluated_count: int
    missing_count: int
    hit_count: int
    hit_rate_pct: Decimal | None
    average_return_pct: Decimal | None
    results: list[PickOutcome]


TWO_PLACES = Decimal('0.01')
ZERO = Decimal('0')
ONE_HUNDRED = Decimal('100')


def _parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _quantize_pct(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _first_price_on_or_after(
    observations: Sequence[PriceObservation],
    target_date: date,
) -> PriceObservation | None:
    dated = sorted(observations, key=lambda item: _parse_date(item.trading_date))
    for observation in dated:
        if _parse_date(observation.trading_date) >= target_date:
            return observation
    return None


def _forward_return_pct(entry_price: Decimal, forward_close: Decimal) -> Decimal | None:
    if entry_price <= ZERO:
        return None
    return _quantize_pct(((forward_close - entry_price) / entry_price) * ONE_HUNDRED)


def evaluate_strategy_outcomes(
    picks: Sequence[ScreeningPick],
    price_history: Mapping[str, Sequence[PriceObservation]],
    *,
    horizon_days: int = 7,
    hit_threshold_pct: Decimal = ZERO,
    top_n: int | None = None,
    strategy_key: str | None = None,
) -> StrategyOutcomeSummary:
    """Evaluate historical screener picks against forward prices.

    The default strategy is the first pick's strategy. This keeps single-strategy
    dashboard summaries deterministic while allowing callers to request another
    strategy explicitly.
    """
    if not picks:
        effective_strategy = strategy_key or 'unknown'
        return StrategyOutcomeSummary(
            strategy_key=effective_strategy,
            horizon_days=horizon_days,
            hit_threshold_pct=hit_threshold_pct,
            evaluated_count=0,
            missing_count=0,
            hit_count=0,
            hit_rate_pct=None,
            average_return_pct=None,
            results=[],
        )

    effective_strategy = strategy_key or picks[0].strategy_key
    selected = [pick for pick in picks if pick.strategy_key == effective_strategy]
    selected = sorted(selected, key=lambda pick: pick.rank)
    if top_n is not None:
        selected = selected[:top_n]

    results: list[PickOutcome] = []
    returns: list[Decimal] = []
    hit_count = 0
    missing_count = 0

    for pick in selected:
        run_date = _parse_date(pick.run_date)
        target_date = run_date + timedelta(days=horizon_days)
        forward_price = _first_price_on_or_after(price_history.get(pick.ticker, []), target_date)
        if forward_price is None:
            missing_count += 1
            results.append(
                PickOutcome(
                    strategy_key=pick.strategy_key,
                    run_date=run_date.isoformat(),
                    ticker=pick.ticker,
                    rank=pick.rank,
                    entry_price=pick.entry_price,
                    target_date=target_date.isoformat(),
                    forward_date=None,
                    forward_close=None,
                    forward_return_pct=None,
                    is_hit=None,
                )
            )
            continue

        forward_return = _forward_return_pct(pick.entry_price, forward_price.close_price)
        is_hit = forward_return is not None and forward_return >= hit_threshold_pct
        if forward_return is not None:
            returns.append(forward_return)
        if is_hit:
            hit_count += 1
        results.append(
            PickOutcome(
                strategy_key=pick.strategy_key,
                run_date=run_date.isoformat(),
                ticker=pick.ticker,
                rank=pick.rank,
                entry_price=pick.entry_price,
                target_date=target_date.isoformat(),
                forward_date=_parse_date(forward_price.trading_date).isoformat(),
                forward_close=forward_price.close_price,
                forward_return_pct=forward_return,
                is_hit=is_hit,
            )
        )

    evaluated_count = len(returns)
    hit_rate_pct = _quantize_pct((Decimal(hit_count) / Decimal(evaluated_count)) * ONE_HUNDRED) if evaluated_count else None
    average_return_pct = _quantize_pct(sum(returns, ZERO) / Decimal(evaluated_count)) if evaluated_count else None

    return StrategyOutcomeSummary(
        strategy_key=effective_strategy,
        horizon_days=horizon_days,
        hit_threshold_pct=hit_threshold_pct,
        evaluated_count=evaluated_count,
        missing_count=missing_count,
        hit_count=hit_count,
        hit_rate_pct=hit_rate_pct,
        average_return_pct=average_return_pct,
        results=results,
    )
