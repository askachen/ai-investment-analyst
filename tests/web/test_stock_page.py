from fastapi.testclient import TestClient

from ai_investment_analyst.web.app import app


MOCK_REPORT = """【個股分析報告】2330
投資評級：買進
信心等級：高
一句話投資主軸
台積電測試摘要
財務摘要表
- 營收：6500.00 億元
- EPS：10.25
- 淨利：2600.00 億元
估值觀察
本益比已反映部分成長預期。
評價標籤：偏高
合理價區間：約 950 - 1,080 元。
目標價推導
以 Base Case 45 元 EPS 與 22 倍本益比推估，目標價約 990 元。
Bull Case
- AI 需求延續。
Base Case
- 先進製程報價穩定。
Bear Case
- 終端需求轉弱。
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
    assert '投資重點速覽' in response.text
    assert '評價標籤' in response.text
    assert '合理價區間：約 950 - 1,080 元。' in response.text
    assert '目標價約 990 元。' in response.text
    assert 'financial-snapshot-grid' in response.text
    assert 'scenario-grid' in response.text


def test_stock_detail_page_uses_ticker_when_name_missing(monkeypatch):
    monkeypatch.setattr('ai_investment_analyst.web.app.generate_stock_report', lambda ticker: MOCK_REPORT.replace('2330', 'AAPL'))
    monkeypatch.setattr('ai_investment_analyst.web.app.resolve_stock_name', lambda ticker: None)

    client = TestClient(app)
    response = client.get('/stocks/AAPL')

    assert response.status_code == 200
    assert '<h1>AAPL</h1>' in response.text
