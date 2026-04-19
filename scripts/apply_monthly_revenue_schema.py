from pathlib import Path

from ai_investment_analyst.db.connection import get_connection

BASE_DIR = Path(__file__).resolve().parents[1]
SQL_PATH = BASE_DIR / "openspec" / "changes" / "stock-analysis-report" / "sql" / "004_monthly_revenue.sql"

if __name__ == "__main__":
    sql = SQL_PATH.read_text(encoding="utf-8")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    print("Monthly revenue schema applied successfully.")
