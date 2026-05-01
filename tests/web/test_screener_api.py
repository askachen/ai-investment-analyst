from fastapi.testclient import TestClient

from ai_investment_analyst.web.app import app


def test_latest_screener_api_returns_snapshot(monkeypatch):
    monkeypatch.setattr('ai_investment_analyst.web.app.resolve_screener_display_name', lambda ticker: {'2330': '台積電', '2454': '聯發科'}.get(ticker))
    monkeypatch.setattr(
        'ai_investment_analyst.web.app.load_latest_screener_snapshot',
        lambda: {
            'run_date': '2026-05-01',
            'generated_at': '2026-05-01T01:10:00+00:00',
            'results': [
                {
                    'rank': 1,
                    'ticker': '2330',
                    'total_score': '82.50',
                    'reasons': ['月營收年增 22.30%', '近 10 日動能維持正向'],
                },
                {
                    'rank': 2,
                    'ticker': '2454',
                    'total_score': '74.25',
                    'reasons': ['EPS 維持正值'],
                },
                {
                    'rank': 3,
                    'ticker': 'AAPL',
                    'total_score': '63.20',
                    'reasons': ['估值中性'],
                },
            ],
        },
    )

    client = TestClient(app)
    response = client.get('/api/screener/latest')

    assert response.status_code == 200
    payload = response.json()
    assert payload['run_date'] == '2026-05-01'
    assert payload['results'][0]['ticker'] == '2330'
    assert payload['results'][0]['display_name'] == '台積電'
    assert payload['results'][0]['rank'] == 1
    assert payload['results'][0]['reasons'][0] == '月營收年增 22.30%'
    assert payload['results'][1]['display_name'] == '聯發科'
    assert payload['results'][2]['ticker'] == 'AAPL'
    assert payload['results'][2]['display_name'] is None


def test_resolve_screener_display_name_falls_back_to_db_local_name(monkeypatch):
    monkeypatch.setattr('ai_investment_analyst.web.app.lookup_taiwan_stock_name', lambda ticker: None)
    monkeypatch.setattr('ai_investment_analyst.web.app.load_symbol_display_name_from_db', lambda ticker: '玉晶光' if ticker == '3406' else None)

    from ai_investment_analyst.web.app import resolve_screener_display_name

    assert resolve_screener_display_name('3406') == '玉晶光'


def test_resolve_stock_name_prefers_db_local_name_before_yfinance(monkeypatch):
    monkeypatch.setattr('ai_investment_analyst.web.app.lookup_taiwan_stock_name', lambda ticker: None)
    monkeypatch.setattr('ai_investment_analyst.web.app.load_symbol_display_name_from_db', lambda ticker: '台積電' if ticker == '2330' else None)
    monkeypatch.setattr('ai_investment_analyst.web.app.candidate_market_tickers', lambda ticker: [ticker, f'{ticker}.TW'])

    class DummyTicker:
        @property
        def info(self):
            return {'shortName': 'Taiwan Semiconductor Manufacturing Co.'}

    monkeypatch.setattr('ai_investment_analyst.web.app.yf.Ticker', lambda ticker: DummyTicker())

    from ai_investment_analyst.web.app import resolve_stock_name

    assert resolve_stock_name('2330') == '台積電'


def test_latest_screener_api_returns_empty_payload_when_missing(monkeypatch):
    monkeypatch.setattr('ai_investment_analyst.web.app.load_latest_screener_snapshot', lambda: None)

    client = TestClient(app)
    response = client.get('/api/screener/latest')

    assert response.status_code == 200
    assert response.json() == {
        'run_date': None,
        'generated_at': None,
        'universe_size': None,
        'candidate_count': None,
        'results': [],
    }


def test_latest_screener_api_returns_empty_payload_when_store_fails(monkeypatch):
    monkeypatch.setattr(
        'ai_investment_analyst.web.app.load_latest_screener_snapshot',
        lambda: (_ for _ in ()).throw(RuntimeError('db unavailable')),
    )

    client = TestClient(app)
    response = client.get('/api/screener/latest')

    assert response.status_code == 200
    assert response.json()['results'] == []
