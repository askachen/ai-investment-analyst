from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import requests
from psycopg.rows import dict_row

from ai_investment_analyst.config import settings
from ai_investment_analyst.db.connection import get_connection

FINMIND_BASE_URL = "https://api.finmindtrade.com/api/v4"
DEFAULT_STOCK_IDS: tuple[str, ...] = ("2330", "2454")
DEFAULT_START_DATE = "2024-01-01"


@dataclass(frozen=True)
class StockSpec:
    stock_id: str
    market_code: str = "TW"
    instrument_type: str = "stock"


def decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        if value != value:
            return None
    except Exception:
        pass
    return Decimal(str(value))


def _row_id(row: Any) -> str:
    if isinstance(row, dict):
        return row["id"]
    return row[0]


def finmind_headers() -> dict[str, str]:
    if not settings.finmind_api_token:
        raise ValueError("FINMIND_API_TOKEN is not set")
    return {"Authorization": f"Bearer {settings.finmind_api_token}"}


def ensure_data_source(cur) -> str:
    cur.execute(
        """
        INSERT INTO data_sources (code, name, source_type, base_url, notes)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (code) DO UPDATE
        SET name = EXCLUDED.name, source_type = EXCLUDED.source_type, base_url = EXCLUDED.base_url, notes = EXCLUDED.notes, updated_at = NOW()
        RETURNING id
        """,
        ("finmind", "FinMind API", "rest-api", FINMIND_BASE_URL, "Imported by ai-investment-analyst FinMind loader"),
    )
    return _row_id(cur.fetchone())


def get_market_id(cur, market_code: str) -> str:
    cur.execute("SELECT id FROM markets WHERE code = %s", (market_code,))
    return _row_id(cur.fetchone())


def upsert_symbol(cur, market_id: str, stock_id: str) -> str:
    cur.execute(
        """
        INSERT INTO symbols (market_id, ticker, name, local_name, instrument_type, exchange, currency_code, country_code, metadata)
        VALUES (%s, %s, %s, %s, 'stock', 'TWSE/TPEx', 'TWD', 'TW', '{}'::jsonb)
        ON CONFLICT (market_id, ticker) DO UPDATE
        SET updated_at = NOW()
        RETURNING id
        """,
        (market_id, stock_id, stock_id, stock_id),
    )
    return _row_id(cur.fetchone())


def create_ingestion_run(cur, data_source_id: str, market_id: str, stock_ids: list[str], start_date: str) -> str:
    cur.execute(
        """
        INSERT INTO ingestion_runs (data_source_id, run_type, target_table, market_id, status, context)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        RETURNING id
        """,
        (data_source_id, "manual-finmind-monthly-revenue-load", "monthly_revenues", market_id, "running", json.dumps({"stock_ids": stock_ids, "start_date": start_date}, ensure_ascii=False)),
    )
    return _row_id(cur.fetchone())


def finalize_ingestion_run(cur, ingestion_run_id: str, *, status: str, records_received: int, records_inserted: int, records_updated: int, records_failed: int, error_message: str | None = None) -> None:
    cur.execute(
        """
        UPDATE ingestion_runs
        SET finished_at = NOW(), status = %s, records_received = %s, records_inserted = %s, records_updated = %s,
            records_failed = %s, error_message = %s, updated_at = NOW()
        WHERE id = %s
        """,
        (status, records_received, records_inserted, records_updated, records_failed, error_message, ingestion_run_id),
    )


def fetch_monthly_revenue(stock_id: str, start_date: str) -> list[dict[str, Any]]:
    response = requests.get(
        f"{FINMIND_BASE_URL}/data",
        headers=finmind_headers(),
        params={
            "dataset": "TaiwanStockMonthRevenue",
            "data_id": stock_id,
            "start_date": start_date,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != 200:
        raise ValueError(f"FinMind TaiwanStockMonthRevenue failed: {payload}")
    return payload.get("data", [])


def upsert_monthly_revenue(cur, *, symbol_id: str, data_source_id: str, ingestion_run_id: str, row: dict[str, Any]) -> None:
    revenue_year = int(row["revenue_year"])
    revenue_month = int(row["revenue_month"])
    revenue_period = date(revenue_year, revenue_month, 1)
    cur.execute(
        """
        INSERT INTO monthly_revenues (
            symbol_id, data_source_id, ingestion_run_id, revenue_year, revenue_month, revenue_period,
            revenue, revenue_month_change_percent, revenue_year_change_percent, raw_payload
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (symbol_id, data_source_id, revenue_period) DO UPDATE
        SET
            ingestion_run_id = EXCLUDED.ingestion_run_id,
            revenue = EXCLUDED.revenue,
            revenue_month_change_percent = EXCLUDED.revenue_month_change_percent,
            revenue_year_change_percent = EXCLUDED.revenue_year_change_percent,
            raw_payload = EXCLUDED.raw_payload,
            updated_at = NOW()
        """,
        (
            symbol_id,
            data_source_id,
            ingestion_run_id,
            revenue_year,
            revenue_month,
            revenue_period,
            decimal_or_none(row.get("revenue")),
            decimal_or_none(row.get("revenue_month_change_percent")),
            decimal_or_none(row.get("revenue_year_change_percent")),
            json.dumps(row, ensure_ascii=False),
        ),
    )


def load_monthly_revenue(stock_ids: tuple[str, ...] = DEFAULT_STOCK_IDS, start_date: str = DEFAULT_START_DATE) -> dict[str, Any]:
    summary: dict[str, Any] = {"processed": [], "failed": []}
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            data_source_id = ensure_data_source(cur)
            market_id = get_market_id(cur, "TW")
            ingestion_run_id = create_ingestion_run(cur, data_source_id, market_id, list(stock_ids), start_date)
            conn.commit()

        try:
            with conn.cursor() as cur:
                for stock_id in stock_ids:
                    symbol_id = upsert_symbol(cur, market_id, stock_id)
                    rows = fetch_monthly_revenue(stock_id, start_date)
                    for row in rows:
                        upsert_monthly_revenue(cur, symbol_id=symbol_id, data_source_id=data_source_id, ingestion_run_id=ingestion_run_id, row=row)
                    latest_row = rows[-1] if rows else None
                    summary["processed"].append(
                        {
                            "stock_id": stock_id,
                            "rows": len(rows),
                            "latest_period": f"{latest_row.get('revenue_year')}-{int(latest_row.get('revenue_month')):02d}" if latest_row else None,
                            "latest_revenue": str(decimal_or_none(latest_row.get("revenue"))) if latest_row else None,
                        }
                    )
                total_rows = sum(item["rows"] for item in summary["processed"])
                finalize_ingestion_run(cur, ingestion_run_id, status="success", records_received=total_rows, records_inserted=total_rows, records_updated=0, records_failed=0)
                conn.commit()
        except Exception as exc:
            with conn.cursor() as cur:
                total_rows = sum(item.get("rows", 0) for item in summary["processed"])
                finalize_ingestion_run(cur, ingestion_run_id, status="failed", records_received=total_rows, records_inserted=total_rows, records_updated=0, records_failed=1, error_message=str(exc))
                conn.commit()
            raise
    return summary


if __name__ == "__main__":
    result = load_monthly_revenue()
    print(json.dumps(result, ensure_ascii=False, indent=2))
