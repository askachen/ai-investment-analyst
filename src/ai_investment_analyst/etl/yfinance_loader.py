from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import yfinance as yf
from psycopg.rows import dict_row

from ai_investment_analyst.db.connection import get_connection
from ai_investment_analyst.db.price_store import refresh_price_daily_canonical, upsert_price_daily_raw

DEFAULT_TICKERS: tuple[str, ...] = (
    "^TWII",
    "^IXIC",
    "^DJI",
    "2454.TW",
    "2330.TW",
)


@dataclass(frozen=True)
class TickerSpec:
    ticker: str
    market_code: str
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


def infer_market_code(ticker: str) -> str:
    return "TW" if ticker.endswith(".TW") or ticker == "^TWII" else "US"


def infer_instrument_type(ticker: str) -> str:
    return "index" if ticker.startswith("^") else "stock"


def _row_id(row: Any) -> str:
    if isinstance(row, dict):
        return row["id"]
    return row[0]


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
            "yfinance",
            "Yahoo Finance via yfinance",
            "api-wrapper",
            "https://finance.yahoo.com",
            "Imported by ai-investment-analyst yfinance loader",
        ),
    )
    return _row_id(cur.fetchone())


def get_market_id(cur, market_code: str) -> str:
    cur.execute("SELECT id FROM markets WHERE code = %s", (market_code,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Market {market_code} not found. Did you run schema seed?")
    return _row_id(row)


def upsert_symbol(cur, market_id: str, spec: TickerSpec, info: dict[str, Any]) -> str:
    name = info.get("shortName") or info.get("longName") or spec.ticker
    local_name = info.get("longName") if spec.market_code == "TW" else None
    exchange = info.get("exchange") or info.get("fullExchangeName")
    sector = info.get("sector")
    industry = info.get("industry")
    currency_code = info.get("currency")
    country_code = info.get("country")
    metadata = {
        "quoteType": info.get("quoteType"),
        "market": info.get("market"),
        "exchange": exchange,
    }

    cur.execute(
        """
        INSERT INTO symbols (
            market_id, ticker, name, local_name, instrument_type,
            exchange, sector, industry, currency_code, country_code, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (market_id, ticker) DO UPDATE
        SET
            name = EXCLUDED.name,
            local_name = EXCLUDED.local_name,
            instrument_type = EXCLUDED.instrument_type,
            exchange = EXCLUDED.exchange,
            sector = EXCLUDED.sector,
            industry = EXCLUDED.industry,
            currency_code = EXCLUDED.currency_code,
            country_code = EXCLUDED.country_code,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        RETURNING id
        """,
        (
            market_id,
            spec.ticker,
            name,
            local_name,
            spec.instrument_type,
            exchange,
            sector,
            industry,
            currency_code,
            country_code,
            json.dumps(metadata, ensure_ascii=False),
        ),
    )
    return _row_id(cur.fetchone())


def create_ingestion_run(cur, data_source_id: str, market_id: str, tickers: list[str]) -> str:
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
            "manual-yfinance-load",
            "price_daily_raw,price_daily_canonical",
            market_id,
            "running",
            json.dumps({"tickers": tickers}, ensure_ascii=False),
        ),
    )
    return _row_id(cur.fetchone())


def finalize_ingestion_run(cur, ingestion_run_id: str, *, status: str, records_received: int, records_inserted: int, records_updated: int, records_failed: int, error_message: str | None = None) -> None:
    cur.execute(
        """
        UPDATE ingestion_runs
        SET finished_at = NOW(), status = %s, records_received = %s, records_inserted = %s,
            records_updated = %s, records_failed = %s, error_message = %s, updated_at = NOW()
        WHERE id = %s
        """,
        (status, records_received, records_inserted, records_updated, records_failed, error_message, ingestion_run_id),
    )


def store_price_row(cur, *, symbol_id: str, data_source_id: str, ingestion_run_id: str, trading_date: date, row: dict[str, Any]) -> None:
    open_price = decimal_or_none(row.get("Open"))
    high_price = decimal_or_none(row.get("High"))
    low_price = decimal_or_none(row.get("Low"))
    close_price = decimal_or_none(row.get("Close"))
    adjusted_close = decimal_or_none(row.get("Adj Close"))
    volume = int_or_none(row.get("Volume"))
    price_change = None
    change_percent = None
    if open_price is not None and close_price is not None:
        price_change = close_price - open_price
        if open_price != 0:
            change_percent = (price_change / open_price) * Decimal("100")
    turnover_value = close_price * Decimal(volume) if close_price is not None and volume is not None else None

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
        adjusted_close=adjusted_close,
        price_change=price_change,
        change_percent=change_percent,
        volume=volume,
        turnover_value=turnover_value,
        trade_count=None,
        raw_payload=row,
    )
    refresh_price_daily_canonical(cur, symbol_id=symbol_id, trading_date=trading_date)


def load_latest_prices(tickers: tuple[str, ...] = DEFAULT_TICKERS) -> dict[str, Any]:
    summary: dict[str, Any] = {"processed": [], "failed": []}
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            data_source_id = ensure_data_source(cur)
            market_ids = {code: get_market_id(cur, code) for code in {infer_market_code(t) for t in tickers}}
            ingestion_runs = {code: create_ingestion_run(cur, data_source_id, market_ids[code], [ticker for ticker in tickers if infer_market_code(ticker) == code]) for code in market_ids}
            conn.commit()
        try:
            with conn.cursor() as cur:
                for ticker in tickers:
                    spec = TickerSpec(ticker=ticker, market_code=infer_market_code(ticker), instrument_type=infer_instrument_type(ticker))
                    yf_ticker = yf.Ticker(ticker)
                    info = yf_ticker.info or {}
                    history = yf_ticker.history(period="5d", interval="1d", auto_adjust=False)
                    if history.empty:
                        raise ValueError(f"No history returned for {ticker}")
                    latest = history.tail(1)
                    trading_date = latest.index[0].date()
                    latest_row = latest.iloc[0].to_dict()
                    market_id = market_ids[spec.market_code]
                    ingestion_run_id = ingestion_runs[spec.market_code]
                    symbol_id = upsert_symbol(cur, market_id, spec, info)
                    store_price_row(cur, symbol_id=symbol_id, data_source_id=data_source_id, ingestion_run_id=ingestion_run_id, trading_date=trading_date, row=latest_row)
                    summary["processed"].append({"ticker": ticker, "market": spec.market_code, "trading_date": trading_date.isoformat(), "close": str(decimal_or_none(latest_row.get("Close")))})
                for market_code, ingestion_run_id in ingestion_runs.items():
                    count = len([item for item in summary["processed"] if item["market"] == market_code])
                    finalize_ingestion_run(cur, ingestion_run_id, status="success", records_received=count, records_inserted=count, records_updated=0, records_failed=0)
                conn.commit()
        except Exception as exc:
            with conn.cursor() as cur:
                for market_code, ingestion_run_id in ingestion_runs.items():
                    processed_count = len([item for item in summary["processed"] if item["market"] == market_code])
                    finalize_ingestion_run(cur, ingestion_run_id, status="failed", records_received=processed_count, records_inserted=processed_count, records_updated=0, records_failed=1, error_message=str(exc))
                conn.commit()
            raise
    return summary


if __name__ == "__main__":
    result = load_latest_prices()
    print(json.dumps(result, ensure_ascii=False, indent=2))
