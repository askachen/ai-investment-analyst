from fastapi.testclient import TestClient

from ai_investment_analyst.web.app import app


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
