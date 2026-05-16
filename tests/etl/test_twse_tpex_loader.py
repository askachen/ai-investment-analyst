from datetime import date
from decimal import Decimal
import ssl
from types import SimpleNamespace

from ai_investment_analyst.etl import twse_tpex_loader


def test_store_price_row_uses_previous_close_basis_for_official_change_percent(monkeypatch):
    captured = {}
    monkeypatch.setattr(twse_tpex_loader, "upsert_price_daily_raw", lambda *args, **kwargs: captured.update(kwargs))
    monkeypatch.setattr(twse_tpex_loader, "refresh_price_daily_canonical", lambda *args, **kwargs: None)

    twse_tpex_loader.store_price_row(
        object(),
        symbol_id="symbol-id",
        data_source_id="source-id",
        ingestion_run_id="run-id",
        row={
            "date": "2026-05-07",
            "open": Decimal("95"),
            "max": Decimal("101"),
            "min": Decimal("94"),
            "close": Decimal("100"),
            "spread": Decimal("2"),
            "Trading_Volume": 1000,
            "Trading_money": Decimal("100000"),
            "Trading_turnover": 10,
        },
    )

    assert captured["price_change"] == Decimal("2")
    assert captured["change_percent"] == Decimal("2.040816326530612244897959184")


def test_official_data_tls_adapter_disables_only_openssl_strict_flag(monkeypatch):
    class FakeContext:
        verify_flags = ssl.VERIFY_X509_STRICT | ssl.VERIFY_X509_PARTIAL_CHAIN

    fake_context = FakeContext()
    captured = {}

    def fake_pool_manager(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(twse_tpex_loader.ssl, "create_default_context", lambda: fake_context)
    monkeypatch.setattr(twse_tpex_loader, "PoolManager", fake_pool_manager)

    twse_tpex_loader._OfficialDataTLSAdapter()

    assert fake_context.verify_flags & ssl.VERIFY_X509_STRICT == 0
    assert fake_context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN
    assert captured["ssl_context"] is fake_context


def test_parse_twse_daily_price_rows_filters_to_requested_stock_ids():
    payload = {
        "tables": [
            {
                "title": "每日收盤行情",
                "fields": [
                    "證券代號",
                    "證券名稱",
                    "成交股數",
                    "成交筆數",
                    "成交金額",
                    "開盤價",
                    "最高價",
                    "最低價",
                    "收盤價",
                    "漲跌(+/-)",
                    "漲跌價差",
                ],
                "data": [
                    ["00400A", "主動ETF", "1,000", "10", "12,000", "12.0", "12.1", "11.9", "12.0", "+", "0.1"],
                    ["2330", "台積電", "40,000,000", "50,000", "45,600,000,000", "1120.00", "1150.00", "1115.00", "1140.00", "+", "20.00"],
                    ["2454", "聯發科", "--", "--", "--", "--", "--", "--", "--", "", "--"],
                ],
            }
        ]
    }

    rows = twse_tpex_loader.parse_twse_daily_price_rows(payload, trading_date=date(2026, 5, 7), stock_ids={"2330", "2454"})

    assert rows == [
        {
            "date": "2026-05-07",
            "stock_id": "2330",
            "stock_name": "台積電",
            "exchange": "TWSE",
            "open": Decimal("1120.00"),
            "max": Decimal("1150.00"),
            "min": Decimal("1115.00"),
            "close": Decimal("1140.00"),
            "spread": Decimal("20.00"),
            "Trading_Volume": 40000000,
            "Trading_money": Decimal("45600000000"),
            "Trading_turnover": 50000,
        }
    ]


def test_parse_tpex_daily_price_rows_filters_to_requested_stock_ids():
    payload = {
        "date": "20260507",
        "tables": [
            {
                "title": "上櫃股票行情",
                "fields": [
                    "代號",
                    "名稱",
                    "收盤",
                    "漲跌",
                    "開盤",
                    "最高",
                    "最低",
                    "均價",
                    "成交股數",
                    "成交金額(元)",
                    "成交筆數",
                ],
                "data": [
                    ["006201", "元大富櫃50", "46.83", "+0.85", "46.23", "46.88", "46.19", "46.57", "387,533", "18,046,255", "360"],
                    ["6488", "環球晶", "505.00", "-5.00", "510.00", "515.00", "503.00", "508.00", "1,200,000", "609,600,000", "2,300"],
                ],
            }
        ],
    }

    rows = twse_tpex_loader.parse_tpex_daily_price_rows(payload, trading_date=date(2026, 5, 7), stock_ids={"6488"})

    assert rows == [
        {
            "date": "2026-05-07",
            "stock_id": "6488",
            "stock_name": "環球晶",
            "exchange": "TPEx",
            "open": Decimal("510.00"),
            "max": Decimal("515.00"),
            "min": Decimal("503.00"),
            "close": Decimal("505.00"),
            "spread": Decimal("-5.00"),
            "Trading_Volume": 1200000,
            "Trading_money": Decimal("609600000"),
            "Trading_turnover": 2300,
        }
    ]


def test_fetch_official_taiwan_stock_universe_combines_twse_and_tpex_rows():
    twse_rows = [
        {"公司代號": "1101", "公司簡稱": "台泥", "產業別": "01"},
        {"公司代號": "ABCD", "公司簡稱": "非股票", "產業別": "80"},
    ]
    tpex_rows = [
        {"SecuritiesCompanyCode": "6488", "CompanyAbbreviation": "環球晶", "SecuritiesIndustryCode": "24"},
        {"SecuritiesCompanyCode": "006201", "CompanyAbbreviation": "元大富櫃50", "SecuritiesIndustryCode": ""},
    ]

    rows = twse_tpex_loader.build_official_stock_info_rows(twse_rows, tpex_rows)

    assert rows == [
        {"stock_id": "1101", "stock_name": "台泥", "industry_category": "01", "type": "twse", "exchange": "TWSE"},
        {"stock_id": "6488", "stock_name": "環球晶", "industry_category": "24", "type": "tpex", "exchange": "TPEx"},
    ]


def test_sync_official_taiwan_stock_universe_persists_all_official_symbols(monkeypatch):
    monkeypatch.setattr(
        twse_tpex_loader,
        "fetch_official_taiwan_stock_universe_rows",
        lambda: [
            {"stock_id": "1101", "stock_name": "台泥", "industry_category": "01", "type": "twse", "exchange": "TWSE"},
            {"stock_id": "6488", "stock_name": "環球晶", "industry_category": "24", "type": "tpex", "exchange": "TPEx"},
        ],
    )
    calls = []

    result = twse_tpex_loader.sync_official_taiwan_stock_universe(
        ensure_data_source_fn=lambda cur: calls.append("data_source") or "source-id",
        get_market_id_fn=lambda cur, market_code: calls.append(("market", market_code)) or "market-id",
        create_ingestion_run_fn=lambda cur, data_source_id, market_id, stock_ids, start_date: calls.append(("run", tuple(stock_ids), start_date)) or "run-id",
        upsert_symbol_fn=lambda cur, market_id, spec, info: calls.append(("upsert", spec.stock_id, info["stock_name"], info["exchange"])) or spec.stock_id,
        finalize_ingestion_run_fn=lambda cur, ingestion_run_id, **kwargs: calls.append(("finalize", ingestion_run_id, kwargs["records_received"], kwargs["status"])),
        connection_factory=lambda: _FakeConnection(),
    )

    assert result == ["1101", "6488"]
    assert calls == [
        "data_source",
        ("market", "TW"),
        ("run", ("1101", "6488"), "official-universe-sync"),
        ("upsert", "1101", "台泥", "TWSE"),
        ("upsert", "6488", "環球晶", "TPEx"),
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
