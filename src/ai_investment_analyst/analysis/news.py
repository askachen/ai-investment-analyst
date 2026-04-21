from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from opencc import OpenCC
import requests
import yfinance as yf

from ai_investment_analyst.config import settings

_TRADITIONAL_CONVERTER = OpenCC("s2t")


@dataclass(frozen=True)
class NewsItem:
    title: str
    publisher: str
    link: str
    published_at: str
    summary: str


def normalize_yfinance_news(raw_items: list[dict[str, Any]], limit: int = 5) -> list[NewsItem]:
    items: list[NewsItem] = []
    for raw in raw_items:
        content = raw.get("content") or raw
        title = content.get("title")
        if not title:
            continue
        canonical = content.get("canonicalUrl") or {}
        provider = content.get("provider") or {}
        items.append(
            NewsItem(
                title=title,
                publisher=provider.get("displayName") or content.get("publisher") or "Unknown",
                link=canonical.get("url") or content.get("link") or "",
                published_at=content.get("pubDate") or content.get("published_at") or "",
                summary=content.get("summary") or content.get("description") or "",
            )
        )
        if len(items) >= limit:
            break
    return items


def fetch_ticker_news(
    ticker: str,
    count: int = 5,
    tab: str = "news",
    ticker_factory: Callable[[str], Any] | None = None,
) -> list[NewsItem]:
    factory = ticker_factory or yf.Ticker
    raw_items = factory(ticker).get_news(count=count, tab=tab) or []
    return normalize_yfinance_news(raw_items, limit=count)


def _translate_text_via_google_endpoint(text: str) -> str:
    if not text:
        return text
    try:
        response = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "auto", "tl": "zh-TW", "dt": "t", "q": text},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        translated = "".join(part[0] for part in payload[0] if part and part[0])
        return translated or text
    except Exception:
        return text


def _translate_text_with_gemini(text: str) -> str:
    if not text:
        return text
    if not settings.gemini_api_key:
        return _translate_text_via_google_endpoint(text)
    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}",
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": (
                                    "請將以下財經新聞內容翻譯成自然、精簡的繁體中文。"
                                    "保留原意，不要添加評論，不要使用簡體中文。\n\n"
                                    f"{text}"
                                )
                            }
                        ]
                    }
                ]
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        candidates = payload.get("candidates") or []
        for candidate in candidates:
            parts = ((candidate.get("content") or {}).get("parts") or [])
            for part in parts:
                translated = part.get("text", "").strip()
                if translated:
                    return translated
    except Exception:
        return _translate_text_via_google_endpoint(text)
    return _translate_text_via_google_endpoint(text)


def summarize_news_in_traditional_chinese(
    items: list[NewsItem],
    translator: Callable[[str], str] | None = None,
) -> list[NewsItem]:
    translate = translator or _translate_text_with_gemini
    translated_items: list[NewsItem] = []
    for item in items:
        translated_title = _TRADITIONAL_CONVERTER.convert(translate(item.title))
        translated_summary = _TRADITIONAL_CONVERTER.convert(translate(item.summary))
        translated_items.append(
            NewsItem(
                title=translated_title,
                publisher=item.publisher,
                link=item.link,
                published_at=item.published_at,
                summary=translated_summary,
            )
        )
    return translated_items


def compress_news_item_to_one_liner(item: NewsItem, max_len: int = 76) -> str:
    summary = item.summary.split("。", 1)[0].strip()
    line = f"- {item.title}：{summary}"
    if len(line) <= max_len:
        return line
    allowed = max_len - 1
    return line[:allowed].rstrip() + "…"


def rewrite_news_as_analyst_bullets(items: list[NewsItem]) -> list[str]:
    bullets: list[str] = []
    for item in items[:3]:
        tone = "市場焦點偏多" if any(keyword in f"{item.title} {item.summary}" for keyword in ["上調", "續強", "成長", "需求", "獲利", "利多"]) else "市場焦點中性"
        one_liner = compress_news_item_to_one_liner(item, max_len=68).lstrip("- ")
        bullets.append(f"- {tone}：{one_liner}")
    return bullets


def classify_news_catalysts(items: list[NewsItem]) -> dict[str, list[str]]:
    groups = {"positive": [], "neutral": [], "risk": []}
    positive_keywords = ["上調", "續強", "成長", "需求", "獲利", "利多"]
    risk_keywords = ["風險", "不確定", "地緣政治", "下修", "壓力", "偏高"]
    for item in items[:5]:
        text = f"{item.title} {item.summary}"
        bullet = compress_news_item_to_one_liner(item)
        has_positive = any(keyword in text for keyword in positive_keywords)
        has_risk = any(keyword in text for keyword in risk_keywords)
        if has_positive and not has_risk:
            groups["positive"].append(bullet)
        elif has_risk and not has_positive:
            groups["risk"].append(bullet)
        else:
            groups["neutral"].append(bullet)
    return groups
