from ai_investment_analyst.analysis.daily_screener import generate_daily_screening


if __name__ == "__main__":
    snapshot = generate_daily_screening()
    print(f"Daily screener generated for {snapshot.run_date} ({snapshot.candidate_count} candidates).")
    for result in snapshot.results[:10]:
        print(f"{result.rank}. {result.ticker} | score={result.total_score}")
