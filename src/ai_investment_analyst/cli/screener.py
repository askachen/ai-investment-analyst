from __future__ import annotations

import argparse
from decimal import Decimal
from typing import Callable, Sequence

from ai_investment_analyst.analysis.screener import (
    ScreeningCriteria,
    get_strategy_profile,
    load_screener_candidates,
    render_screening_results,
    score_candidates,
)
from ai_investment_analyst.analysis.stock_report import (
    StockReportContext,
    load_market_context_from_yfinance,
    load_stock_report_context,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the AI Investment Analyst stock screener")
    parser.add_argument("tickers", nargs="+", help="Ticker symbols to score, e.g. 2330 2454 AAPL")
    parser.add_argument("--strategy", choices=["balanced", "growth", "value", "flow"], default="balanced")
    parser.add_argument("--min-revenue-yoy", type=Decimal, default=Decimal("0"))
    parser.add_argument("--min-eps", type=Decimal, default=Decimal("0"))
    parser.add_argument("--max-pe", type=Decimal, default=Decimal("999"))
    parser.add_argument("--min-average-volume-5d", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    return parser


def run_screener_cli(
    argv: Sequence[str] | None = None,
    *,
    context_loader: Callable[[str], StockReportContext] = load_stock_report_context,
    market_context_loader: Callable[[str], StockReportContext] = load_market_context_from_yfinance,
    volume_loader: Callable[[str], int] | None = None,
    pb_ratio_loader: Callable[[str], Decimal | None] | None = None,
) -> str:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    strategy_profile = get_strategy_profile(args.strategy)
    criteria = ScreeningCriteria(
        min_revenue_yoy_pct=args.min_revenue_yoy,
        min_eps=args.min_eps,
        max_pe_ratio=args.max_pe,
        min_average_volume_5d=args.min_average_volume_5d,
    )

    def safe_context_loader(ticker: str) -> StockReportContext:
        try:
            return context_loader(ticker)
        except Exception:
            return market_context_loader(ticker)

    load_kwargs = {
        "tickers": args.tickers,
        "context_loader": safe_context_loader,
        "pb_ratio_loader": pb_ratio_loader,
    }
    if volume_loader is not None:
        load_kwargs["volume_loader"] = volume_loader
    candidates = load_screener_candidates(**load_kwargs)
    ranked = score_candidates(candidates, criteria, strategy=strategy_profile)
    return render_screening_results(ranked, limit=args.limit)


def main(argv: Sequence[str] | None = None) -> int:
    print(run_screener_cli(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
