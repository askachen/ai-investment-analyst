from ai_investment_analyst.etl.finmind_financial_loader import load_financial_statements


if __name__ == "__main__":
    result = load_financial_statements()
    print(result)
