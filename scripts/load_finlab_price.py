from ai_investment_analyst.etl.finlab_loader import load_finlab_price_data


if __name__ == "__main__":
    result = load_finlab_price_data()
    print(result)
