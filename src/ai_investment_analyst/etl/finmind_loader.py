from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import requests
from psycopg.rows import dict_row

from ai_investment_analyst.config import settings
from ai_investment_analyst.db.connection import get_connection
from ai_investment_analyst.db.price_store import refresh_price_daily_canonical, upsert_price_daily_raw

FINMIND_BASE_URL = "https://api.finmindtrade.com/api/v4"
DEFAULT_STOCK_IDS: tuple[str, ...] = ("2330", "2454")
DEFAULT_START_DATE = "2026-04-01"


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


def int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        if value != value:
            return None
    except Exception:
        pass
    return int(value)


def _row_id(row: Any) -> str:
    if isinstance(row, dict):
        return row["id"]
    return row[0]


def ensure_finmind_token() -> str:
    if not settings.finmind_api_token:
        raise ValueError("FINMIND_API_TOKEN is not set")
    return settings.finmind_api_token


def finmind_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {ensure_finmind_token()}"}


def fetch_finmind_stock_info(stock_id: str) -> dict[str, Any]:
    response = requests.get(f"{FINMIND_BASE_URL}/data", headers=finmind_headers(), params={"dataset": "TaiwanStockInfo"}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != 200:
        raise ValueError(f"FinMind TaiwanStockInfo failed: {payload}")
    for item in payload.get("data", []):
        if item.get("stock_id") == stock_id:
            return item
    return {"stock_id": stock_id, "stock_name": stock_id, "type": "stock"}


def fetch_finmind_stock_price(stock_id: str, start_date: str) -> list[dict[str, Any]]:
    response = requests.get(f"{FINMIND_BASE_URL}/data", headers=finmind_headers(), params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != 200:
        raise ValueError(f"FinMind TaiwanStockPrice failed: {payload}")
    return payload.get("data", [])


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
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Market {market_code} not found. Did you run schema seed?")
    return _row_id(row)


def upsert_symbol(cur, market_id: str, spec: StockSpec, info: dict[str, Any]) -> str:
    metadata = {"industry_category": info.get("industry_category"), "type": info.get("type"), "source": "FinMind"}
    cur.execute(
        """
        INSERT INTO symbols (market_id, ticker, name, local_name, instrument_type, exchange, sector, industry, currency_code, country_code, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (market_id, ticker) DO UPDATE
        SET name = EXCLUDED.name, local_name = EXCLUDED.local_name, instrument_type = EXCLUDED.instrument_type,
            exchange = EXCLUDED.exchange, sector = EXCLUDED.sector, industry = EXCLUDED.industry,
            currency_code = EXCLUDED.currency_code, country_code = EXCLUDED.country_code, metadata = EXCLUDED.metadata, updated_at = NOW()
        RETURNING id
        """,
        (market_id, spec.stock_id, info.get("stock_name") or spec.stock_id, info.get("stock_name") or spec.stock_id, spec.instrument_type, "TWSE/TPEx", info.get("industry_category"), info.get("industry_category"), "TWD", "TW", json.dumps(metadata, ensure_ascii=False)),
    )
    return _row_id(cur.fetchone())


def create_ingestion_run(cur, data_source_id: str, market_id: str, stock_ids: list[str], start_date: str) -> str:
    cur.execute(
        """
        INSERT INTO ingestion_runs (data_source_id, run_type, target_table, market_id, status, context)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        RETURNING id
        """,
        (data_source_id, "manual-finmind-load", "price_daily_raw,price_daily_canonical", market_id, "running", json.dumps({"stock_ids": stock_ids, "start_date": start_date}, ensure_ascii=False)),
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


def store_price_row(cur, *, symbol_id: str, data_source_id: str, ingestion_run_id: str, row: dict[str, Any]) -> None:
    trading_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
    open_price = decimal_or_none(row.get("open"))
    high_price = decimal_or_none(row.get("max"))
    low_price = decimal_or_none(row.get("min"))
    close_price = decimal_or_none(row.get("close"))
    price_change = decimal_or_none(row.get("spread"))
    volume = int_or_none(row.get("Trading_Volume"))
    turnover_value = decimal_or_none(row.get("Trading_money"))
    trade_count = int_or_none(row.get("Trading_turnover"))
    change_percent = None
    if open_price not in (None, Decimal("0")) and close_price is not None:
        change_percent = ((close_price - open_price) / open_price) * Decimal("100")
    upsert_price_daily_raw(
        cur,
        symbol_id=symbol_id,
        data_source_id=data_source_id,
        ingestion_run_id=ingestion_run_id,
        trading_date=trading_date,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        adjusted_close=None,
        price_change=price_change,
        change_percent=change_percent,
        volume=volume,
        turnover_value=turnover_value,
        trade_count=trade_count,
        raw_payload=row,
    )
    refresh_price_daily_canonical(cur, symbol_id=symbol_id, trading_date=trading_date)


def load_taiwan_stock_price(stock_ids: tuple[str, ...] = DEFAULT_STOCK_IDS, start_date: str = DEFAULT_START_DATE) -> dict[str, Any]:
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
                    spec = StockSpec(stock_id=stock_id)
                    info = fetch_finmind_stock_info(stock_id)
                    rows = fetch_finmind_stock_price(stock_id, start_date)
                    symbol_id = upsert_symbol(cur, market_id, spec, info)
                    for row in rows:
                        store_price_row(cur, symbol_id=symbol_id, data_source_id=data_source_id, ingestion_run_id=ingestion_run_id, row=row)
                    latest_row = rows[-1] if rows else None
                    summary["processed"].append({"stock_id": stock_id, "rows": len(rows), "latest_date": latest_row.get("date") if latest_row else None, "latest_close": str(decimal_or_none(latest_row.get("close"))) if latest_row else None})
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
    result = load_taiwan_stock_price()
    print(json.dumps(result, ensure_ascii=False, indent=2))
