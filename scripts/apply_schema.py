from pathlib import Path

from ai_investment_analyst.db.connection import get_connection

BASE_DIR = Path(__file__).resolve().parents[1]
SCHEMA_SQL = BASE_DIR / "openspec" / "changes" / "ai-investment-analyst-db" / "sql" / "001_initial_schema.sql"
SEED_SQL = BASE_DIR / "openspec" / "changes" / "ai-investment-analyst-db" / "sql" / "002_seed_markets.sql"


def run_sql_file(path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


if __name__ == "__main__":
    run_sql_file(SCHEMA_SQL)
    run_sql_file(SEED_SQL)
    print("Schema and seed applied successfully.")
