from fastapi.testclient import TestClient

from ai_investment_analyst.web.app import app


def test_health_returns_ok():
    client = TestClient(app)
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
