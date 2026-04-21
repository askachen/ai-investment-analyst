from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from ai_investment_analyst.analysis.stock_report import generate_stock_report

app = FastAPI(title="AI Investment Analyst")
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class ReportRequest(BaseModel):
    ticker: str = Field(min_length=1)


class ReportResponse(BaseModel):
    ticker: str
    report: str
    mode: str
    generated_at: str


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/', response_class=HTMLResponse)
def index(request: Request):
    return TEMPLATES.TemplateResponse(
        request,
        'index.html',
        {
            'result': None,
            'ticker': '',
        },
    )


@app.post('/api/report', response_model=ReportResponse)
def create_report(payload: ReportRequest):
    ticker = payload.ticker.strip()
    if not ticker:
        raise HTTPException(status_code=422, detail='ticker is required')
    report = generate_stock_report(ticker)
    mode = 'deterministic'
    return ReportResponse(
        ticker=ticker,
        report=report,
        mode=mode,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
