from ai_investment_analyst.etl.finmind_monthly_revenue_loader import load_monthly_revenue


if __name__ == "__main__":
    result = load_monthly_revenue()
    print(result)
