from __future__ import annotations

import json
import re
import ssl
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from typing import Any, Iterable

import requests
from psycopg.rows import dict_row
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

from ai_investment_analyst.db.connection import get_connection
from ai_investment_analyst.db.price_store import refresh_price_daily_canonical, upsert_price_daily_raw

TWSE_BASE_URL = "https://www.twse.com.tw"
TPEX_BASE_URL = "https://www.tpex.org.tw"
TWSE_LISTED_COMPANIES_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_LISTED_COMPANIES_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
DEFAULT_START_DATE = "2026-04-01"


class _OfficialDataTLSAdapter(HTTPAdapter):
    """HTTPS adapter for Taiwan official data endpoints.

    Python 3.13/OpenSSL can reject the TWSE OpenAPI certificate chain with
    ``Missing Subject Key Identifier`` when strict X.509 verification is on.
    Keep normal CA/hostname verification enabled, but disable only the extra
    OpenSSL strict flag for these official public-data hosts.
    """

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):  # type: ignore[override]
        context = ssl.create_default_context()
        if hasattr(ssl, "VERIFY_X509_STRICT"):
            context.verify_flags &= ~ssl.VERIFY_X509_STRICT
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=context,
            **pool_kwargs,
        )


@lru_cache(maxsize=1)
def _official_requests_session() -> requests.Session:
    session = requests.Session()
    adapter = _OfficialDataTLSAdapter()
    session.mount("https://openapi.twse.com.tw", adapter)
    session.mount(TWSE_BASE_URL, adapter)
    session.mount(TPEX_BASE_URL, adapter)
    return session


def _official_get(url: str, **kwargs) -> requests.Response:
    return _official_requests_session().get(url, **kwargs)


@dataclass(frozen=True)
class StockSpec:
    stock_id: str
    market_code: str = "TW"
    instrument_type: str = "stock"
    exchange: str = "TWSE/TPEx"


def _row_id(row: Any) -> str:
    if isinstance(row, dict):
        return row["id"]
    return row[0]


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _is_common_stock_code(value: Any) -> bool:
    code = _clean_text(value).upper()
    return len(code) == 4 and code.isdigit()


def decimal_or_none(value: Any) -> Decimal | None:
    text = _clean_text(value).replace(",", "")
    if text in {"", "--", "---", "X", "x", "N/A", "nan"}:
        return None
    try:
        return Decimal(text)
    except Exception:
        return None


def int_or_none(value: Any) -> int | None:
    text = _clean_text(value).replace(",", "")
    if text in {"", "--", "---", "X", "x", "N/A", "nan"}:
        return None
    try:
        return int(Decimal(text))
    except Exception:
        return None


def _signed_decimal(value: Any) -> Decimal | None:
    text = re.sub(r"<[^>]*>", "", _clean_text(value)).replace(",", "")
    text = text.replace("＋", "+").replace("－", "-").strip()
    if text in {"", "--", "---", "X", "x", "N/A"}:
        return None
    if text.startswith("+"):
        text = text[1:]
    try:
        return Decimal(text)
    except Exception:
        return None


def fetch_twse_listed_company_rows() -> list[dict[str, Any]]:
    response = _official_get(TWSE_LISTED_COMPANIES_URL, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_tpex_listed_company_rows() -> list[dict[str, Any]]:
    response = _official_get(TPEX_LISTED_COMPANIES_URL, timeout=30)
    response.raise_for_status()
    return response.json()


def build_official_stock_info_rows(
    twse_rows: Iterable[dict[str, Any]],
    tpex_rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in twse_rows:
        stock_id = _clean_text(row.get("公司代號"))
        if not _is_common_stock_code(stock_id):
            continue
        rows.append(
            {
                "stock_id": stock_id,
                "stock_name": _clean_text(row.get("公司簡稱") or row.get("公司名稱") or stock_id),
                "industry_category": _clean_text(row.get("產業別")) or None,
                "type": "twse",
                "exchange": "TWSE",
            }
        )
    for row in tpex_rows:
        stock_id = _clean_text(row.get("SecuritiesCompanyCode"))
        if not _is_common_stock_code(stock_id):
            continue
        rows.append(
            {
                "stock_id": stock_id,
                "stock_name": _clean_text(row.get("CompanyAbbreviation") or row.get("CompanyName") or stock_id),
                "industry_category": _clean_text(row.get("SecuritiesIndustryCode")) or None,
                "type": "tpex",
                "exchange": "TPEx",
            }
        )
    deduped = {row["stock_id"]: row for row in rows}
    return [deduped[key] for key in sorted(deduped)]


def fetch_official_taiwan_stock_universe_rows() -> list[dict[str, Any]]:
    return build_official_stock_info_rows(fetch_twse_listed_company_rows(), fetch_tpex_listed_company_rows())


def ensure_data_source(cur, *, code: str = "twse-tpex", name: str = "TWSE/TPEx official public data", base_url: str = "https://www.twse.com.tw; https://www.tpex.org.tw") -> str:
    cur.execute(
        """
        INSERT INTO data_sources (code, name, source_type, base_url, notes)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (code) DO UPDATE
        SET name = EXCLUDED.name, source_type = EXCLUDED.source_type, base_url = EXCLUDED.base_url, notes = EXCLUDED.notes, updated_at = NOW()
        RETURNING id
        """,
        (code, name, "public-rest-api", base_url, "Imported by ai-investment-analyst official TWSE/TPEx loader"),
    )
    return _row_id(cur.fetchone())


def get_market_id(cur, market_code: str) -> str:
    cur.execute("SELECT id FROM markets WHERE code = %s", (market_code,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Market {market_code} not found. Did you run schema seed?")
    return _row_id(row)


def create_ingestion_run(cur, data_source_id: str, market_id: str, stock_ids: list[str], start_date: str) -> str:
    cur.execute(
        """
        INSERT INTO ingestion_runs (data_source_id, run_type, target_table, market_id, status, context)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        RETURNING id
        """,
        (
            data_source_id,
            "official-twse-tpex-load",
            "symbols,price_daily_raw,price_daily_canonical",
            market_id,
            "running",
            json.dumps({"stock_ids": stock_ids, "start_date": start_date}, ensure_ascii=False),
        ),
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


def upsert_symbol(cur, market_id: str, spec: StockSpec, info: dict[str, Any]) -> str:
    exchange = info.get("exchange") or spec.exchange
    metadata = {"industry_category": info.get("industry_category"), "type": info.get("type"), "source": "TWSE/TPEx official"}
    cur.execute(
        """
        INSERT INTO symbols (market_id, ticker, name, local_name, instrument_type, exchange, sector, industry, currency_code, country_code, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (market_id, ticker) DO UPDATE
        SET name = EXCLUDED.name, local_name = EXCLUDED.local_name, instrument_type = EXCLUDED.instrument_type,
            exchange = EXCLUDED.exchange, sector = EXCLUDED.sector, industry = EXCLUDED.industry,
            currency_code = EXCLUDED.currency_code, country_code = EXCLUDED.country_code, metadata = EXCLUDED.metadata,
            is_active = TRUE, updated_at = NOW()
        RETURNING id
        """,
        (
            market_id,
            spec.stock_id,
            info.get("stock_name") or spec.stock_id,
            info.get("stock_name") or spec.stock_id,
            spec.instrument_type,
            exchange,
            info.get("industry_category"),
            info.get("industry_category"),
            "TWD",
            "TW",
            json.dumps(metadata, ensure_ascii=False),
        ),
    )
    return _row_id(cur.fetchone())


def sync_official_taiwan_stock_universe(
    ensure_data_source_fn=None,
    get_market_id_fn=None,
    create_ingestion_run_fn=None,
    upsert_symbol_fn=None,
    finalize_ingestion_run_fn=None,
    connection_factory=get_connection,
) -> list[str]:
    ensure_data_source_fn = ensure_data_source_fn or ensure_data_source
    get_market_id_fn = get_market_id_fn or get_market_id
    create_ingestion_run_fn = create_ingestion_run_fn or create_ingestion_run
    upsert_symbol_fn = upsert_symbol_fn or upsert_symbol
    finalize_ingestion_run_fn = finalize_ingestion_run_fn or finalize_ingestion_run
    stock_info_rows = fetch_official_taiwan_stock_universe_rows()
    tickers = [row["stock_id"] for row in stock_info_rows]
    with connection_factory() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            data_source_id = ensure_data_source_fn(cur)
            market_id = get_market_id_fn(cur, "TW")
            ingestion_run_id = create_ingestion_run_fn(cur, data_source_id, market_id, tickers, "official-universe-sync")
            conn.commit()
        try:
            with conn.cursor() as cur:
                for row in stock_info_rows:
                    spec = StockSpec(stock_id=row["stock_id"], exchange=row.get("exchange") or "TWSE/TPEx")
                    upsert_symbol_fn(cur, market_id, spec, row)
                finalize_ingestion_run_fn(cur, ingestion_run_id, status="success", records_received=len(tickers), records_inserted=len(tickers), records_updated=0, records_failed=0)
                conn.commit()
        except Exception as exc:
            with conn.cursor() as cur:
                finalize_ingestion_run_fn(cur, ingestion_run_id, status="failed", records_received=len(tickers), records_inserted=0, records_updated=0, records_failed=1, error_message=str(exc))
                conn.commit()
            raise
    return tickers


def _table_dicts(payload: dict[str, Any], title_keyword: str) -> Iterable[dict[str, Any]]:
    for table in payload.get("tables") or []:
        if title_keyword and title_keyword not in _clean_text(table.get("title")):
            continue
        fields = table.get("fields") or []
        for row in table.get("data") or []:
            yield dict(zip(fields, row))


def parse_twse_daily_price_rows(payload: dict[str, Any], *, trading_date: date, stock_ids: set[str]) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for row in _table_dicts(payload, "每日收盤行情"):
        stock_id = _clean_text(row.get("證券代號")).upper()
        if stock_id not in stock_ids or not _is_common_stock_code(stock_id):
            continue
        close_price = decimal_or_none(row.get("收盤價"))
        if close_price is None:
            continue
        parsed.append(
            {
                "date": trading_date.isoformat(),
                "stock_id": stock_id,
                "stock_name": _clean_text(row.get("證券名稱") or stock_id),
                "exchange": "TWSE",
                "open": decimal_or_none(row.get("開盤價")),
                "max": decimal_or_none(row.get("最高價")),
                "min": decimal_or_none(row.get("最低價")),
                "close": close_price,
                "spread": _signed_decimal(row.get("漲跌價差")),
                "Trading_Volume": int_or_none(row.get("成交股數")),
                "Trading_money": decimal_or_none(row.get("成交金額")),
                "Trading_turnover": int_or_none(row.get("成交筆數")),
            }
        )
    return parsed


def parse_tpex_daily_price_rows(payload: dict[str, Any], *, trading_date: date, stock_ids: set[str]) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for row in _table_dicts(payload, "上櫃股票行情"):
        stock_id = _clean_text(row.get("代號")).upper()
        if stock_id not in stock_ids or not _is_common_stock_code(stock_id):
            continue
        close_price = decimal_or_none(row.get("收盤"))
        if close_price is None:
            continue
        parsed.append(
            {
                "date": trading_date.isoformat(),
                "stock_id": stock_id,
                "stock_name": _clean_text(row.get("名稱") or stock_id),
                "exchange": "TPEx",
                "open": decimal_or_none(row.get("開盤")),
                "max": decimal_or_none(row.get("最高")),
                "min": decimal_or_none(row.get("最低")),
                "close": close_price,
                "spread": _signed_decimal(row.get("漲跌")),
                "Trading_Volume": int_or_none(row.get("成交股數")),
                "Trading_money": decimal_or_none(row.get("成交金額(元)")),
                "Trading_turnover": int_or_none(row.get("成交筆數")),
            }
        )
    return parsed


def _twse_date(value: date) -> str:
    return value.strftime("%Y%m%d")


def _tpex_roc_date(value: date) -> str:
    return f"{value.year - 1911}/{value.month:02d}/{value.day:02d}"


def fetch_twse_daily_price_rows(trading_date: date, stock_ids: set[str]) -> list[dict[str, Any]]:
    response = _official_get(
        f"{TWSE_BASE_URL}/exchangeReport/MI_INDEX",
        params={"response": "json", "date": _twse_date(trading_date), "type": "ALLBUT0999"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return parse_twse_daily_price_rows(payload, trading_date=trading_date, stock_ids=stock_ids)


def fetch_tpex_daily_price_rows(trading_date: date, stock_ids: set[str]) -> list[dict[str, Any]]:
    response = _official_get(
        f"{TPEX_BASE_URL}/www/zh-tw/afterTrading/dailyQuotes",
        params={"date": _tpex_roc_date(trading_date), "type": "EW", "response": "json"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return parse_tpex_daily_price_rows(payload, trading_date=trading_date, stock_ids=stock_ids)


def iter_trading_dates(start_date: str, end_date: date | None = None) -> list[date]:
    current = datetime.strptime(start_date, "%Y-%m-%d").date()
    final = end_date or date.today()
    dates: list[date] = []
    while current <= final:
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    return dates


def store_price_row(cur, *, symbol_id: str, data_source_id: str, ingestion_run_id: str, row: dict[str, Any]) -> None:
    trading_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
    open_price = decimal_or_none(row.get("open"))
    close_price = decimal_or_none(row.get("close"))
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
        high_price=decimal_or_none(row.get("max")),
        low_price=decimal_or_none(row.get("min")),
        close_price=close_price,
        adjusted_close=None,
        price_change=decimal_or_none(row.get("spread")),
        change_percent=change_percent,
        volume=int_or_none(row.get("Trading_Volume")),
        turnover_value=decimal_or_none(row.get("Trading_money")),
        trade_count=int_or_none(row.get("Trading_turnover")),
        raw_payload=row,
    )
    refresh_price_daily_canonical(cur, symbol_id=symbol_id, trading_date=trading_date)


def load_twse_tpex_stock_price(
    stock_ids: tuple[str, ...],
    start_date: str = DEFAULT_START_DATE,
    *,
    end_date: date | None = None,
    twse_fetcher=fetch_twse_daily_price_rows,
    tpex_fetcher=fetch_tpex_daily_price_rows,
) -> dict[str, Any]:
    selected_stock_ids = tuple(sorted({_clean_text(stock_id).upper() for stock_id in stock_ids if _clean_text(stock_id)}))
    if not selected_stock_ids:
        raise ValueError("stock_ids must not be empty")

    summary: dict[str, Any] = {"processed": [], "failed": [], "source": "twse-tpex"}
    rows_by_stock: dict[str, list[dict[str, Any]]] = {stock_id: [] for stock_id in selected_stock_ids}
    requested_set = set(selected_stock_ids)
    trading_dates = iter_trading_dates(start_date, end_date=end_date)

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            twse_data_source_id = ensure_data_source(cur, code="twse", name="Taiwan Stock Exchange", base_url=TWSE_BASE_URL)
            tpex_data_source_id = ensure_data_source(cur, code="tpex", name="Taipei Exchange", base_url=TPEX_BASE_URL)
            market_id = get_market_id(cur, "TW")
            twse_ingestion_run_id = create_ingestion_run(cur, twse_data_source_id, market_id, list(selected_stock_ids), start_date)
            tpex_ingestion_run_id = create_ingestion_run(cur, tpex_data_source_id, market_id, list(selected_stock_ids), start_date)
            conn.commit()
        try:
            with conn.cursor() as cur:
                for trading_date in trading_dates:
                    for row in twse_fetcher(trading_date, requested_set):
                        info = {
                            "stock_id": row["stock_id"],
                            "stock_name": row.get("stock_name") or row["stock_id"],
                            "exchange": "TWSE",
                            "type": "twse",
                        }
                        symbol_id = upsert_symbol(cur, market_id, StockSpec(stock_id=row["stock_id"], exchange="TWSE"), info)
                        store_price_row(cur, symbol_id=symbol_id, data_source_id=twse_data_source_id, ingestion_run_id=twse_ingestion_run_id, row=row)
                        rows_by_stock[row["stock_id"]].append(row)
                    for row in tpex_fetcher(trading_date, requested_set):
                        info = {
                            "stock_id": row["stock_id"],
                            "stock_name": row.get("stock_name") or row["stock_id"],
                            "exchange": "TPEx",
                            "type": "tpex",
                        }
                        symbol_id = upsert_symbol(cur, market_id, StockSpec(stock_id=row["stock_id"], exchange="TPEx"), info)
                        store_price_row(cur, symbol_id=symbol_id, data_source_id=tpex_data_source_id, ingestion_run_id=tpex_ingestion_run_id, row=row)
                        rows_by_stock[row["stock_id"]].append(row)
                total_rows = sum(len(rows) for rows in rows_by_stock.values())
                finalize_ingestion_run(cur, twse_ingestion_run_id, status="success", records_received=total_rows, records_inserted=total_rows, records_updated=0, records_failed=0)
                finalize_ingestion_run(cur, tpex_ingestion_run_id, status="success", records_received=total_rows, records_inserted=total_rows, records_updated=0, records_failed=0)
                conn.commit()
        except Exception as exc:
            with conn.cursor() as cur:
                total_rows = sum(len(rows) for rows in rows_by_stock.values())
                finalize_ingestion_run(cur, twse_ingestion_run_id, status="failed", records_received=total_rows, records_inserted=total_rows, records_updated=0, records_failed=1, error_message=str(exc))
                finalize_ingestion_run(cur, tpex_ingestion_run_id, status="failed", records_received=total_rows, records_inserted=total_rows, records_updated=0, records_failed=1, error_message=str(exc))
                conn.commit()
            raise

    for stock_id, rows in rows_by_stock.items():
        rows.sort(key=lambda row: row["date"])
        latest_row = rows[-1] if rows else None
        summary["processed"].append(
            {
                "stock_id": stock_id,
                "rows": len(rows),
                "latest_date": latest_row.get("date") if latest_row else None,
                "latest_close": str(decimal_or_none(latest_row.get("close"))) if latest_row else None,
            }
        )
    return summary


if __name__ == "__main__":
    print(json.dumps(load_twse_tpex_stock_price(("2330", "6488")), ensure_ascii=False, indent=2))
