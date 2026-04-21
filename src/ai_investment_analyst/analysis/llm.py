from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import requests

from ai_investment_analyst.analysis.news import NewsItem
from ai_investment_analyst.config import Settings, settings


@dataclass(frozen=True)
class AnalystReportResult:
    report: str
    used_llm: bool


def _render_prompt_section(title: str, lines: list[str]) -> str:
    content = "\n".join(f"- {line}" for line in lines if line)
    return f"## {title}\n{content}" if content else f"## {title}\n- N/A"


def build_gemini_prompt(ticker: str, facts: Any, news_items: list[NewsItem]) -> str:
    news_lines = [
        f"{item.title} | {item.publisher} | {item.published_at} | {item.summary}"
        for item in news_items
    ] or ["No recent news available"]

    return "\n\n".join(
        [
            "你是一位嚴謹、像真人賣方/買方分析師的股票研究員。請用繁體中文撰寫個股分析報告，避免空話，務必清楚寫出風險。",
            f"股票代號：{ticker}",
            _render_prompt_section(
                "已知觀察",
                [
                    f"投資評級：{facts.rating}",
                    f"信心等級：{facts.confidence}",
                    f"一句話投資主軸：{facts.thesis}",
                    f"重點摘要：{facts.summary}",
                    f"價格觀察：{facts.price_observation}",
                    f"基本面觀察：{facts.fundamental_observation}",
                    f"估值觀察：{facts.valuation_observation}",
                    f"評價標籤：{facts.valuation_label}",
                    f"合理價區間：{facts.valuation_range}",
                    f"目標價推導：{facts.target_price_summary}",
                    f"新聞觀察：{facts.news_observation}",
                    f"結論：{facts.conclusion}",
                ]
                + [f"重點：{point}" for point in facts.key_points]
                + [f"財務摘要：{item}" for item in facts.financial_snapshot]
                + [f"風險：{risk}" for risk in facts.risk_flags],
            ),
            _render_prompt_section("近期新聞", news_lines),
            "請固定輸出以下段落：標題、投資評級、重點摘要、價格與技術面觀察、基本面觀察、新聞與市場催化、風險提示、結論。",
        ]
    )


class GeminiReportClient:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        http_post: Callable[..., Any] | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.http_post = http_post or requests.post

    def generate_report(self, ticker: str, facts: Any, news_items: list[NewsItem]) -> str:
        prompt = build_gemini_prompt(ticker, facts, news_items)
        response = self.http_post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        candidates = payload.get("candidates") or []
        for candidate in candidates:
            parts = (((candidate.get("content") or {}).get("parts")) or [])
            texts = [part.get("text", "") for part in parts if part.get("text")]
            if texts:
                return "\n".join(texts).strip()
        raise ValueError("Gemini response did not contain text")


def generate_analyst_report(
    ticker: str,
    facts: Any,
    news_items: list[NewsItem],
    settings: Settings = settings,
    client: GeminiReportClient | None = None,
    fallback_renderer: Callable[[str, Any, list[NewsItem]], str] | None = None,
) -> AnalystReportResult:
    from ai_investment_analyst.analysis.stock_report import render_fallback_report

    renderer = fallback_renderer or render_fallback_report
    if not settings.gemini_api_key:
        return AnalystReportResult(report=renderer(ticker, facts, news_items), used_llm=False)

    llm_client = client or GeminiReportClient(api_key=settings.gemini_api_key)
    try:
        return AnalystReportResult(report=llm_client.generate_report(ticker, facts, news_items), used_llm=True)
    except Exception:
        return AnalystReportResult(report=renderer(ticker, facts, news_items), used_llm=False)
