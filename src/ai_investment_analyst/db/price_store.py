from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

PRICE_SOURCE_PRIORITY: dict[tuple[str, str], list[str]] = {
    ("TW", "stock"): ["finmind", "yfinance", "finlab"],
    ("US", "stock"): ["yfinance", "finmind", "finlab"],
    ("US", "index"): ["yfinance", "finmind", "finlab"],
    ("TW", "index"): ["finmind", "yfinance", "finlab"],
}

DEFAULT_PRIORITY = ["yfinance", "finmind", "finlab"]


def _priority_rank(market_code: str, instrument_type: str, source_code: str) -> int:
    priority = PRICE_SOURCE_PRIORITY.get((market_code, instrument_type), DEFAULT_PRIORITY)
    if source_code in priority:
        return priority.index(source_code)
    return len(priority) + 100


def upsert_price_daily_raw(
    cur,
    *,
    symbol_id: str,
    data_source_id: str,
    ingestion_run_id: str | None,
    trading_date,
    open_price: Decimal | None,
    high_price: Decimal | None,
    low_price: Decimal | None,
    close_price: Decimal | None,
    adjusted_close: Decimal | None,
    price_change: Decimal | None,
    change_percent: Decimal | None,
    volume: int | None,
    turnover_value: Decimal | None,
    trade_count: int | None,
    raw_payload: dict[str, Any],
) -> str:
    cur.execute(
        """
        INSERT INTO price_daily_raw (
            symbol_id, data_source_id, ingestion_run_id, trading_date,
            open_price, high_price, low_price, close_price, adjusted_close,
            price_change, change_percent, volume, turnover_value, trade_count,
            raw_payload
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (symbol_id, data_source_id, trading_date) DO UPDATE
        SET
            ingestion_run_id = EXCLUDED.ingestion_run_id,
            open_price = EXCLUDED.open_price,
            high_price = EXCLUDED.high_price,
            low_price = EXCLUDED.low_price,
            close_price = EXCLUDED.close_price,
            adjusted_close = EXCLUDED.adjusted_close,
            price_change = EXCLUDED.price_change,
            change_percent = EXCLUDED.change_percent,
            volume = EXCLUDED.volume,
            turnover_value = EXCLUDED.turnover_value,
            trade_count = EXCLUDED.trade_count,
            raw_payload = EXCLUDED.raw_payload,
            updated_at = NOW()
        RETURNING id
        """,
        (
            symbol_id,
            data_source_id,
            ingestion_run_id,
            trading_date,
            open_price,
            high_price,
            low_price,
            close_price,
            adjusted_close,
            price_change,
            change_percent,
            volume,
            turnover_value,
            trade_count,
            json.dumps(raw_payload, ensure_ascii=False, default=str),
        ),
    )
    row = cur.fetchone()
    if isinstance(row, dict):
        return row["id"]
    return row[0]


def refresh_price_daily_canonical(cur, *, symbol_id: str, trading_date) -> None:
    cur.execute(
        """
        SELECT
            pdr.id,
            pdr.symbol_id,
            pdr.data_source_id,
            pdr.trading_date,
            pdr.open_price,
            pdr.high_price,
            pdr.low_price,
            pdr.close_price,
            pdr.adjusted_close,
            pdr.price_change,
            pdr.change_percent,
            pdr.volume,
            pdr.turnover_value,
            pdr.trade_count,
            pdr.raw_payload,
            ds.code AS source_code,
            m.code AS market_code,
            s.instrument_type
        FROM price_daily_raw pdr
        JOIN data_sources ds ON ds.id = pdr.data_source_id
        JOIN symbols s ON s.id = pdr.symbol_id
        JOIN markets m ON m.id = s.market_id
        WHERE pdr.symbol_id = %s AND pdr.trading_date = %s
        """,
        (symbol_id, trading_date),
    )
    rows = cur.fetchall()
    if not rows:
        return

    best = min(rows, key=lambda row: _priority_rank(row["market_code"], row["instrument_type"], row["source_code"]))
    cur.execute(
        """
        INSERT INTO price_daily_canonical (
            symbol_id, trading_date, selected_raw_id, data_source_id,
            open_price, high_price, low_price, close_price, adjusted_close,
            price_change, change_percent, volume, turnover_value, trade_count,
            raw_payload
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (symbol_id, trading_date) DO UPDATE
        SET
            selected_raw_id = EXCLUDED.selected_raw_id,
            data_source_id = EXCLUDED.data_source_id,
            open_price = EXCLUDED.open_price,
            high_price = EXCLUDED.high_price,
            low_price = EXCLUDED.low_price,
            close_price = EXCLUDED.close_price,
            adjusted_close = EXCLUDED.adjusted_close,
            price_change = EXCLUDED.price_change,
            change_percent = EXCLUDED.change_percent,
            volume = EXCLUDED.volume,
            turnover_value = EXCLUDED.turnover_value,
            trade_count = EXCLUDED.trade_count,
            raw_payload = EXCLUDED.raw_payload,
            updated_at = NOW()
        """,
        (
            best["symbol_id"],
            best["trading_date"],
            best["id"],
            best["data_source_id"],
            best["open_price"],
            best["high_price"],
            best["low_price"],
            best["close_price"],
            best["adjusted_close"],
            best["price_change"],
            best["change_percent"],
            best["volume"],
            best["turnover_value"],
            best["trade_count"],
            json.dumps(best["raw_payload"], ensure_ascii=False, default=str),
        ),
    )
