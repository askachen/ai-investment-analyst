from __future__ import annotations

from functools import lru_cache
from html import escape
import os
from secrets import compare_digest
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
import requests
import yfinance as yf

from ai_investment_analyst.analysis.screener import get_strategy_profile, list_strategy_profiles
from ai_investment_analyst.analysis.stock_report import candidate_market_tickers
from ai_investment_analyst.analysis.stock_report import generate_stock_report
from ai_investment_analyst.db.connection import get_connection
from ai_investment_analyst.db.screener_store import load_latest_screener_snapshot

app = FastAPI(title="AI Investment Analyst")
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
SESSION_COOKIE_NAME = 'session'
SESSION_COOKIE_VALUE = 'authenticated'
TWSE_NAME_URL = 'https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=json'
TPEX_NAME_URL = 'https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes'


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


class ScreenerSnapshotResponse(BaseModel):
    run_date: str | None = None
    generated_at: str | None = None
    universe_size: int | None = None
    candidate_count: int | None = None
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

    body_parts: list[str] = [f'<article class="report-card"><header class="report-header"><h1>{escape(title)}</h1>']
    if badges:
        body_parts.append(f'<div class="report-badges">{"".join(badges)}</div>')
    body_parts.append('</header>')

    if len(sections) > 1:
        body_parts.append('<nav class="report-nav" aria-label="報告章節快速導覽"><span class="report-nav-label">快速導覽</span><div class="report-nav-links">')
        for index, (heading, _) in enumerate(sections, start=1):
            body_parts.append(f'<a href="#section-{index}">{escape(heading)}</a>')
        body_parts.append('</div></nav>')

    for index, (heading, items) in enumerate(sections, start=1):
        section_classes = ['report-section']
        if heading == '一句話投資主軸':
            section_classes.append('report-section-lead')
        body_parts.append(f'<section id="section-{index}" class="{" ".join(section_classes)}"><h2>{escape(heading)}</h2>')
        bullet_items = [item[2:] for item in items if item.startswith('- ')]
        paragraph_items = [item for item in items if not item.startswith('- ')]
        for paragraph_index, paragraph in enumerate(paragraph_items):
            paragraph_class = ' class="lead-paragraph"' if heading == '一句話投資主軸' and paragraph_index == 0 else ''
            body_parts.append(f'<p{paragraph_class}>{escape(paragraph)}</p>')
        if bullet_items:
            body_parts.append('<ul>')
            for item in bullet_items:
                body_parts.append(f'<li>{escape(item)}</li>')
            body_parts.append('</ul>')
        body_parts.append('</section>')

    body_parts.append('</article>')
    return ''.join(body_parts)


def resolve_stock_name(ticker: str) -> str | None:
    if ticker.isdigit():
        chinese_name = lookup_taiwan_stock_name(ticker)
        if chinese_name:
            return chinese_name
        db_name = load_symbol_display_name_from_db(ticker)
        if db_name:
            return db_name
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
    return _load_taiwan_stock_name_map().get(ticker)


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
        if db_name:
            return db_name
    return resolve_stock_name(ticker)


def enrich_screener_snapshot(snapshot: dict) -> dict:
    enriched_results = []
    for result in snapshot.get('results', []):
        item = dict(result)
        item['display_name'] = resolve_screener_display_name(item['ticker'])
        enriched_results.append(item)
    return {
        **snapshot,
        'results': enriched_results,
    }


def _serialize_strategy(strategy_key: str) -> dict[str, str]:
    strategy = get_strategy_profile(strategy_key)
    return {
        'key': strategy.key,
        'label': strategy.label,
        'description': strategy.description,
    }


def _list_serialized_strategies() -> list[dict[str, str]]:
    return [
        {
            'key': strategy.key,
            'label': strategy.label,
            'description': strategy.description,
        }
        for strategy in list_strategy_profiles()
    ]


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
    return TEMPLATES.TemplateResponse(
        request,
        'stock_detail.html',
        {
            'ticker': normalized_ticker,
            'display_title': display_title,
            'report_html': report_html,
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
