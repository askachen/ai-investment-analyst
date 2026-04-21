from fastapi.testclient import TestClient

from ai_investment_analyst.web.app import app, resolve_stock_name


def test_report_api_returns_report(monkeypatch):
    monkeypatch.setattr(
        'ai_investment_analyst.web.app.generate_stock_report',
        lambda ticker: 'mock report for ' + ticker,
    )
    monkeypatch.setattr(
        'ai_investment_analyst.web.app.resolve_stock_name',
        lambda ticker: '聯發科' if ticker == '2454' else None,
    )
    client = TestClient(app)
    response = client.post('/api/report', json={'ticker': '2454'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['ticker'] == '2454'
    assert payload['report'] == 'mock report for 2454'
    assert payload['report_html'].startswith('<article')
    assert '<h1>2454 聯發科</h1>' in payload['report_html']
    assert '<p>mock report for 2454</p>' in payload['report_html']
    assert payload['mode'] in {'llm', 'fallback', 'deterministic'}


def test_report_api_rejects_blank_ticker():
    client = TestClient(app)
    response = client.post('/api/report', json={'ticker': '   '})
    assert response.status_code == 422


def test_resolve_stock_name_prefers_tw_suffix_for_numeric_tickers(monkeypatch):
    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def info(self):
            if self.symbol == '2454':
                return {'shortName': 'All About Inc'}
            if self.symbol == '2454.TW':
                return {'shortName': '聯發科'}
            return {}

    monkeypatch.setattr('ai_investment_analyst.web.app.yf.Ticker', FakeTicker)

    assert resolve_stock_name('2454') == '聯發科'
