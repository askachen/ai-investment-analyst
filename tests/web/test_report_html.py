from ai_investment_analyst.web.app import render_report_html


def test_render_report_html_formats_sections_and_bullets():
    report = """【個股分析報告】2330
投資評級：中立
信心等級：中

一句話投資主軸
AI 需求延續但短線評價偏高。

重點摘要
目前多空訊號分歧。

財務摘要表
- 營收：6500.00 億元
- EPS：10.25

目標價推導
以 Base Case 15.38 元 EPS 與 22 倍本益比推估，目標價約 338.36 元。

Bull Case
- AI 需求續強。

Base Case
- 需求平穩增長。

Bear Case
- 評價修正壓力上升。

結論
短線宜觀察。"""

    html = render_report_html(report)

    assert '<article class="report-card">' in html
    assert '<h1>2330</h1>' in html
    assert '<div class="report-badges">' in html
    assert '<span class="badge badge-rating">投資評級：中立</span>' in html
    assert '<h2>一句話投資主軸</h2>' in html
    assert '<h2>財務摘要表</h2>' in html
    assert '<li>營收：6500.00 億元</li>' in html
    assert '<h2>目標價推導</h2>' in html
    assert '<h2>Bull Case</h2>' in html
    assert '<h2>Base Case</h2>' in html
    assert '<h2>Bear Case</h2>' in html
    assert '<h2>結論</h2>' in html
