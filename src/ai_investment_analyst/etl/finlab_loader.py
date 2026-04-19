from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import finlab
from finlab import data
import pandas as pd
from psycopg.rows import dict_row

from ai_investment_analyst.config import settings
from ai_investment_analyst.db.connection import get_connection

DEFAULT_STOCK_IDS: tuple[str, ...] = ("2330", "2454")
DEFAULT_LOOKBACK_ROWS = 10


@dataclass(frozen=True)
class StockSpec:
    stock_id: str
    market_code: str = "TW"
    instrument_type: str = "stock"


def decimal_or_none(value: Any) -> Decimal | None:
    if value is None or pd.isna(value):
        return None
    return Decimal(str(value))


def int_or_none(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def _row_id(row: Any) -> str:
    if isinstance(row, dict):
        return row["id"]
    return row[0]


def ensure_finlab_login() -> None:
    if not settings.finlab_api_key:
        raise ValueError("FINLAB_API_KEY is not set")
    finlab.login(settings.finlab_api_key)


def ensure_data_source(cur) -> str:
    cur.execute(
        """
        INSERT INTO data_sources (code, name, source_type, base_url, notes)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (code) DO UPDATE
        SET
            name = EXCLUDED.name,
            source_type = EXCLUDED.source_type,
            base_url = EXCLUDED.base_url,
            notes = EXCLUDED.notes,
            updated_at = NOW()
        RETURNING id
        """,
        (
            "finlab",
            "FinLab Python SDK",
            "python-sdk",
            "https://finlab.finance/docs/getting-started/",
            "Imported by ai-investment-analyst FinLab loader",
        ),
    )
    return _row_id(cur.fetchone())


def get_market_id(cur, market_code: str) -> str:
    cur.execute("SELECT id FROM markets WHERE code = %s", (market_code,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Market {market_code} not found. Did you run schema seed?")
    return _row_id(row)


def upsert_symbol(cur, market_id: str, spec: StockSpec) -> str:
    metadata = {"source": "FinLab"}
    cur.execute(
        """
        INSERT INTO symbols (
            market_id, ticker, name, local_name, instrument_type,
            exchange, currency_code, country_code, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (market_id, ticker) DO UPDATE
        SET
            name = EXCLUDED.name,
            local_name = EXCLUDED.local_name,
            instrument_type = EXCLUDED.instrument_type,
            exchange = EXCLUDED.exchange,
            currency_code = EXCLUDED.currency_code,
            country_code = EXCLUDED.country_code,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        RETURNING id
        """,
        (
            market_id,
            spec.stock_id,
            spec.stock_id,
            spec.stock_id,
            spec.instrument_type,
            "TWSE/TPEx",
            "TWD",
            "TW",
            json.dumps(metadata, ensure_ascii=False),
        ),
    )
    return _row_id(cur.fetchone())


def create_ingestion_run(cur, data_source_id: str, market_id: str, stock_ids: list[str]) -> str:
    cur.execute(
        """
        INSERT INTO ingestion_runs (
            data_source_id, run_type, target_table, market_id, status, context
        )
        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        RETURNING id
        """,
        (
            data_source_id,
            "manual-finlab-load",
            "symbols,price_daily",
            market_id,
            "running",
            json.dumps({"stock_ids": stock_ids}, ensure_ascii=False),
        ),
    )
    return _row_id(cur.fetchone())


def finalize_ingestion_run(
    cur,
    ingestion_run_id: str,
    *,
    status: str,
    records_received: int,
    records_inserted: int,
    records_updated: int,
    records_failed: int,
    error_message: str | None = None,
) -> None:
    cur.execute(
        """
        UPDATE ingestion_runs
        SET
            finished_at = NOW(),
            status = %s,
            records_received = %s,
            records_inserted = %s,
            records_updated = %s,
            records_failed = %s,
            error_message = %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            status,
            records_received,
            records_inserted,
            records_updated,
            records_failed,
            error_message,
            ingestion_run_id,
        ),
    )


def upsert_price_daily(cur, symbol_id: str, ingestion_run_id: str, trading_date, close_price, volume) -> None:
    turnover_value = close_price * Decimal(volume) if close_price is not None and volume is not None else None
    cur.execute(
        """
        INSERT INTO price_daily (
            symbol_id, trading_date, close_price, volume, turnover_value,
            ingestion_run_id, raw_payload
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (symbol_id, trading_date) DO UPDATE
        SET
            close_price = EXCLUDED.close_price,
            volume = EXCLUDED.volume,
            turnover_value = EXCLUDED.turnover_value,
            ingestion_run_id = EXCLUDED.ingestion_run_id,
            raw_payload = EXCLUDED.raw_payload,
            updated_at = NOW()
        """,
        (
            symbol_id,
            trading_date,
            close_price,
            volume,
            turnover_value,
            ingestion_run_id,
            json.dumps({"close_price": str(close_price) if close_price is not None else None, "volume": volume}, ensure_ascii=False),
        ),
    )


def load_finlab_price_data(
    stock_ids: tuple[str, ...] = DEFAULT_STOCK_IDS,
    lookback_rows: int = DEFAULT_LOOKBACK_ROWS,
) -> dict[str, Any]:
    ensure_finlab_login()

    close_df = data.get("price:收盤價")
    volume_df = data.get("price:成交股數")

    summary: dict[str, Any] = {"processed": [], "failed": []}

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            data_source_id = ensure_data_source(cur)
            market_id = get_market_id(cur, "TW")
            ingestion_run_id = create_ingestion_run(cur, data_source_id, market_id, list(stock_ids))
            conn.commit()

        try:
            with conn.cursor() as cur:
                for stock_id in stock_ids:
                    spec = StockSpec(stock_id=stock_id)
                    symbol_id = upsert_symbol(cur, market_id, spec)

                    stock_close = close_df[stock_id].dropna().tail(lookback_rows)
                    stock_volume = volume_df[stock_id].reindex(stock_close.index)

                    for trading_date, close_value in stock_close.items():
                        volume_value = stock_volume.loc[trading_date] if trading_date in stock_volume.index else None
                        upsert_price_daily(
                            cur,
                            symbol_id,
                            ingestion_run_id,
                            trading_date.date(),
                            decimal_or_none(close_value),
                            int_or_none(volume_value),
                        )

                    latest_date = stock_close.index[-1].date() if not stock_close.empty else None
                    latest_close = decimal_or_none(stock_close.iloc[-1]) if not stock_close.empty else None
                    summary["processed"].append(
                        {
                            "stock_id": stock_id,
                            "rows": len(stock_close),
                            "latest_date": latest_date.isoformat() if latest_date else None,
                            "latest_close": str(latest_close) if latest_close is not None else None,
                        }
                    )

                total_rows = sum(item["rows"] for item in summary["processed"])
                finalize_ingestion_run(
                    cur,
                    ingestion_run_id,
                    status="success",
                    records_received=total_rows,
                    records_inserted=total_rows,
                    records_updated=0,
                    records_failed=0,
                )
                conn.commit()
        except Exception as exc:
            with conn.cursor() as cur:
                total_rows = sum(item.get("rows", 0) for item in summary["processed"])
                finalize_ingestion_run(
                    cur,
                    ingestion_run_id,
                    status="failed",
                    records_received=total_rows,
                    records_inserted=total_rows,
                    records_updated=0,
                    records_failed=1,
                    error_message=str(exc),
                )
                conn.commit()
            raise

    return summary


if __name__ == "__main__":
    result = load_finlab_price_data()
    print(json.dumps(result, ensure_ascii=False, indent=2))
