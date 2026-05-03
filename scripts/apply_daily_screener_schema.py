from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ai_investment_analyst.db.connection import get_connection

SQL_PATH = BASE_DIR / "openspec" / "changes" / "stock-analysis-report" / "sql" / "006_daily_screener.sql"

if __name__ == "__main__":
    sql = SQL_PATH.read_text(encoding="utf-8")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    print("Daily screener schema applied successfully.")
