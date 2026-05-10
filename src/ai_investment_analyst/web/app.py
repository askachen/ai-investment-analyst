from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
from html import escape
import os
import re
from secrets import compare_digest
from pathlib import Path
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
import requests
import yfinance as yf

from ai_investment_analyst.analysis.data_quality import StockDataQuality, assess_stock_report_data_quality
from ai_investment_analyst.analysis.recommendation_confidence import derive_recommendation_confidence
from ai_investment_analyst.analysis.screener import calculate_total_score, get_strategy_profile, list_strategy_profiles
from ai_investment_analyst.analysis.stock_report import candidate_market_tickers
from ai_investment_analyst.analysis.stock_report import generate_stock_report, load_stock_report_context
from ai_investment_analyst.db.connection import get_connection
from ai_investment_analyst.db.screener_store import load_latest_screener_snapshot

app = FastAPI(title="AI Investment Analyst")
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
SESSION_COOKIE_NAME = 'session'
SESSION_COOKIE_VALUE = 'authenticated'
TWSE_NAME_URL = 'https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=json'
TPEX_NAME_URL = 'https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes'
BUILTIN_TAIWAN_STOCK_NAMES = {
    '1101': '台泥',
    '1216': '統一',
    '1303': '南亞',
    '2303': '聯電',
    '2308': '台達電',
    '2317': '鴻海',
    '2330': '台積電',
    '2382': '廣達',
    '2412': '中華電',
    '2454': '聯發科',
    '2603': '長榮',
    '2881': '富邦金',
    '2882': '國泰金',
    '3034': '聯詠',
    '3711': '日月光投控',
    '6505': '台塑化',
}


class ReportRequest(BaseModel):
    ticker: str = Field(min_length=1)


class ReportResponse(BaseModel):
    ticker: str
    report: str
    report_html: str
    mode: str
    generated_at: str


class ScreenerResultResponse(BaseModel):
    rank: int
    ticker: str
    display_name: str | None = None
    total_score: str
    reasons: list[str] = Field(default_factory=list)
    close_price: str | None = None
    factor_scores: dict[str, str] = Field(default_factory=dict)


class ScreenerStrategyResponse(BaseModel):
    key: str
    label: str
    description: str
    weights: dict[str, str] = Field(default_factory=dict)


class ScreenerSnapshotResponse(BaseModel):
    run_date: str | None = None
    generated_at: str | None = None
    universe_size: int | None = None
    candidate_count: int | None = None
    freshness_status: str = 'unknown'
    freshness_message: str = '等待最新批次。'
    strategy: ScreenerStrategyResponse | None = None
    strategies: list[ScreenerStrategyResponse] = Field(default_factory=list)
    results: list[ScreenerResultResponse] = Field(default_factory=list)


def render_report_html(report: str, display_title: str | None = None) -> str:
    lines = [line.strip() for line in report.splitlines()]
    title = display_title or 'AI 投資分析師報告'
    badges: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    known_headings = {
        '一句話投資主軸',
        '重點摘要',
        '重點摘要（條列）',
        '財務摘要表',
        '價格與技術面觀察',
        '基本面觀察',
        '估值觀察',
        '目標價推導',
        '新聞與市場催化',
        '利多催化',
        '中性觀察',
        '潛在風險',
        '分析師觀點',
        '風險提示',
        '投資建議',
        'Bull Case',
        'Base Case',
        'Bear Case',
        '結論',
    }
    current_heading = '內容摘要'
    current_items: list[str] = []

    def flush_section() -> None:
        nonlocal current_heading, current_items
        if current_items:
            sections.append((current_heading, current_items.copy()))
        current_items = []

    for line in lines:
        if not line:
            continue
        if line.startswith('【個股分析報告】'):
            if display_title is None:
                title = line.removeprefix('【個股分析報告】').strip() or title
            continue
        if line.startswith('投資評級：'):
            badges.append(f'<span class="badge badge-rating">{escape(line)}</span>')
            continue
        if line.startswith('信心等級：'):
            badges.append(f'<span class="badge badge-confidence">{escape(line)}</span>')
            continue
        if line in known_headings:
            flush_section()
            current_heading = line
            continue
        current_items.append(line)

    flush_section()

    scenario_heading_labels = {
        'Bull Case': '樂觀情境',
        'Base Case': '基準情境',
        'Bear Case': '保守情境',
    }

    def display_heading(heading: str) -> str:
        return scenario_heading_labels.get(heading, heading)

    def _extract_decimal_from_text(text: str, pattern: str) -> Decimal | None:
        match = re.search(pattern, text)
        if not match:
            return None
        try:
            return Decimal(match.group(1).replace(',', ''))
        except Exception:
            return None

    def _extract_latest_close_price(items: list[str]) -> Decimal | None:
        for item in items:
            if '最新收盤價' not in item:
                continue
            value = _extract_decimal_from_text(item, r'最新收盤價\s*([0-9][0-9,]*(?:\.[0-9]+)?)')
            if value is not None:
                return value
        return None

    def _extract_target_price(items: list[str]) -> Decimal | None:
        for item in items:
            value = _extract_decimal_from_text(item, r'目標價約\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*元')
            if value is not None:
                return value
        return None

    def _format_decimal(value: Decimal) -> str:
        quantized = value.quantize(Decimal('0.01')).normalize()
        text = format(quantized, 'f')
        if '.' in text:
            text = text.rstrip('0').rstrip('.')
        return text

    def _format_price_text(value: Decimal) -> str:
        return f'{value.quantize(Decimal("0.01"))} 元'

    def _format_upside_text(latest_close: Decimal, target_price: Decimal) -> str | None:
        if latest_close <= 0:
            return None
        upside = ((target_price - latest_close) / latest_close) * Decimal('100')
        sign = '+' if upside >= 0 else ''
        return f'{sign}{_format_decimal(upside.quantize(Decimal("0.1")))}%'

    insight_cards: list[tuple[str, str]] = []
    scenario_sections: list[tuple[str, list[str], list[str]]] = []
    observation_sections: list[tuple[str, str, list[str], list[str]]] = []
    analyst_takeaway: str | None = None
    risk_focus_items: list[str] = []
    quick_brief_cards: list[tuple[str, str]] = []
    latest_close_price: Decimal | None = None
    target_price: Decimal | None = None
    observation_tones = {
        '利多催化': 'bull',
        '中性觀察': 'neutral',
        '潛在風險': 'bear',
    }
    for heading, items in sections:
        paragraph_items = [item for item in items if not item.startswith('- ')]
        bullet_items = [item[2:] for item in items if item.startswith('- ')]
        if heading == '一句話投資主軸' and paragraph_items:
            insight_cards.append(('投資主軸', paragraph_items[0]))
        elif heading == '重點摘要（條列）':
            latest_close_price = _extract_latest_close_price(bullet_items)
        elif heading == '估值觀察':
            for item in paragraph_items:
                if item.startswith('評價標籤：'):
                    insight_cards.append(('評價標籤', item.removeprefix('評價標籤：').strip()))
                elif item.startswith('合理價區間：'):
                    insight_cards.append(('合理價區間', item))
        elif heading == '目標價推導' and paragraph_items:
            target_price = _extract_target_price(paragraph_items)
            insight_cards.append(('目標價推導', paragraph_items[0]))
        elif heading in {'分析師觀點', '投資建議', '結論'} and analyst_takeaway is None:
            analyst_takeaway = next((item for item in [*paragraph_items, *bullet_items] if item.strip()), None)
            if analyst_takeaway:
                quick_brief_cards.append(('分析師結論', analyst_takeaway))
        elif heading == '風險提示' and (bullet_items or paragraph_items):
            risk_focus_items = [item for item in [*bullet_items, *paragraph_items] if item.strip()]
            if risk_focus_items and not any(label == '潛在風險' for label, _ in quick_brief_cards):
                quick_brief_cards.append(('潛在風險', risk_focus_items[0]))
        elif heading in {'Bull Case', 'Base Case', 'Bear Case'}:
            scenario_sections.append((heading, bullet_items, paragraph_items))
        elif heading in observation_tones and (bullet_items or paragraph_items):
            observation_sections.append((heading, observation_tones[heading], bullet_items, paragraph_items))
            first_observation = next((item for item in [*bullet_items, *paragraph_items] if item.strip()), None)
            if first_observation and heading in {'利多催化', '潛在風險'}:
                quick_brief_cards.append((heading, first_observation))

    if latest_close_price is not None:
        insight_cards.append(('最新收盤價', _format_price_text(latest_close_price)))
    if latest_close_price is not None and target_price is not None:
        upside_text = _format_upside_text(latest_close_price, target_price)
        if upside_text:
            insight_cards.append(('目標價空間', upside_text))

    def _extract_financial_snapshot_cards(items: list[str]) -> list[tuple[str, str]]:
        cards: list[tuple[str, str]] = []
        for item in items:
            if not item.startswith('- '):
                continue
            label, _, value = item[2:].partition('：')
            label = label.strip()
            value = value.strip()
            if label and value:
                cards.append((label, value))
        return cards

    def _render_scenario_card(heading: str, bullet_items: list[str], paragraph_items: list[str]) -> str:
        tone = {
            'Bull Case': 'bull',
            'Base Case': 'base',
            'Bear Case': 'bear',
        }.get(heading, 'base')
        body_parts = [
            f'<article class="scenario-card scenario-card-{tone}"><div class="scenario-card-label">{escape(display_heading(heading))}</div>'
        ]
        for paragraph in paragraph_items:
            body_parts.append(f'<p>{escape(paragraph)}</p>')
        if bullet_items:
            body_parts.append('<ul>')
            for item in bullet_items:
                body_parts.append(f'<li>{escape(item)}</li>')
            body_parts.append('</ul>')
        body_parts.append('</article>')
        return ''.join(body_parts)

    def _render_observation_card(heading: str, tone: str, bullet_items: list[str], paragraph_items: list[str]) -> str:
        body_parts = [
            f'<article class="observation-card observation-card-{tone}"><div class="observation-card-label">{escape(display_heading(heading))}</div>'
        ]
        for paragraph in paragraph_items:
            body_parts.append(f'<p>{escape(paragraph)}</p>')
        if bullet_items:
            body_parts.append('<ul>')
            for item in bullet_items:
                body_parts.append(f'<li>{escape(item)}</li>')
            body_parts.append('</ul>')
        body_parts.append('</article>')
        return ''.join(body_parts)

    deduped_quick_brief_cards: list[tuple[str, str]] = []
    seen_quick_brief_labels: set[str] = set()
    for label, value in quick_brief_cards:
        if not value or label in seen_quick_brief_labels:
            continue
        deduped_quick_brief_cards.append((label, value))
        seen_quick_brief_labels.add(label)

    body_parts: list[str] = [f'<article class="report-card"><header class="report-header"><h1>{escape(title)}</h1>']
    if badges:
        body_parts.append(f'<div class="report-badges">{"".join(badges)}</div>')
    body_parts.append('</header>')

    if insight_cards:
        body_parts.append('<section class="report-insights" aria-label="投資重點速覽">')
        body_parts.append('<div class="report-insights-title">投資重點速覽</div>')
        body_parts.append('<div class="report-insights-grid">')
        for label, value in insight_cards:
            body_parts.append(
                f'<article class="insight-card"><span class="insight-label">{escape(label)}</span><strong>{escape(value)}</strong></article>'
            )
        body_parts.append('</div></section>')

    if deduped_quick_brief_cards:
        body_parts.append('<section class="quick-brief" aria-label="決策速讀">')
        body_parts.append('<div class="quick-brief-title">決策速讀</div>')
        body_parts.append('<div class="quick-brief-grid">')
        for label, value in deduped_quick_brief_cards:
            body_parts.append(
                f'<article class="quick-brief-card"><span class="quick-brief-label">{escape(label)}</span><strong>{escape(value)}</strong></article>'
            )
        body_parts.append('</div></section>')

    if analyst_takeaway:
        body_parts.append('<section class="analyst-takeaway" aria-label="分析師快速結論">')
        body_parts.append('<div class="analyst-takeaway-title">分析師快速結論</div>')
        body_parts.append(f'<p class="analyst-takeaway-text">{escape(analyst_takeaway)}</p>')
        body_parts.append('</section>')

    if risk_focus_items:
        body_parts.append('<section class="risk-focus" aria-label="風險提示重點">')
        body_parts.append('<div class="risk-focus-title">風險提示重點</div>')
        body_parts.append('<ul class="risk-focus-list">')
        for item in risk_focus_items:
            body_parts.append(f'<li>{escape(item)}</li>')
        body_parts.append('</ul></section>')

    if sections or scenario_sections or observation_sections:
        body_parts.append('<details class="report-details">')
        body_parts.append('<summary>展開完整研究細節</summary>')
        body_parts.append('<div class="report-details-body">')

        if scenario_sections:
            body_parts.append('<section class="scenario-overview" aria-label="三種情境推演">')
            body_parts.append('<div class="scenario-overview-title">三種情境推演</div>')
            body_parts.append('<div class="scenario-grid scenario-grid-overview">')
            for heading, bullet_items, paragraph_items in scenario_sections:
                body_parts.append(_render_scenario_card(heading, bullet_items, paragraph_items))
            body_parts.append('</div></section>')

        if observation_sections:
            body_parts.append('<section class="observation-radar" aria-label="投資觀察雷達">')
            body_parts.append('<div class="observation-radar-title">投資觀察雷達</div>')
            body_parts.append('<div class="observation-grid">')
            for heading, tone, bullet_items, paragraph_items in observation_sections:
                body_parts.append(_render_observation_card(heading, tone, bullet_items, paragraph_items))
            body_parts.append('</div></section>')

        if len(sections) > 1:
            body_parts.append('<nav class="report-nav" aria-label="報告章節快速導覽"><span class="report-nav-label">快速導覽</span><div class="report-nav-links">')
            for index, (heading, _) in enumerate(sections, start=1):
                body_parts.append(f'<a href="#section-{index}">{escape(display_heading(heading))}</a>')
            body_parts.append('</div></nav>')

        for index, (heading, items) in enumerate(sections, start=1):
            section_classes = ['report-section']
            if heading == '一句話投資主軸':
                section_classes.append('report-section-lead')
            body_parts.append(f'<section id="section-{index}" class="{" ".join(section_classes)}"><h2>{escape(display_heading(heading))}</h2>')
            bullet_items = [item[2:] for item in items if item.startswith('- ')]
            paragraph_items = [item for item in items if not item.startswith('- ')]
            for paragraph_index, paragraph in enumerate(paragraph_items):
                paragraph_class = ' class="lead-paragraph"' if heading == '一句話投資主軸' and paragraph_index == 0 else ''
                body_parts.append(f'<p{paragraph_class}>{escape(paragraph)}</p>')
            if heading == '財務摘要表':
                snapshot_cards = _extract_financial_snapshot_cards(items)
                if snapshot_cards:
                    body_parts.append('<div class="financial-snapshot-grid">')
                    for label, value in snapshot_cards:
                        body_parts.append(
                            f'<article class="financial-snapshot-card"><span class="financial-snapshot-label">{escape(label)}</span><strong class="financial-snapshot-value">{escape(value)}</strong></article>'
                        )
                    body_parts.append('</div>')
                elif bullet_items:
                    body_parts.append('<ul>')
                    for item in bullet_items:
                        body_parts.append(f'<li>{escape(item)}</li>')
                    body_parts.append('</ul>')
            elif heading in {'Bull Case', 'Base Case', 'Bear Case'}:
                body_parts.append('<div class="scenario-grid">')
                body_parts.append(_render_scenario_card(heading, bullet_items, paragraph_items))
                body_parts.append('</div>')
            elif bullet_items:
                body_parts.append('<ul>')
                for item in bullet_items:
                    body_parts.append(f'<li>{escape(item)}</li>')
                body_parts.append('</ul>')
            body_parts.append('</section>')

        body_parts.append('</div></details>')

    body_parts.append('</article>')
    return ''.join(body_parts)


def resolve_stock_name(ticker: str) -> str | None:
    if ticker.isdigit():
        chinese_name = lookup_taiwan_stock_name(ticker)
        if chinese_name:
            return chinese_name
        db_name = load_symbol_display_name_from_db(ticker)
        if db_name and db_name != ticker:
            return db_name
        builtin_name = lookup_builtin_taiwan_stock_name(ticker)
        if builtin_name:
            return builtin_name
    candidates = candidate_market_tickers(ticker)
    if ticker.isdigit():
        tw_symbol = f'{ticker}.TW'
        if tw_symbol in candidates:
            candidates = [tw_symbol] + [candidate for candidate in candidates if candidate != tw_symbol]
    for candidate in candidates:
        try:
            info = yf.Ticker(candidate).info or {}
        except Exception:
            continue
        for key in ('shortName', 'longName', 'displayName'):
            value = (info.get(key) or '').strip()
            if value:
                return value
    return None


@lru_cache(maxsize=1)
def _load_taiwan_stock_name_map() -> dict[str, str]:
    mapping: dict[str, str] = {}

    try:
        response = requests.get(TWSE_NAME_URL, timeout=20)
        response.raise_for_status()
        payload = response.json()
        for code, name, *_ in payload.get('data', []):
            if code and name:
                mapping[str(code).strip()] = str(name).strip()
    except Exception:
        pass

    try:
        response = requests.get(TPEX_NAME_URL, timeout=20)
        response.raise_for_status()
        payload = response.json()
        for row in payload:
            code = str(row.get('SecuritiesCompanyCode') or '').strip()
            name = str(row.get('CompanyName') or '').strip()
            if code and name:
                mapping[code] = name
    except Exception:
        pass

    return mapping


def lookup_taiwan_stock_name(ticker: str) -> str | None:
    return _load_taiwan_stock_name_map().get(ticker) or BUILTIN_TAIWAN_STOCK_NAMES.get(ticker)


def lookup_builtin_taiwan_stock_name(ticker: str) -> str | None:
    return BUILTIN_TAIWAN_STOCK_NAMES.get(ticker)


def load_symbol_display_name_from_db(ticker: str) -> str | None:
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(NULLIF(TRIM(local_name), ''), NULLIF(TRIM(name), ''))
                FROM symbols
                WHERE ticker = %s
                ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
                LIMIT 1
                """,
                (ticker,),
            )
            row = cur.fetchone()
    except Exception:
        return None
    if not row or not row[0]:
        return None
    return str(row[0]).strip()


def resolve_screener_display_name(ticker: str) -> str | None:
    if ticker.isdigit():
        chinese_name = lookup_taiwan_stock_name(ticker)
        if chinese_name:
            return chinese_name
        db_name = load_symbol_display_name_from_db(ticker)
        if db_name and db_name != ticker:
            return db_name
    return resolve_stock_name(ticker)


def build_stock_data_quality(ticker: str) -> StockDataQuality | None:
    try:
        context = load_stock_report_context(ticker)
    except Exception:
        return None
    return assess_stock_report_data_quality(context)


def serialize_stock_data_quality(quality: StockDataQuality | None) -> dict | None:
    return asdict(quality) if quality is not None else None


def build_stock_decision_card(report: str, data_quality: StockDataQuality | None = None) -> dict[str, object]:
    lines = [line.strip() for line in report.splitlines() if line.strip()]
    rating = next((line.removeprefix('投資評級：').strip() for line in lines if line.startswith('投資評級：')), '待觀察')
    report_confidence = next((line.removeprefix('信心等級：').strip() for line in lines if line.startswith('信心等級：')), None)

    thesis = '請閱讀完整報告確認投資主軸。'
    for index, line in enumerate(lines):
        if line == '一句話投資主軸' and index + 1 < len(lines):
            thesis = lines[index + 1]
            break
    if thesis == '請閱讀完整報告確認投資主軸。':
        thesis = next((line for line in lines if line not in {'分析師觀點', '投資建議', '結論'} and not line.startswith(('【', '投資評級：', '信心等級：'))), thesis)

    risk_line = next((line[2:] for line in lines if line.startswith('- ') and any(keyword in line for keyword in ('風險', '轉弱', '競爭', '修正'))), None)
    if risk_line is None:
        risk_line = next((line for line in lines if any(keyword in line for keyword in ('潛在風險', 'Bear Case', '風險提示'))), '尚未列出明確風險，需保守解讀。')

    has_core_signals = any(keyword in report for keyword in ('財務摘要表', '估值觀察', '目標價推導', '價格與技術面觀察', '基本面觀察'))
    has_clear_risk_factors = any(keyword in report for keyword in ('潛在風險', '風險提示', 'Bear Case'))
    recommendation_confidence = derive_recommendation_confidence(
        data_quality,
        report_confidence=report_confidence,
        has_core_signals=has_core_signals,
        has_clear_risk_factors=has_clear_risk_factors,
    )

    next_step = '先檢查資料可信度與風險，再決定是否加入觀察清單。'
    if rating in {'買進', '加碼'}:
        next_step = '先確認風險與資料品質，再評估分批進場或加入觀察清單。'
    elif rating in {'賣出', '減碼'}:
        next_step = '優先確認下修理由，避免只因短線波動做決策。'

    return {
        'rating': rating,
        'thesis': thesis,
        'risk': risk_line,
        'next_step': next_step,
        'confidence': asdict(recommendation_confidence),
    }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_snapshot_date(snapshot: dict) -> date | None:
    generated_at = snapshot.get('generated_at')
    if generated_at:
        try:
            parsed = datetime.fromisoformat(str(generated_at).replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).date()
        except Exception:
            pass
    run_date = snapshot.get('run_date')
    if run_date:
        try:
            return date.fromisoformat(str(run_date)[:10])
        except Exception:
            pass
    return None


def describe_screener_snapshot_freshness(snapshot: dict) -> tuple[str, str]:
    snapshot_date = _parse_snapshot_date(snapshot)
    if snapshot_date is None:
        return 'unknown', '等待最新批次。'
    age_days = max((_utc_now().date() - snapshot_date).days, 0)
    if age_days == 0:
        return 'fresh', '資料今日已更新。'
    if age_days == 1:
        return 'fresh', '資料為昨日批次。'
    return 'stale', f'資料已 {age_days} 天未更新，請檢查每日批次。'


def _with_freshness_metadata(snapshot: dict) -> dict:
    status, message = describe_screener_snapshot_freshness(snapshot)
    return {
        **snapshot,
        'freshness_status': snapshot.get('freshness_status') or status,
        'freshness_message': snapshot.get('freshness_message') or message,
    }


def enrich_screener_snapshot(snapshot: dict) -> dict:
    enriched_results = []
    for result in snapshot.get('results', []):
        item = dict(result)
        item['display_name'] = resolve_screener_display_name(item['ticker'])
        enriched_results.append(item)
    return _with_freshness_metadata({
        **snapshot,
        'results': enriched_results,
    })


def _decimal_factor_scores(result: dict) -> dict[str, Decimal]:
    factor_scores = result.get('factor_scores') or {}
    decimals: dict[str, Decimal] = {}
    for key, value in factor_scores.items():
        try:
            decimals[key] = Decimal(str(value))
        except Exception:
            continue
    return decimals


def rerank_screener_snapshot(snapshot: dict, strategy_key: str) -> dict | None:
    active_strategy = get_strategy_profile(strategy_key)
    reranked_results = []
    for result in snapshot.get('results', []):
        factor_scores = _decimal_factor_scores(result)
        if not factor_scores:
            return None
        item = dict(result)
        item['factor_scores'] = {key: str(value) for key, value in factor_scores.items()}
        item['total_score'] = str(calculate_total_score(factor_scores, active_strategy.weights))
        reranked_results.append(item)
    reranked_results.sort(
        key=lambda item: (
            Decimal(str(item.get('total_score', '0'))),
            Decimal(str((item.get('factor_scores') or {}).get('momentum', '0'))),
            str(item.get('ticker', '')),
        ),
        reverse=True,
    )
    for index, item in enumerate(reranked_results, start=1):
        item['rank'] = index
    return {
        **snapshot,
        'strategy': _serialize_strategy(active_strategy.key),
        'strategies': snapshot.get('strategies') or _list_serialized_strategies(),
        'candidate_count': len(reranked_results),
        'results': reranked_results,
    }


def _serialize_strategy(strategy_key: str) -> dict[str, str | dict[str, str]]:
    strategy = get_strategy_profile(strategy_key)
    weights = {
        key: f'{int((weight * 100).quantize(Decimal("1")))}%'
        for key, weight in strategy.weights.items()
    }
    return {
        'key': strategy.key,
        'label': strategy.label,
        'description': strategy.description,
        'weights': weights,
    }


def _list_serialized_strategies() -> list[dict[str, str | dict[str, str]]]:
    return [_serialize_strategy(strategy.key) for strategy in list_strategy_profiles()]


def get_web_login_username() -> str:
    return os.getenv('WEB_LOGIN_USERNAME', 'admin').strip() or 'admin'


def get_web_login_password() -> str:
    return os.getenv('WEB_LOGIN_PASSWORD', '').strip()


def is_auth_enabled() -> bool:
    return bool(get_web_login_password())


def is_authenticated(request: Request) -> bool:
    return request.cookies.get(SESSION_COOKIE_NAME) == SESSION_COOKIE_VALUE


def require_auth_for_page(request: Request):
    if is_auth_enabled() and not is_authenticated(request):
        return RedirectResponse(url='/login', status_code=303)
    return None


def require_auth_for_api(request: Request):
    if is_auth_enabled() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail='authentication required')


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/login', response_class=HTMLResponse)
def login_page(request: Request):
    if not is_auth_enabled():
        return RedirectResponse(url='/', status_code=303)
    return TEMPLATES.TemplateResponse(
        request,
        'login.html',
        {
            'error': None,
            'username_placeholder': get_web_login_username(),
        },
    )


@app.post('/login')
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    expected_username = get_web_login_username()
    expected_password = get_web_login_password()
    if not expected_password:
        return RedirectResponse(url='/', status_code=303)
    if not compare_digest(username.strip(), expected_username) or not compare_digest(password, expected_password):
        return TEMPLATES.TemplateResponse(
            request,
            'login.html',
            {
                'error': '帳號或密碼錯誤，請再試一次。',
                'username_placeholder': expected_username,
            },
            status_code=401,
        )

    response = RedirectResponse(url='/', status_code=303)
    response.set_cookie(SESSION_COOKIE_NAME, SESSION_COOKIE_VALUE, httponly=True, samesite='lax')
    return response


@app.post('/logout')
def logout(request: Request):
    redirect_target = '/login' if is_auth_enabled() else '/'
    response = RedirectResponse(url=redirect_target, status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME, httponly=True, samesite='lax')
    return response


@app.get('/', response_class=HTMLResponse)
def index(request: Request):
    auth_redirect = require_auth_for_page(request)
    if auth_redirect:
        return auth_redirect
    return TEMPLATES.TemplateResponse(
        request,
        'index.html',
        {
            'result': None,
            'ticker': '',
            'show_logout': is_auth_enabled() and is_authenticated(request),
        },
    )


@app.get('/stocks/{ticker}', response_class=HTMLResponse)
def stock_detail_page(request: Request, ticker: str):
    auth_redirect = require_auth_for_page(request)
    if auth_redirect:
        return auth_redirect

    normalized_ticker = ticker.strip()
    report = generate_stock_report(normalized_ticker)
    stock_name = resolve_stock_name(normalized_ticker)
    display_title = f'{normalized_ticker} {stock_name}' if stock_name else normalized_ticker
    report_html = render_report_html(report, display_title=display_title)
    data_quality_obj = build_stock_data_quality(normalized_ticker)
    data_quality = serialize_stock_data_quality(data_quality_obj)
    decision_card = build_stock_decision_card(report, data_quality_obj)
    return TEMPLATES.TemplateResponse(
        request,
        'stock_detail.html',
        {
            'ticker': normalized_ticker,
            'display_title': display_title,
            'report_html': report_html,
            'data_quality': data_quality,
            'decision_card': decision_card,
            'show_logout': is_auth_enabled() and is_authenticated(request),
        },
    )


@app.post('/api/report', response_model=ReportResponse)
def create_report(payload: ReportRequest, request: Request):
    require_auth_for_api(request)
    ticker = payload.ticker.strip()
    if not ticker:
        raise HTTPException(status_code=422, detail='ticker is required')
    report = generate_stock_report(ticker)
    stock_name = resolve_stock_name(ticker)
    display_title = f'{ticker} {stock_name}' if stock_name else ticker
    mode = 'deterministic'
    return ReportResponse(
        ticker=ticker,
        report=report,
        report_html=render_report_html(report, display_title=display_title),
        mode=mode,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@app.get('/api/screener/latest', response_model=ScreenerSnapshotResponse)
def get_latest_screener(request: Request, strategy: str = 'balanced'):
    require_auth_for_api(request)
    active_strategy = get_strategy_profile(strategy)
    try:
        snapshot = load_latest_screener_snapshot(active_strategy.key)
        if snapshot is None and active_strategy.key != 'balanced':
            balanced_snapshot = load_latest_screener_snapshot('balanced')
            if balanced_snapshot is not None:
                snapshot = rerank_screener_snapshot(balanced_snapshot, active_strategy.key)
    except Exception:
        snapshot = None
    if snapshot is None:
        return ScreenerSnapshotResponse(
            strategy=ScreenerStrategyResponse(**_serialize_strategy(active_strategy.key)),
            strategies=[ScreenerStrategyResponse(**item) for item in _list_serialized_strategies()],
        )
    enriched_snapshot = enrich_screener_snapshot(snapshot)
    enriched_snapshot.setdefault('strategy', _serialize_strategy(active_strategy.key))
    enriched_snapshot.setdefault('strategies', _list_serialized_strategies())
    return ScreenerSnapshotResponse(**enriched_snapshot)
