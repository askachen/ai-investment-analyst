from fastapi.testclient import TestClient

from ai_investment_analyst.analysis.data_quality import DataQualityDomain, StockDataQuality
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
    monkeypatch.setattr(
        'ai_investment_analyst.web.app.build_stock_data_quality',
        lambda ticker: None,
    )

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
    assert 'decision-card-layout' in response.text
    assert '.data-quality-grid,\n        .report-insights-grid,\n        .financial-snapshot-grid' in response.text
    assert 'overflow-wrap: anywhere;' in response.text
    assert 'min-height: 44px;' in response.text
    assert '決策卡' in response.text
    assert '建議動作' in response.text
    assert '買進' in response.text
    assert '推薦信心' in response.text
    assert '下一步' in response.text


def test_stock_detail_page_shows_observation_radar_when_report_contains_catalysts_and_risks(monkeypatch):
    report = """【個股分析報告】3017
投資評級：買進
信心等級：中高
利多催化
- GB200 水冷模組出貨升溫。
中性觀察
- 客戶拉貨節奏仍需持續追蹤。
潛在風險
- 高階散熱市場競爭升溫。
分析師觀點
短線動能偏強，但仍需留意評價升溫後的震盪。"""
    monkeypatch.setattr('ai_investment_analyst.web.app.generate_stock_report', lambda ticker: report)
    monkeypatch.setattr('ai_investment_analyst.web.app.resolve_stock_name', lambda ticker: '奇鋐' if ticker == '3017' else None)
    monkeypatch.setattr('ai_investment_analyst.web.app.build_stock_data_quality', lambda ticker: None)

    client = TestClient(app)
    response = client.get('/stocks/3017')

    assert response.status_code == 200
    assert '決策速讀' in response.text
    assert '分析師結論' in response.text
    assert '利多催化' in response.text
    assert '潛在風險' in response.text
    assert '短線動能偏強，但仍需留意評價升溫後的震盪。' in response.text
    assert '投資觀察雷達' in response.text
    assert 'observation-card observation-card-bull' in response.text
    assert 'observation-card observation-card-neutral' in response.text
    assert 'observation-card observation-card-bear' in response.text


def test_stock_detail_page_uses_ticker_when_name_missing(monkeypatch):
    monkeypatch.setattr('ai_investment_analyst.web.app.generate_stock_report', lambda ticker: MOCK_REPORT.replace('2330', 'AAPL'))
    monkeypatch.setattr('ai_investment_analyst.web.app.resolve_stock_name', lambda ticker: None)
    monkeypatch.setattr('ai_investment_analyst.web.app.build_stock_data_quality', lambda ticker: None)

    client = TestClient(app)
    response = client.get('/stocks/AAPL')

    assert response.status_code == 200
    assert '<h1>AAPL</h1>' in response.text


def test_stock_detail_page_renders_data_quality_panel(monkeypatch):
    quality = StockDataQuality(
        overall_status='partial',
        confidence_label='中高',
        completeness_pct=75,
        domains=[
            DataQualityDomain('price', '價格', 'fresh', '價格資料 1 天內更新。', '2026-05-09'),
            DataQualityDomain('revenue', '月營收', 'partial', '月營收可用但不完整。', '2026-04-01'),
            DataQualityDomain('financial', '財報', 'missing', '缺少財報摘要資料。'),
        ],
        warnings=['缺少財報摘要資料。'],
    )
    monkeypatch.setattr('ai_investment_analyst.web.app.generate_stock_report', lambda ticker: MOCK_REPORT)
    monkeypatch.setattr('ai_investment_analyst.web.app.resolve_stock_name', lambda ticker: '台積電')
    monkeypatch.setattr('ai_investment_analyst.web.app.build_stock_data_quality', lambda ticker: quality)

    client = TestClient(app)
    response = client.get('/stocks/2330')

    assert response.status_code == 200
    assert '資料可信度' in response.text
    assert '完整度 75%｜信心 中高' in response.text
    assert '價格資料 1 天內更新。' in response.text
    assert '缺少財報摘要資料。' in response.text
