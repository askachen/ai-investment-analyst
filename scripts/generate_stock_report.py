import sys

from ai_investment_analyst.analysis.stock_report import generate_stock_report


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "2330"
    print(generate_stock_report(ticker))
