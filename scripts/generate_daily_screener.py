from pathlib import Path
import sys

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ai_investment_analyst.analysis.daily_screener_job import run_daily_screener_job


if __name__ == "__main__":
    result = run_daily_screener_job()
    print(f"Upstream refresh completed for {len(result.tickers)} tickers: {', '.join(result.tickers)}")
    for dataset_name, summary in result.source_refresh.items():
        print(f"[{dataset_name}] {summary}")
    for snapshot in result.snapshots:
        print(
            f"Daily screener [{snapshot.strategy_key}] generated for {snapshot.run_date} "
            f"({snapshot.candidate_count} candidates)."
        )
        for entry in snapshot.results[:10]:
            print(f"{entry.rank}. {entry.ticker} | score={entry.total_score}")
