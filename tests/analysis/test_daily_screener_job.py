from types import SimpleNamespace

import pytest

from ai_investment_analyst.analysis.stock_report import load_stock_report_context


def test_run_daily_screener_job_uses_official_universe_and_price_loader_defaults():
    from ai_investment_analyst.analysis import daily_screener_job

    assert daily_screener_job.run_daily_screener_job.__kwdefaults__["universe_loader"] is daily_screener_job.sync_official_taiwan_stock_universe
    assert daily_screener_job.run_daily_screener_job.__kwdefaults__["price_loader"] is daily_screener_job.load_twse_tpex_stock_price


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
        price_loader=lambda stock_ids, start_date=None: mark("price_loader", (tuple(stock_ids), start_date)) or {"dataset": "price"},
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
    assert calls[6][1][0] == ("2330", "2454", "2881")
    assert calls[6][1][1] is not None
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


def test_run_daily_screener_job_uses_full_universe_loader_when_no_ticker_override(monkeypatch):
    from ai_investment_analyst.analysis import daily_screener_job

    monkeypatch.setattr(
        daily_screener_job,
        "settings",
        SimpleNamespace(screening_tickers=("1101",), screening_tickers_overridden=False),
    )
    captured = {}

    result = daily_screener_job.run_daily_screener_job(
        tickers=None,
        universe_loader=lambda: ["1101", "2330", "2454"],
        base_schema_applier=lambda: None,
        market_seed_applier=lambda: None,
        price_schema_applier=lambda: None,
        revenue_schema_applier=lambda: None,
        financial_schema_applier=lambda: None,
        screener_schema_applier=lambda: None,
        price_loader=lambda stock_ids, start_date=None: {"stock_ids": tuple(stock_ids), "start_date": start_date},
        revenue_loader=lambda stock_ids: {"stock_ids": tuple(stock_ids)},
        financial_loader=lambda stock_ids: {"stock_ids": tuple(stock_ids)},
        screener_generator=lambda **kwargs: captured.update(kwargs) or [],
    )

    assert result.tickers == ["1101", "2330", "2454"]
    assert captured["ticker_loader"]() == ["1101", "2330", "2454"]


def test_run_daily_screener_job_skips_full_universe_fundamentals_when_fresh(monkeypatch):
    from ai_investment_analyst.analysis import daily_screener_job

    monkeypatch.setattr(
        daily_screener_job,
        "settings",
        SimpleNamespace(screening_tickers=("1101",), screening_tickers_overridden=False),
    )
    calls = []
    monkeypatch.setattr(daily_screener_job, "_select_revenue_refresh_tickers", lambda tickers: [])
    monkeypatch.setattr(daily_screener_job, "_select_financial_refresh_tickers", lambda tickers: [])

    result = daily_screener_job.run_daily_screener_job(
        tickers=None,
        universe_loader=lambda: ["1101", "2330", "2454"],
        base_schema_applier=lambda: None,
        market_seed_applier=lambda: None,
        price_schema_applier=lambda: None,
        revenue_schema_applier=lambda: None,
        financial_schema_applier=lambda: None,
        screener_schema_applier=lambda: None,
        price_loader=lambda stock_ids, start_date=None: calls.append(("price", tuple(stock_ids), start_date)) or {"stock_ids": tuple(stock_ids)},
        revenue_loader=lambda stock_ids: calls.append(("revenue", tuple(stock_ids))) or {"stock_ids": tuple(stock_ids)},
        financial_loader=lambda stock_ids: calls.append(("financial", tuple(stock_ids))) or {"stock_ids": tuple(stock_ids)},
        screener_generator=lambda **kwargs: [],
    )

    assert calls[0][0] == "price"
    assert calls[0][1] == ("1101", "2330", "2454")
    assert calls[0][2] is not None
    assert calls[1:] == []
    assert result.source_refresh["revenue"] == {"skipped": True, "reason": "full_universe_revenue_is_fresh"}
    assert result.source_refresh["financial"] == {"skipped": True, "reason": "full_universe_financials_are_fresh"}



def test_run_daily_screener_job_refreshes_missing_full_universe_fundamentals(monkeypatch):
    from ai_investment_analyst.analysis import daily_screener_job

    monkeypatch.setattr(
        daily_screener_job,
        "settings",
        SimpleNamespace(screening_tickers=("1101",), screening_tickers_overridden=False),
    )
    calls = []
    monkeypatch.setattr(daily_screener_job, "_select_revenue_refresh_tickers", lambda tickers: ["1101", "2330"])
    monkeypatch.setattr(daily_screener_job, "_select_financial_refresh_tickers", lambda tickers: ["2454"])

    result = daily_screener_job.run_daily_screener_job(
        tickers=None,
        universe_loader=lambda: ["1101", "2330", "2454"],
        base_schema_applier=lambda: None,
        market_seed_applier=lambda: None,
        price_schema_applier=lambda: None,
        revenue_schema_applier=lambda: None,
        financial_schema_applier=lambda: None,
        screener_schema_applier=lambda: None,
        price_loader=lambda stock_ids, start_date=None: calls.append(("price", tuple(stock_ids), start_date)) or {"stock_ids": tuple(stock_ids)},
        revenue_loader=lambda stock_ids: calls.append(("revenue", tuple(stock_ids))) or {"stock_ids": tuple(stock_ids)},
        financial_loader=lambda stock_ids: calls.append(("financial", tuple(stock_ids))) or {"stock_ids": tuple(stock_ids)},
        screener_generator=lambda **kwargs: [],
    )

    assert calls[0][0] == "price"
    assert calls[0][1] == ("1101", "2330", "2454")
    assert calls[0][2] is not None
    assert calls[1:] == [("revenue", ("1101", "2330")), ("financial", ("2454",))]
    assert result.source_refresh["revenue"] == {"stock_ids": ("1101", "2330")}
    assert result.source_refresh["financial"] == {"stock_ids": ("2454",)}



def test_run_daily_screener_job_prefers_screening_ticker_override_over_full_universe(monkeypatch):
    from ai_investment_analyst.analysis import daily_screener_job

    monkeypatch.setattr(
        daily_screener_job,
        "settings",
        SimpleNamespace(screening_tickers=("2330", "2454"), screening_tickers_overridden=True),
    )
    captured = {}

    result = daily_screener_job.run_daily_screener_job(
        tickers=None,
        universe_loader=lambda: (_ for _ in ()).throw(AssertionError("universe loader should not run when override is set")),
        base_schema_applier=lambda: None,
        market_seed_applier=lambda: None,
        price_schema_applier=lambda: None,
        revenue_schema_applier=lambda: None,
        financial_schema_applier=lambda: None,
        screener_schema_applier=lambda: None,
        price_loader=lambda stock_ids, start_date=None: {"stock_ids": tuple(stock_ids), "start_date": start_date},
        revenue_loader=lambda stock_ids: {"stock_ids": tuple(stock_ids)},
        financial_loader=lambda stock_ids: {"stock_ids": tuple(stock_ids)},
        screener_generator=lambda **kwargs: captured.update(kwargs) or [],
    )

    assert result.tickers == ["2330", "2454"]
    assert captured["ticker_loader"]() == ["2330", "2454"]



def test_latest_expected_revenue_period_uses_release_window():
    from datetime import date

    from ai_investment_analyst.analysis.daily_screener_job import _latest_expected_revenue_period

    assert _latest_expected_revenue_period(date(2026, 5, 9)) == date(2026, 3, 1)
    assert _latest_expected_revenue_period(date(2026, 5, 12)) == date(2026, 4, 1)
    assert _latest_expected_revenue_period(date(2026, 1, 5)) == date(2025, 11, 1)



def test_latest_expected_financial_report_date_uses_quarter_windows():
    from datetime import date

    from ai_investment_analyst.analysis.daily_screener_job import _latest_expected_financial_report_date

    assert _latest_expected_financial_report_date(date(2026, 3, 15)) == date(2025, 9, 30)
    assert _latest_expected_financial_report_date(date(2026, 5, 9)) == date(2025, 12, 31)
    assert _latest_expected_financial_report_date(date(2026, 8, 20)) == date(2026, 3, 31)
    assert _latest_expected_financial_report_date(date(2026, 11, 1)) == date(2026, 6, 30)
    assert _latest_expected_financial_report_date(date(2026, 12, 10)) == date(2026, 9, 30)



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
            price_loader=lambda stock_ids, start_date=None: {"dataset": "price"},
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
            price_loader=lambda stock_ids, start_date=None: calls.append("price_loader") or {"dataset": "price"},
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
