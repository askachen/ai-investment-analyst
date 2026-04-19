from ai_investment_analyst.etl.yfinance_loader import load_latest_prices


if __name__ == "__main__":
    result = load_latest_prices()
    print(result)
