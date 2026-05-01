from ai_investment_analyst.analysis.daily_screener import generate_all_daily_screenings


if __name__ == "__main__":
    snapshots = generate_all_daily_screenings()
    for snapshot in snapshots:
        print(
            f"Daily screener [{snapshot.strategy_key}] generated for {snapshot.run_date} "
            f"({snapshot.candidate_count} candidates)."
        )
        for result in snapshot.results[:10]:
            print(f"{result.rank}. {result.ticker} | score={result.total_score}")
