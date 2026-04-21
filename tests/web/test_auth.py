from fastapi.testclient import TestClient

from ai_investment_analyst.web.app import app


def test_login_page_renders_when_auth_enabled(monkeypatch):
    monkeypatch.setenv('WEB_LOGIN_PASSWORD', 'secret-pass')

    client = TestClient(app)
    response = client.get('/login')

    assert response.status_code == 200
    assert '登入 AI 投資分析師' in response.text
    assert 'name="password"' in response.text


def test_index_redirects_to_login_when_not_authenticated(monkeypatch):
    monkeypatch.setenv('WEB_LOGIN_PASSWORD', 'secret-pass')

    client = TestClient(app)
    response = client.get('/', follow_redirects=False)

    assert response.status_code == 303
    assert response.headers['location'] == '/login'


def test_login_sets_session_cookie_and_redirects(monkeypatch):
    monkeypatch.setenv('WEB_LOGIN_PASSWORD', 'secret-pass')

    client = TestClient(app)
    response = client.post('/login', data={'password': 'secret-pass'}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers['location'] == '/'
    assert 'session=' in response.headers['set-cookie']


def test_report_api_requires_login_when_auth_enabled(monkeypatch):
    monkeypatch.setenv('WEB_LOGIN_PASSWORD', 'secret-pass')

    client = TestClient(app)
    response = client.post('/api/report', json={'ticker': '2330'})

    assert response.status_code == 401
    assert response.json() == {'detail': 'authentication required'}


def test_authenticated_user_can_access_report_api(monkeypatch):
    monkeypatch.setenv('WEB_LOGIN_PASSWORD', 'secret-pass')
    monkeypatch.setattr(
        'ai_investment_analyst.web.app.generate_stock_report',
        lambda ticker: 'mock report for ' + ticker,
    )

    client = TestClient(app)
    login_response = client.post('/login', data={'password': 'secret-pass'}, follow_redirects=False)

    assert login_response.status_code == 303

    response = client.post('/api/report', json={'ticker': '2330'})
    assert response.status_code == 200
    assert response.json()['report'] == 'mock report for 2330'