from ai_investment_analyst.web.app import resolve_screener_display_name, resolve_stock_name


def test_resolve_screener_display_name_returns_taiwanese_chinese_name(monkeypatch):
    monkeypatch.setattr('ai_investment_analyst.web.app.lookup_taiwan_stock_name', lambda ticker: '聯發科' if ticker == '2454' else None)
    monkeypatch.setattr('ai_investment_analyst.web.app.load_symbol_display_name_from_db', lambda ticker: None)
    monkeypatch.setattr('ai_investment_analyst.web.app.resolve_stock_name', lambda ticker: 'MediaTek Inc.' if ticker == '2454' else None)

    assert resolve_screener_display_name('2454') == '聯發科'


def test_resolve_stock_name_falls_back_to_builtin_taiwanese_name_when_live_sources_unavailable(monkeypatch):
    monkeypatch.setattr('ai_investment_analyst.web.app.lookup_taiwan_stock_name', lambda ticker: None)
    monkeypatch.setattr('ai_investment_analyst.web.app.load_symbol_display_name_from_db', lambda ticker: None)

    class FakeTicker:
        def __init__(self, symbol: str):
            self.info = {'shortName': 'DELTA ELECTRONIC'}

    monkeypatch.setattr('ai_investment_analyst.web.app.yf.Ticker', FakeTicker)

    assert resolve_stock_name('2308') == '台達電'
