from types import SimpleNamespace

from ai_investment_analyst.etl import finmind_loader


def test_sync_taiwan_stock_universe_filters_non_stock_like_rows(monkeypatch):
    monkeypatch.setattr(
        finmind_loader,
        "settings",
        SimpleNamespace(finmind_api_token="token"),
    )

    payload = [
        {"stock_id": "1101", "stock_name": "台泥", "industry_category": "水泥工業", "type": "twse"},
        {"stock_id": "2330", "stock_name": "台積電", "industry_category": "半導體業", "type": "twse"},
        {"stock_id": "0050", "stock_name": "ETF", "industry_category": "ETF", "type": "etf"},
        {"stock_id": "ABC", "stock_name": "非股票", "industry_category": "其他", "type": "other"},
    ]
    calls = []

    result = finmind_loader.sync_taiwan_stock_universe(
        fetch_stock_info_rows=lambda: payload,
        ensure_data_source_fn=lambda cur: calls.append("data_source") or "source-id",
        get_market_id_fn=lambda cur, market_code: calls.append(("market", market_code)) or "market-id",
        create_ingestion_run_fn=lambda cur, data_source_id, market_id, stock_ids, start_date: calls.append(("run", tuple(stock_ids), start_date)) or "run-id",
        upsert_symbol_fn=lambda cur, market_id, spec, info: calls.append(("upsert", spec.stock_id, info["stock_name"])) or spec.stock_id,
        finalize_ingestion_run_fn=lambda cur, ingestion_run_id, **kwargs: calls.append(("finalize", ingestion_run_id, kwargs["records_received"], kwargs["status"])),
        connection_factory=lambda: _FakeConnection(),
    )

    assert result == ["1101", "2330"]
    assert calls == [
        "data_source",
        ("market", "TW"),
        ("run", ("1101", "2330"), "universe-sync"),
        ("upsert", "1101", "台泥"),
        ("upsert", "2330", "台積電"),
        ("finalize", "run-id", 2, "success"),
    ]


class _FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def cursor(self, *args, **kwargs):
        return _FakeCursor()

    def commit(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False
