from ai_investment_analyst.analysis.llm import GeminiReportClient, build_gemini_prompt, generate_analyst_report
from ai_investment_analyst.analysis.news import NewsItem
from ai_investment_analyst.analysis.stock_report import ReportFacts
from ai_investment_analyst.config import Settings


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_build_gemini_prompt_includes_facts_and_news():
    facts = ReportFacts(
        rating="偏多",
        confidence="中",
        summary="基本面與價格動能同步改善。",
        key_points=["價格站穩短期均線", "月營收年增為正"],
        price_observation="近 5 日漲幅 6.25%。",
        fundamental_observation="月營收年增 22.3%，財報獲利維持高檔。",
        valuation_observation="本益比約 20 倍，評價位於歷史中高區間。",
        valuation_label="合理",
        valuation_range="合理價區間：約 1500 - 1800。",
        news_observation="近期新聞偏正向。",
        risk_flags=["短線漲多後可能震盪"],
        conclusion="維持偏多看法，但需追蹤需求延續性。",
    )

    news_items = [NewsItem(title="AI demand strong", publisher="Reuters", link="https://example.com", published_at="2026-04-21T08:00:00Z", summary="Orders remain robust")]

    prompt = build_gemini_prompt("2330", facts, news_items)

    assert "2330" in prompt
    assert "價格站穩短期均線" in prompt
    assert "AI demand strong" in prompt
    assert "風險" in prompt


def test_generate_analyst_report_falls_back_without_api_key():
    facts = ReportFacts(
        rating="偏多",
        confidence="中",
        summary="summary",
        key_points=["point"],
        price_observation="price",
        fundamental_observation="fundamental",
        valuation_observation="valuation",
        valuation_label="合理",
        valuation_range="合理價區間：100-120",
        news_observation="news",
        risk_flags=["risk"],
        conclusion="conclusion",
    )

    result = generate_analyst_report(
        ticker="2330",
        facts=facts,
        news_items=[],
        settings=Settings(database_url="", finmind_api_token="", finlab_api_key="", gemini_api_key=""),
    )

    assert result.used_llm is False
    assert "投資評級" in result.report


def test_gemini_client_parses_response_text():
    facts = ReportFacts(
        rating="偏多",
        confidence="中",
        summary="summary",
        key_points=["point"],
        price_observation="price",
        fundamental_observation="fundamental",
        valuation_observation="valuation",
        valuation_label="合理",
        valuation_range="合理價區間：100-120",
        news_observation="news",
        risk_flags=["risk"],
        conclusion="conclusion",
    )

    def fake_post(url, json, timeout):
        assert "generateContent" in url
        return DummyResponse(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "【個股分析報告】2330\n投資評級：偏多"}
                            ]
                        }
                    }
                ]
            }
        )

    client = GeminiReportClient(api_key="test-key", model="gemini-2.0-flash", http_post=fake_post)
    text = client.generate_report("2330", facts, [])

    assert "投資評級：偏多" in text
