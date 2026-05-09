from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Sequence

from ai_investment_analyst.analysis.daily_screener import DailyScreeningSnapshot, generate_all_daily_screenings
from ai_investment_analyst.analysis.stock_report import load_stock_report_context
from ai_investment_analyst.config import settings
from ai_investment_analyst.db.connection import get_connection
from ai_investment_analyst.etl.finmind_financial_loader import load_financial_statements
from ai_investment_analyst.etl.finmind_monthly_revenue_loader import load_monthly_revenue
from ai_investment_analyst.etl.twse_tpex_loader import DEFAULT_START_DATE, load_twse_tpex_stock_price, sync_official_taiwan_stock_universe

REQUIRED_SCHEMA_TABLES = (
    'markets',
    'symbols',
    'price_daily_canonical',
    'monthly_revenues',
    'financial_statement_items',
    'screening_runs',
    'screening_results',
)

PACKAGE_DIR = Path(__file__).resolve().parents[1]
SQL_DIR = PACKAGE_DIR / "sql"
BASE_SCHEMA_SQL = SQL_DIR / "ai_investment_analyst_db" / "001_initial_schema.sql"
MARKET_SEED_SQL = SQL_DIR / "ai_investment_analyst_db" / "002_seed_markets.sql"
PRICE_SCHEMA_SQL = SQL_DIR / "multi_source_price_strategy" / "003_multi_source_price.sql"
REVENUE_SCHEMA_SQL = SQL_DIR / "stock_analysis_report" / "004_monthly_revenue.sql"
FINANCIAL_SCHEMA_SQL = SQL_DIR / "stock_analysis_report" / "005_financial_statement_items.sql"
SCREENER_SCHEMA_SQL = SQL_DIR / "stock_analysis_report" / "006_daily_screener.sql"


@dataclass(frozen=True)
class DailyScreenerJobResult:
    tickers: list[str]
    source_refresh: dict[str, Any]
    snapshots: list[DailyScreeningSnapshot]


def _run_sql_file(path: Path) -> None:
    try:
        sql = path.read_text(encoding="utf-8")
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(sql)
            conn.commit()
    except Exception as exc:
        raise RuntimeError(f"Failed to apply schema SQL: {path}") from exc


def apply_base_schema() -> None:
    _run_sql_file(BASE_SCHEMA_SQL)


def apply_market_seed() -> None:
    _run_sql_file(MARKET_SEED_SQL)


def apply_price_schema() -> None:
    _run_sql_file(PRICE_SCHEMA_SQL)


def apply_revenue_schema() -> None:
    _run_sql_file(REVENUE_SCHEMA_SQL)


def apply_financial_schema() -> None:
    _run_sql_file(FINANCIAL_SCHEMA_SQL)


def apply_screener_schema() -> None:
    _run_sql_file(SCREENER_SCHEMA_SQL)


def _missing_source_data_market_fallback(_: str):
    raise RuntimeError(
        "official daily screener refresh requires DB-backed source data; market fallback is disabled for this job"
    )


def _schema_ready() -> bool:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            '''
            select table_name
            from information_schema.tables
            where table_schema = 'public'
              and table_name = any(%s)
            ''',
            (list(REQUIRED_SCHEMA_TABLES),),
        )
        found = {row[0] for row in cur.fetchall()}
    return all(table_name in found for table_name in REQUIRED_SCHEMA_TABLES)


def _ensure_schema(
    *,
    base_schema_applier: Callable[[], None],
    market_seed_applier: Callable[[], None],
    price_schema_applier: Callable[[], None],
    revenue_schema_applier: Callable[[], None],
    financial_schema_applier: Callable[[], None],
    screener_schema_applier: Callable[[], None],
) -> None:
    if _schema_ready():
        return
    base_schema_applier()
    market_seed_applier()
    price_schema_applier()
    revenue_schema_applier()
    financial_schema_applier()
    screener_schema_applier()


def _price_refresh_start_date(tickers: Sequence[str], fallback_start_date: str = DEFAULT_START_DATE) -> str:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            '''
            select max(pdc.trading_date)
            from price_daily_canonical pdc
            join symbols s on s.id = pdc.symbol_id
            where s.ticker = any(%s)
            ''',
            (list(tickers),),
        )
        latest_date = cur.fetchone()[0]
    if latest_date is None:
        return fallback_start_date
    return max((latest_date - timedelta(days=14)).isoformat(), fallback_start_date)


def run_daily_screener_job(
    tickers: Sequence[str] | None = None,
    *,
    base_schema_applier: Callable[[], None] = apply_base_schema,
    market_seed_applier: Callable[[], None] = apply_market_seed,
    price_schema_applier: Callable[[], None] = apply_price_schema,
    revenue_schema_applier: Callable[[], None] = apply_revenue_schema,
    financial_schema_applier: Callable[[], None] = apply_financial_schema,
    screener_schema_applier: Callable[[], None] = apply_screener_schema,
    universe_loader: Callable[[], list[str]] = sync_official_taiwan_stock_universe,
    price_loader: Callable[..., Any] = load_twse_tpex_stock_price,
    revenue_loader: Callable[..., Any] = load_monthly_revenue,
    financial_loader: Callable[..., Any] = load_financial_statements,
    screener_generator: Callable[..., list[DailyScreeningSnapshot]] = generate_all_daily_screenings,
) -> DailyScreenerJobResult:
    full_universe_refresh = False
    if tickers is None:
        if settings.screening_tickers_overridden:
            selected_tickers = [ticker.upper() for ticker in settings.screening_tickers]
        else:
            selected_tickers = [ticker.upper() for ticker in universe_loader()]
            full_universe_refresh = True
    else:
        selected_tickers = [ticker.upper() for ticker in tickers]
    if not selected_tickers:
        raise ValueError("tickers must not be empty")

    _ensure_schema(
        base_schema_applier=base_schema_applier,
        market_seed_applier=market_seed_applier,
        price_schema_applier=price_schema_applier,
        revenue_schema_applier=revenue_schema_applier,
        financial_schema_applier=financial_schema_applier,
        screener_schema_applier=screener_schema_applier,
    )

    price_start_date = _price_refresh_start_date(selected_tickers)
    source_refresh = {
        "price": price_loader(stock_ids=tuple(selected_tickers), start_date=price_start_date),
    }
    if full_universe_refresh:
        skipped_summary = {"skipped": True, "reason": "full_universe_daily_refresh_uses_existing_fundamentals"}
        source_refresh["revenue"] = skipped_summary
        source_refresh["financial"] = skipped_summary
    else:
        source_refresh["revenue"] = revenue_loader(stock_ids=tuple(selected_tickers))
        source_refresh["financial"] = financial_loader(stock_ids=tuple(selected_tickers))
    snapshots = screener_generator(
        ticker_loader=lambda: list(selected_tickers),
        context_loader=load_stock_report_context,
        market_context_loader=_missing_source_data_market_fallback,
    )
    return DailyScreenerJobResult(
        tickers=list(selected_tickers),
        source_refresh=source_refresh,
        snapshots=snapshots,
    )
