from ai_investment_analyst.analysis.news import (
    NewsItem,
    classify_news_catalysts,
    compress_news_item_to_one_liner,
    fetch_ticker_news,
    normalize_yfinance_news,
    rewrite_news_as_analyst_bullets,
    summarize_news_in_traditional_chinese,
)


class FakeTicker:
    def __init__(self, symbol: str):
        self.symbol = symbol

    def get_news(self, count=10, tab="news"):
        assert self.symbol == "2330.TW"
        assert count == 2
        assert tab == "news"
        return [
            {
                "content": {
                    "title": "TSMC expands capacity",
                    "summary": "Demand for advanced nodes remains strong.",
                    "canonicalUrl": {"url": "https://example.com/a"},
                    "provider": {"displayName": "Reuters"},
                    "pubDate": "2026-04-21T08:00:00Z",
                }
            },
            {
                "content": {
                    "title": "TSMC wins new AI orders",
                    "summary": "Cloud customers continue to invest.",
                    "canonicalUrl": {"url": "https://example.com/b"},
                    "provider": {"displayName": "Bloomberg"},
                    "pubDate": "2026-04-20T08:00:00Z",
                }
            },
            {"content": {"summary": "missing title should be skipped"}},
        ]


def test_normalize_yfinance_news_filters_invalid_items():
    items = normalize_yfinance_news(
        [
            {"content": {"title": "A", "summary": "B", "canonicalUrl": {"url": "https://example.com"}, "provider": {"displayName": "Reuters"}, "pubDate": "2026-04-21T08:00:00Z"}},
            {"content": {"summary": "skip me"}},
        ],
        limit=5,
    )

    assert items == [
        NewsItem(
            title="A",
            publisher="Reuters",
            link="https://example.com",
            published_at="2026-04-21T08:00:00Z",
            summary="B",
        )
    ]


def test_fetch_ticker_news_uses_ticker_factory_and_limit():
    items = fetch_ticker_news("2330.TW", count=2, ticker_factory=FakeTicker)

    assert len(items) == 2
    assert items[0].title == "TSMC expands capacity"
    assert items[1].publisher == "Bloomberg"


def test_summarize_news_in_traditional_chinese_uses_translator_and_fallback():
    items = [
        NewsItem(
            title="TSMC wins new AI orders",
            publisher="Reuters",
            link="https://example.com/a",
            published_at="2026-04-20T08:00:00Z",
            summary="Cloud customers continue to invest.",
        ),
        NewsItem(
            title="Margin outlook improves",
            publisher="Bloomberg",
            link="https://example.com/b",
            published_at="2026-04-19T08:00:00Z",
            summary="Gross margin outlook improves this quarter.",
        ),
    ]

    result = summarize_news_in_traditional_chinese(
        items,
        translator=lambda text: f"简体：{text}",
    )

    assert result[0].title == "簡體：TSMC wins new AI orders"
    assert result[0].summary == "簡體：Cloud customers continue to invest."
    assert result[1].title == "簡體：Margin outlook improves"


def test_rewrite_news_as_analyst_bullets_uses_tw_style():
    items = [
        NewsItem(
            title="臺積電上調全年營收展望",
            publisher="WSJ",
            link="https://example.com/a",
            published_at="2026-04-20T08:00:00Z",
            summary="公司指出 AI 晶片需求續強，先進製程接單能見度提升。",
        )
    ]

    bullets = rewrite_news_as_analyst_bullets(items)

    assert "市場焦點偏多" in bullets[0]
    assert "AI 晶片需求續強" in bullets[0]
    assert "上調全年營收展望" in bullets[0]


def test_classify_news_catalysts_groups_positive_neutral_and_risk():
    items = [
        NewsItem(
            title="臺積電上調全年營收展望",
            publisher="WSJ",
            link="https://example.com/a",
            published_at="2026-04-20T08:00:00Z",
            summary="AI 晶片需求續強。",
        ),
        NewsItem(
            title="外資關注估值是否偏高",
            publisher="Reuters",
            link="https://example.com/b",
            published_at="2026-04-19T08:00:00Z",
            summary="市場討論評價已反映多數利多。",
        ),
        NewsItem(
            title="地緣政治變數升溫",
            publisher="Bloomberg",
            link="https://example.com/c",
            published_at="2026-04-18T08:00:00Z",
            summary="供應鏈不確定性可能增加。",
        ),
    ]

    groups = classify_news_catalysts(items)

    assert groups["positive"]
    assert groups["neutral"]
    assert groups["risk"]


def test_compress_news_item_to_one_liner_creates_short_analyst_note():
    item = NewsItem(
        title="臺積電上調全年營收展望",
        publisher="WSJ",
        link="https://example.com/a",
        published_at="2026-04-20T08:00:00Z",
        summary="公司指出 AI 晶片需求續強，先進製程接單能見度提升，市場關注今年獲利上修空間。",
    )

    line = compress_news_item_to_one_liner(item)

    assert "臺積電上調全年營收展望" in line
    assert "AI 晶片需求續強" in line
    assert len(line) < 80
