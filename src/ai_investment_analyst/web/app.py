from __future__ import annotations

from html import escape
import os
from secrets import compare_digest
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
import yfinance as yf

from ai_investment_analyst.analysis.stock_report import candidate_market_tickers
from ai_investment_analyst.analysis.stock_report import generate_stock_report

app = FastAPI(title="AI Investment Analyst")
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
SESSION_COOKIE_NAME = 'session'
SESSION_COOKIE_VALUE = 'authenticated'


class ReportRequest(BaseModel):
    ticker: str = Field(min_length=1)


class ReportResponse(BaseModel):
    ticker: str
    report: str
    report_html: str
    mode: str
    generated_at: str


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

    for heading, items in sections:
        body_parts.append(f'<section class="report-section"><h2>{escape(heading)}</h2>')
        bullet_items = [item[2:] for item in items if item.startswith('- ')]
        paragraph_items = [item for item in items if not item.startswith('- ')]
        for paragraph in paragraph_items:
            body_parts.append(f'<p>{escape(paragraph)}</p>')
        if bullet_items:
            body_parts.append('<ul>')
            for item in bullet_items:
                body_parts.append(f'<li>{escape(item)}</li>')
            body_parts.append('</ul>')
        body_parts.append('</section>')

    body_parts.append('</article>')
    return ''.join(body_parts)


def resolve_stock_name(ticker: str) -> str | None:
    for candidate in candidate_market_tickers(ticker):
        try:
            info = yf.Ticker(candidate).info or {}
        except Exception:
            continue
        for key in ('shortName', 'longName', 'displayName'):
            value = (info.get(key) or '').strip()
            if value:
                return value
    return None


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
        },
    )


@app.post('/login')
def login(request: Request, password: str = Form(...)):
    expected_password = get_web_login_password()
    if not expected_password:
        return RedirectResponse(url='/', status_code=303)
    if not compare_digest(password, expected_password):
        return TEMPLATES.TemplateResponse(
            request,
            'login.html',
            {
                'error': '密碼錯誤，請再試一次。',
            },
            status_code=401,
        )

    response = RedirectResponse(url='/', status_code=303)
    response.set_cookie(SESSION_COOKIE_NAME, SESSION_COOKIE_VALUE, httponly=True, samesite='lax')
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
