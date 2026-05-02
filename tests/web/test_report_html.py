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
    assert '<div class="financial-snapshot-grid">' in html
    assert '<span class="financial-snapshot-label">營收</span>' in html
    assert '<strong class="financial-snapshot-value">6500.00 億元</strong>' in html
    assert '<h2>目標價推導</h2>' in html
    assert '<h2>樂觀情境</h2>' in html
    assert '<h2>基準情境</h2>' in html
    assert '<h2>保守情境</h2>' in html
    assert '<h2>結論</h2>' in html


def test_render_report_html_uses_stock_name_in_title():
    report = """【個股分析報告】2454 聯發科
投資評級：偏多
信心等級：中

結論
中長線趨勢正向。"""

    html = render_report_html(report)

    assert '<h1>2454 聯發科</h1>' in html


def test_render_report_html_adds_quick_navigation_and_lead_section():
    report = """【個股分析報告】2330 台積電
投資評級：買進
信心等級：高

一句話投資主軸
AI 需求推升先進製程報價與產能利用率。

重點摘要
- 短中期動能穩定。
- 現金流與獲利能力同步改善。

估值觀察
本益比已位於區間上緣。
評價標籤：偏高
合理價區間：約 950 - 1,080 元。

目標價推導
以 Base Case 45 元 EPS 與 22 倍本益比推估，目標價約 990 元。

潛在風險
- 若終端需求放緩，評價可能壓縮。"""

    html = render_report_html(report)

    assert '<nav class="report-nav" aria-label="報告章節快速導覽">' in html
    assert '<a href="#section-1">一句話投資主軸</a>' in html
    assert '<a href="#section-2">重點摘要</a>' in html
    assert '<section id="section-1" class="report-section report-section-lead">' in html
    assert '<p class="lead-paragraph">AI 需求推升先進製程報價與產能利用率。</p>' in html
    assert '<section class="report-insights" aria-label="投資重點速覽">' in html
    assert '<span class="insight-label">評價標籤</span>' in html
    assert '<strong>偏高</strong>' in html
    assert '合理價區間：約 950 - 1,080 元。' in html
    assert '目標價約 990 元。' in html


def test_render_report_html_promotes_financial_snapshot_and_scenarios():
    report = """【個股分析報告】2330 台積電
投資評級：買進
信心等級：高

一句話投資主軸
先進製程需求持續增溫。

財務摘要表
- 營收：6500.00 億元
- EPS：10.25
- 淨利：2600.00 億元

Bull Case
- AI 資本支出續強，推升產能利用率。

Base Case
- 高速運算需求延續，獲利穩步成長。

Bear Case
- 終端需求放緩，評價面臨修正。"""

    html = render_report_html(report)

    assert '<div class="financial-snapshot-grid">' in html
    assert '<article class="financial-snapshot-card">' in html
    assert '<span class="financial-snapshot-label">營收</span>' in html
    assert '<strong class="financial-snapshot-value">6500.00 億元</strong>' in html
    assert '<section class="scenario-overview" aria-label="三種情境推演">' in html
    assert '<div class="scenario-overview-title">三種情境推演</div>' in html
    assert '<div class="scenario-grid scenario-grid-overview">' in html
    assert '<article class="scenario-card scenario-card-bull"><div class="scenario-card-label">樂觀情境</div>' in html
    assert '<article class="scenario-card scenario-card-base"><div class="scenario-card-label">基準情境</div>' in html
    assert '<article class="scenario-card scenario-card-bear"><div class="scenario-card-label">保守情境</div>' in html
    assert 'AI 資本支出續強，推升產能利用率。' in html
    assert '高速運算需求延續，獲利穩步成長。' in html
    assert '終端需求放緩，評價面臨修正。' in html


def test_render_report_html_builds_observation_radar_for_catalysts_and_risks():
    report = """【個股分析報告】3017 奇鋐
投資評級：買進
信心等級：中高

利多催化
- GB200 水冷模組出貨升溫。

中性觀察
- 客戶拉貨節奏仍需持續追蹤。

潛在風險
- 高階散熱市場競爭升溫。"""

    html = render_report_html(report)

    assert '<section class="observation-radar" aria-label="投資觀察雷達">' in html
    assert '<div class="observation-radar-title">投資觀察雷達</div>' in html
    assert '<article class="observation-card observation-card-bull">' in html
    assert '<article class="observation-card observation-card-neutral">' in html
    assert '<article class="observation-card observation-card-bear">' in html
    assert 'GB200 水冷模組出貨升溫。' in html
    assert '客戶拉貨節奏仍需持續追蹤。' in html
    assert '高階散熱市場競爭升溫。' in html


def test_render_report_html_promotes_analyst_takeaway_and_risk_focus():
    report = """【個股分析報告】2382 廣達
投資評級：買進
信心等級：中高

一句話投資主軸
AI 伺服器出貨動能延續。

風險提示
- 雲端客戶資本支出若遞延，短線修正壓力將升高。
- 毛利率改善速度可能低於市場預期。

分析師觀點
未來兩季若 AI 伺服器良率與出貨同步改善，評價有望重新上修。"""

    html = render_report_html(report)

    assert '<section class="analyst-takeaway" aria-label="分析師快速結論">' in html
    assert '<div class="analyst-takeaway-title">分析師快速結論</div>' in html
    assert '未來兩季若 AI 伺服器良率與出貨同步改善，評價有望重新上修。' in html
    assert '<section class="risk-focus" aria-label="風險提示重點">' in html
    assert '<div class="risk-focus-title">風險提示重點</div>' in html
    assert '雲端客戶資本支出若遞延，短線修正壓力將升高。' in html
    assert '毛利率改善速度可能低於市場預期。' in html
