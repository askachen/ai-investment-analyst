from fastapi.testclient import TestClient

from ai_investment_analyst.web.app import app


def test_index_page_contains_form():
    client = TestClient(app)
    response = client.get('/')
    assert response.status_code == 200
    assert 'AI 投資分析師' in response.text
    assert 'name="ticker"' in response.text
    assert '開始分析' in response.text
    assert 'id="result-html"' in response.text
    assert 'id="daily-screener"' in response.text
    assert '推薦股策略排行' in response.text
    assert '股票' in response.text
    assert '盤面' in response.text
    assert '基本面' in response.text
    assert '模型' in response.text
    assert '@media (max-width: 768px)' in response.text
    assert 'overflow-x: hidden;' in response.text
    assert 'data-label="股票"' in response.text
    assert 'compact-score-note' in response.text
    assert 'compact-topline' in response.text
    assert 'compact-meta-grid' in response.text
    assert 'stock-name' in response.text
    assert 'stock-link' in response.text
    assert 'action="/logout"' not in response.text
    assert "fetch('/api/screener/latest')" in response.text
    assert 'const submitButton = form.querySelector(\'button[type="submit"]\');' in response.text
    assert 'submitButton.disabled = true;' in response.text
    assert 'submitButton.disabled = false;' in response.text
    assert 'result.innerHTML = payload.report_html;' in response.text
    assert 'function buildReportUrl(ticker)' in response.text
    assert '返回個股完整報告' in response.text
    assert 'function buildScreenerTable(payload)' in response.text
