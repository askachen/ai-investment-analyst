from fastapi.testclient import TestClient

from ai_investment_analyst.web.app import app


def test_latest_screener_api_returns_snapshot(monkeypatch):
    monkeypatch.setattr('ai_investment_analyst.web.app.resolve_screener_display_name', lambda ticker: {'2330': '台積電', '2454': '聯發科'}.get(ticker))
    monkeypatch.setattr(
        'ai_investment_analyst.web.app.load_latest_screener_snapshot',
        lambda strategy='balanced': {
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
    assert payload['strategy']['key'] == 'balanced'
    assert payload['strategy']['weights'] == {
        'momentum': '25%',
        'revenue': '30%',
        'quality': '15%',
        'valuation': '20%',
        'liquidity': '10%',
    }
    assert payload['strategies'][0]['weights']['revenue'] == '30%'
    assert len(payload['strategies']) >= 3


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
        'strategy': {
            'key': 'balanced',
            'label': '平衡多因子',
            'description': '兼顧盤面、營收、品質、估值與流動性，適合做每日預設榜單。',
            'weights': {
                'momentum': '25%',
                'revenue': '30%',
                'quality': '15%',
                'valuation': '20%',
                'liquidity': '10%',
            },
        },
        'strategies': [
            {
                'key': 'balanced',
                'label': '平衡多因子',
                'description': '兼顧盤面、營收、品質、估值與流動性，適合做每日預設榜單。',
                'weights': {
                    'momentum': '25%',
                    'revenue': '30%',
                    'quality': '15%',
                    'valuation': '20%',
                    'liquidity': '10%',
                },
            },
            {
                'key': 'growth',
                'label': '成長動能',
                'description': '提高營收成長與價格動能權重，較偏中期成長股輪動。',
                'weights': {
                    'momentum': '30%',
                    'revenue': '35%',
                    'quality': '15%',
                    'valuation': '10%',
                    'liquidity': '10%',
                },
            },
            {
                'key': 'value',
                'label': '價值穩健',
                'description': '提高估值與品質權重，偏好獲利穩定且評價較合理的標的。',
                'weights': {
                    'momentum': '15%',
                    'revenue': '15%',
                    'quality': '20%',
                    'valuation': '40%',
                    'liquidity': '10%',
                },
            },
            {
                'key': 'flow',
                'label': '流動性強勢',
                'description': '提高盤面與流動性權重，較偏短中線強勢股與成交量擴張。',
                'weights': {
                    'momentum': '35%',
                    'revenue': '20%',
                    'quality': '10%',
                    'valuation': '10%',
                    'liquidity': '25%',
                },
            },
        ],
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


def test_latest_screener_api_supports_strategy_reranking(monkeypatch):
    calls = []
    monkeypatch.setattr('ai_investment_analyst.web.app.resolve_screener_display_name', lambda ticker: None)
    monkeypatch.setattr(
        'ai_investment_analyst.web.app.load_latest_screener_snapshot',
        lambda strategy='balanced': calls.append(strategy) or {
            'run_date': '2026-05-01',
            'generated_at': '2026-05-01T01:10:00+00:00',
            'strategy': {
                'key': strategy,
                'label': '價值穩健',
                'description': 'value snapshot',
                'weights': {
                    'momentum': '15%',
                    'revenue': '15%',
                    'quality': '20%',
                    'valuation': '40%',
                    'liquidity': '10%',
                },
            },
            'strategies': [
                {
                    'key': 'balanced',
                    'label': '平衡多因子',
                    'description': 'balanced',
                    'weights': {
                        'momentum': '25%',
                        'revenue': '30%',
                        'quality': '15%',
                        'valuation': '20%',
                        'liquidity': '10%',
                    },
                },
                {
                    'key': 'value',
                    'label': '價值穩健',
                    'description': 'value',
                    'weights': {
                        'momentum': '15%',
                        'revenue': '15%',
                        'quality': '20%',
                        'valuation': '40%',
                        'liquidity': '10%',
                    },
                },
            ],
            'results': [
                {
                    'rank': 1,
                    'ticker': 'VALUE',
                    'total_score': '88.00',
                    'close_price': '85',
                    'factor_scores': {
                        'momentum': '14',
                        'revenue': '48',
                        'quality': '88',
                        'valuation': '89.76',
                        'liquidity': '1.2',
                    },
                    'reasons': ['value'],
                },
            ],
        },
    )

    client = TestClient(app)
    response = client.get('/api/screener/latest?strategy=value')

    assert response.status_code == 200
    payload = response.json()
    assert calls == ['value']
    assert payload['strategy']['key'] == 'value'
    assert payload['strategy']['weights']['valuation'] == '40%'
    assert payload['results'][0]['ticker'] == 'VALUE'
    assert payload['results'][0]['rank'] == 1
