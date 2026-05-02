import pytest

from ai_investment_analyst.analysis.stock_report import load_stock_report_context


def test_run_daily_screener_job_bootstraps_source_data_before_strict_snapshots():
    from ai_investment_analyst.analysis.daily_screener_job import run_daily_screener_job

    calls = []
    captured = {}
    snapshots = [object()]

    def mark(name, payload=None):
        calls.append((name, payload))

    result = run_daily_screener_job(
        tickers=("2330", "2454", "2881"),
        base_schema_applier=lambda: mark("base_schema"),
        market_seed_applier=lambda: mark("market_seed"),
        price_schema_applier=lambda: mark("price_schema"),
        revenue_schema_applier=lambda: mark("revenue_schema"),
        financial_schema_applier=lambda: mark("financial_schema"),
        screener_schema_applier=lambda: mark("screener_schema"),
        price_loader=lambda stock_ids: mark("price_loader", tuple(stock_ids)) or {"dataset": "price"},
        revenue_loader=lambda stock_ids: mark("revenue_loader", tuple(stock_ids)) or {"dataset": "revenue"},
        financial_loader=lambda stock_ids: mark("financial_loader", tuple(stock_ids)) or {"dataset": "financial"},
        screener_generator=lambda **kwargs: captured.update(kwargs) or mark("screener_generator", tuple(kwargs["ticker_loader"]())) or snapshots,
    )

    assert [name for name, _ in calls] == [
        "base_schema",
        "market_seed",
        "price_schema",
        "revenue_schema",
        "financial_schema",
        "screener_schema",
        "price_loader",
        "revenue_loader",
        "financial_loader",
        "screener_generator",
    ]
    assert calls[6][1] == ("2330", "2454", "2881")
    assert calls[7][1] == ("2330", "2454", "2881")
    assert calls[8][1] == ("2330", "2454", "2881")
    assert captured["ticker_loader"]() == ["2330", "2454", "2881"]
    assert captured["context_loader"] is load_stock_report_context
    with pytest.raises(RuntimeError, match="official daily screener refresh requires DB-backed source data"):
        captured["market_context_loader"]("2330")
    assert result.tickers == ["2330", "2454", "2881"]
    assert result.source_refresh["price"] == {"dataset": "price"}
    assert result.source_refresh["revenue"] == {"dataset": "revenue"}
    assert result.source_refresh["financial"] == {"dataset": "financial"}
    assert result.snapshots == snapshots


def test_run_daily_screener_job_rejects_empty_ticker_input_instead_of_falling_back_to_defaults():
    from ai_investment_analyst.analysis.daily_screener_job import run_daily_screener_job

    with pytest.raises(ValueError, match="tickers must not be empty"):
        run_daily_screener_job(
            tickers=(),
            base_schema_applier=lambda: None,
            market_seed_applier=lambda: None,
            price_schema_applier=lambda: None,
            revenue_schema_applier=lambda: None,
            financial_schema_applier=lambda: None,
            screener_schema_applier=lambda: None,
            price_loader=lambda stock_ids: {"dataset": "price"},
            revenue_loader=lambda stock_ids: {"dataset": "revenue"},
            financial_loader=lambda stock_ids: {"dataset": "financial"},
            screener_generator=lambda **kwargs: [],
        )


def test_sql_resources_live_inside_the_package_directory():
    from pathlib import Path

    from ai_investment_analyst.analysis import daily_screener_job

    package_root = Path(daily_screener_job.__file__).resolve().parents[1]
    for sql_path in [
        daily_screener_job.BASE_SCHEMA_SQL,
        daily_screener_job.MARKET_SEED_SQL,
        daily_screener_job.PRICE_SCHEMA_SQL,
        daily_screener_job.REVENUE_SCHEMA_SQL,
        daily_screener_job.FINANCIAL_SCHEMA_SQL,
        daily_screener_job.SCREENER_SCHEMA_SQL,
    ]:
        assert Path(sql_path).resolve().is_relative_to(package_root)



def test_run_sql_file_wraps_file_and_db_failures_with_context(tmp_path):
    from ai_investment_analyst.analysis.daily_screener_job import _run_sql_file

    missing_path = tmp_path / "missing.sql"
    with pytest.raises(RuntimeError, match="Failed to apply schema SQL: .*missing.sql"):
        _run_sql_file(missing_path)



def test_run_daily_screener_job_fails_closed_before_snapshot_generation_when_source_refresh_breaks():
    from ai_investment_analyst.analysis.daily_screener_job import run_daily_screener_job

    calls = []

    with pytest.raises(RuntimeError, match="FinMind monthly revenue unavailable"):
        run_daily_screener_job(
            tickers=("2330",),
            base_schema_applier=lambda: calls.append("base_schema"),
            market_seed_applier=lambda: calls.append("market_seed"),
            price_schema_applier=lambda: calls.append("price_schema"),
            revenue_schema_applier=lambda: calls.append("revenue_schema"),
            financial_schema_applier=lambda: calls.append("financial_schema"),
            screener_schema_applier=lambda: calls.append("screener_schema"),
            price_loader=lambda stock_ids: calls.append("price_loader") or {"dataset": "price"},
            revenue_loader=lambda stock_ids: (_ for _ in ()).throw(RuntimeError("FinMind monthly revenue unavailable")),
            financial_loader=lambda stock_ids: calls.append("financial_loader") or {"dataset": "financial"},
            screener_generator=lambda **kwargs: calls.append("screener_generator") or [],
        )

    assert calls == [
        "base_schema",
        "market_seed",
        "price_schema",
        "revenue_schema",
        "financial_schema",
        "screener_schema",
        "price_loader",
    ]
