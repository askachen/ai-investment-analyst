from ai_investment_analyst.web.app import render_report_html


def test_render_report_html_formats_sections_and_bullets():
    report = """【個股分析報告】2330
投資評級：中立
信心等級：中

重點摘要
目前多空訊號分歧。

重點摘要（條列）
- 第一點
- 第二點

結論
短線宜觀察。"""

    html = render_report_html(report)

    assert '<article class="report-card">' in html
    assert '<h1>2330</h1>' in html
    assert '<div class="report-badges">' in html
    assert '<span class="badge badge-rating">投資評級：中立</span>' in html
    assert '<h2>重點摘要</h2>' in html
    assert '<p>目前多空訊號分歧。</p>' in html
    assert '<ul>' in html
    assert '<li>第一點</li>' in html
    assert '<li>第二點</li>' in html
    assert '<h2>結論</h2>' in html
