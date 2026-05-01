from fastapi.testclient import TestClient

from ai_investment_analyst.web.app import app


MOCK_REPORT = """【個股分析報告】2330
投資評級：買進
信心等級：高
重點摘要
台積電測試摘要
分析師觀點
AI 需求延續。"""


def test_stock_detail_page_renders_report_with_traditional_chinese_name(monkeypatch):
    monkeypatch.setattr('ai_investment_analyst.web.app.generate_stock_report', lambda ticker: MOCK_REPORT)
    monkeypatch.setattr('ai_investment_analyst.web.app.resolve_stock_name', lambda ticker: '台積電' if ticker == '2330' else None)

    client = TestClient(app)
    response = client.get('/stocks/2330')

    assert response.status_code == 200
    assert '2330 台積電' in response.text
    assert '返回推薦榜單' in response.text
    assert '台積電測試摘要' in response.text
    assert 'AI 需求延續。' in response.text


def test_stock_detail_page_uses_ticker_when_name_missing(monkeypatch):
    monkeypatch.setattr('ai_investment_analyst.web.app.generate_stock_report', lambda ticker: MOCK_REPORT.replace('2330', 'AAPL'))
    monkeypatch.setattr('ai_investment_analyst.web.app.resolve_stock_name', lambda ticker: None)

    client = TestClient(app)
    response = client.get('/stocks/AAPL')

    assert response.status_code == 200
    assert '<h1>AAPL</h1>' in response.text
