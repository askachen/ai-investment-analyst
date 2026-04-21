from fastapi.testclient import TestClient

from ai_investment_analyst.web.app import app


def test_report_api_returns_report(monkeypatch):
    monkeypatch.setattr(
        'ai_investment_analyst.web.app.generate_stock_report',
        lambda ticker: 'mock report for ' + ticker,
    )
    client = TestClient(app)
    response = client.post('/api/report', json={'ticker': '2330'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['ticker'] == '2330'
    assert payload['report'] == 'mock report for 2330'
    assert payload['mode'] in {'llm', 'fallback', 'deterministic'}


def test_report_api_rejects_blank_ticker():
    client = TestClient(app)
    response = client.post('/api/report', json={'ticker': '   '})
    assert response.status_code == 422
