from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Callable, Sequence

from ai_investment_analyst.analysis.screener import (
    RankedCandidate,
    ScreeningCriteria,
    _latest_average_volume_5d_from_db,
    get_strategy_profile,
    load_screener_candidates,
    score_candidates,
)
from ai_investment_analyst.analysis.stock_report import (
    StockReportContext,
    load_market_context_from_yfinance,
    load_stock_report_context,
)
from ai_investment_analyst.db.screener_store import (
    list_default_screening_tickers,
    save_screening_snapshot,
)


@dataclass(frozen=True)
class DailyScreeningResult:
    rank: int
    ticker: str
    total_score: Decimal
    close_price: Decimal
    factor_scores: dict[str, Decimal]
    reasons: list[str]


@dataclass(frozen=True)
class DailyScreeningSnapshot:
    run_date: str
    generated_at: str
    universe_size: int
    candidate_count: int
    strategy_key: str
    results: list[DailyScreeningResult]


def _safe_volume_loader(volume_loader: Callable[[str], int | None]) -> Callable[[str], int | None]:
    def wrapper(ticker: str) -> int | None:
        try:
            return volume_loader(ticker)
        except Exception:
            return None

    return wrapper


def _safe_pb_ratio_loader(pb_ratio_loader: Callable[[str], Decimal | None] | None) -> Callable[[str], Decimal | None] | None:
    if pb_ratio_loader is None:
        return None

    def wrapper(ticker: str) -> Decimal | None:
        try:
            return pb_ratio_loader(ticker)
        except Exception:
            return None

    return wrapper


def _build_snapshot(
    ranked: list[RankedCandidate],
    universe_size: int,
    strategy_key: str,
    generated_at: datetime | None = None,
) -> DailyScreeningSnapshot:
    generated_at = generated_at or datetime.now(timezone.utc)
    results = [
        DailyScreeningResult(
            rank=index,
            ticker=item.candidate.ticker,
            total_score=item.total_score,
            close_price=item.candidate.close_price,
            factor_scores=item.factor_scores,
            reasons=item.reasons,
        )
        for index, item in enumerate(ranked, start=1)
    ]
    return DailyScreeningSnapshot(
        run_date=date.today().isoformat(),
        generated_at=generated_at.isoformat(),
        universe_size=universe_size,
        candidate_count=len(results),
        strategy_key=strategy_key,
        results=results,
    )


def generate_daily_screening(
    ticker_loader: Callable[[], list[str]] = list_default_screening_tickers,
    context_loader: Callable[[str], StockReportContext] = load_stock_report_context,
    market_context_loader: Callable[[str], StockReportContext] = load_market_context_from_yfinance,
    volume_loader: Callable[[str], int | None] | None = None,
    pb_ratio_loader: Callable[[str], Decimal | None] | None = None,
    criteria: ScreeningCriteria | None = None,
    strategy: str = 'balanced',
    snapshot_saver: Callable[[DailyScreeningSnapshot], object] = save_screening_snapshot,
) -> DailyScreeningSnapshot:
    strategy_profile = get_strategy_profile(strategy)
    criteria = criteria or strategy_profile.criteria
    tickers = ticker_loader()

    def safe_context_loader(ticker: str) -> StockReportContext:
        try:
            return context_loader(ticker)
        except Exception:
            return market_context_loader(ticker)

    load_kwargs = {
        'tickers': tickers,
        'context_loader': safe_context_loader,
        'pb_ratio_loader': _safe_pb_ratio_loader(pb_ratio_loader),
        'volume_loader': _safe_volume_loader(volume_loader or _latest_average_volume_5d_from_db),
    }
    candidates = load_screener_candidates(**load_kwargs)
    ranked = score_candidates(candidates, criteria, strategy=strategy_profile)
    snapshot = _build_snapshot(ranked, universe_size=len(tickers), strategy_key=strategy_profile.key)
    snapshot_saver(snapshot)
    return snapshot


def generate_all_daily_screenings(
    ticker_loader: Callable[[], list[str]] = list_default_screening_tickers,
    context_loader: Callable[[str], StockReportContext] = load_stock_report_context,
    market_context_loader: Callable[[str], StockReportContext] = load_market_context_from_yfinance,
    volume_loader: Callable[[str], int | None] | None = None,
    pb_ratio_loader: Callable[[str], Decimal | None] | None = None,
    criteria: ScreeningCriteria | None = None,
    snapshot_saver: Callable[[DailyScreeningSnapshot], object] = save_screening_snapshot,
    strategy_keys: Sequence[str] = ('balanced', 'growth', 'value', 'flow'),
) -> list[DailyScreeningSnapshot]:
    snapshots: list[DailyScreeningSnapshot] = []
    tickers = ticker_loader()
    for strategy_key in strategy_keys:
        snapshot = generate_daily_screening(
            ticker_loader=lambda tickers=tickers: list(tickers),
            context_loader=context_loader,
            market_context_loader=market_context_loader,
            volume_loader=volume_loader,
            pb_ratio_loader=pb_ratio_loader,
            criteria=criteria,
            strategy=strategy_key,
            snapshot_saver=snapshot_saver,
        )
        snapshots.append(snapshot)
    return snapshots
