from ai_investment_analyst.etl.finmind_loader import load_taiwan_stock_price


if __name__ == "__main__":
    result = load_taiwan_stock_price()
    print(result)
