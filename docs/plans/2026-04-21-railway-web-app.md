# Railway Web Investment Analyst Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 將目前的 `ai-investment-analyst` 包裝成可部署到 Railway 的網站，讓一般使用者能在網頁輸入股票代號並取得投資分析報告。

**Architecture:** 後端採 Python Web API（FastAPI）包住現有分析引擎，前端採單頁應用（建議 Next.js 或簡化版 Jinja/HTMX）。部署目標為 Railway 單服務起步版；如後續要加背景排程、快取、使用者帳號，可再拆 service。資料來源初期沿用目前的 yfinance + 可選 DB fallback 設計，以降低首版部署複雜度。

**Tech Stack:** FastAPI, Uvicorn, Pydantic, Python 3.11, Railway, optional PostgreSQL on Railway, existing ai-investment-analyst core modules, optional Next.js/Tailwind for frontend.

---

## Product Scope (MVP)

### User-facing capabilities
1. 輸入股票代號（如 `2330`, `TSM`, `AAPL`）
2. 產生繁體中文投資分析報告
3. 顯示 loading 狀態
4. 顯示最近一份報告結果
5. 失敗時顯示可理解錯誤訊息

### Nice-to-have after MVP
1. 報告分享連結
2. 最近查詢紀錄
3. LLM / fallback 模式標示
4. 使用者登入
5. 限流與 API key 配額保護
6. 背景任務與報告快取

---

## Recommended deployment shape

### Option A — Fastest MVP
- **Single Railway service**
- FastAPI backend serves API + simple server-rendered frontend
- Optional Railway Postgres
- 適合先讓你老婆與朋友試用

### Option B — Better UX
- **Frontend:** Next.js on Railway
- **Backend:** FastAPI API on Railway
- **DB:** Railway Postgres
- 適合正式產品化、未來可加會員與歷史紀錄

**Recommendation:** 先做 **Option A**，因為你現在已經有成熟 Python 分析核心，可以最快上線。等使用者真的開始用，再拆前後端。

---

## Repository layout recommendation

### If new repo is created for web product

```text
investment-analyst-web/
  backend/
    pyproject.toml
    src/
      web_app/
        main.py
        api/
        services/
        templates/
        static/
    tests/
  packages/
    ai_investment_analyst_core/   # optional extracted shared core later
  railway.json                     # optional
  Procfile                         # optional if needed
  README.md
  .env.example
```

### Faster alternative
直接在現有 repo 內新增：

```text
src/ai_investment_analyst/web/
  app.py
  templates/
  static/
```

這樣最快，但 repo 會逐漸變成 monolith。

---

## Environment variables for Railway

Required:
- `PORT` (Railway injects automatically)
- `GEMINI_API_KEY`

Optional:
- `DATABASE_URL`
- `FINMIND_API_TOKEN`
- `FINLAB_API_KEY`

Potential future:
- `APP_ENV=production`
- `RATE_LIMIT_PER_MINUTE`
- `SESSION_SECRET`

---

## MVP API contract

### `GET /health`
Returns:
```json
{"status":"ok"}
```

### `POST /api/report`
Request:
```json
{"ticker":"2330"}
```

Response:
```json
{
  "ticker": "2330",
  "report": "...full report text...",
  "mode": "llm" | "fallback",
  "generated_at": "2026-04-21T09:00:00Z"
}
```

### `GET /`
- 顯示輸入框與最近一次結果
- 可直接表單送出

---

## UX recommendation

### Page sections
1. Hero title: `AI 投資分析師`
2. 股票代號輸入框
3. 提交按鈕：`開始分析`
4. Example chips: `2330`, `TSM`, `AAPL`
5. 分析結果卡片
6. 風險免責聲明

### Tone
- 面向一般人
- 語言用繁體中文
- 明確聲明：**非投資建議，僅供參考**

---

## Implementation tasks

### Task 1: Add web framework and health endpoint

**Objective:** 建立最小可啟動的 Railway-compatible web service。

**Files:**
- Modify: `pyproject.toml`
- Create: `src/ai_investment_analyst/web/app.py`
- Create: `tests/web/test_health.py`
- Create: `.env.example` (if missing / update)

**Step 1: Write failing test**
```python
from fastapi.testclient import TestClient
from ai_investment_analyst.web.app import app


def test_health_returns_ok():
    client = TestClient(app)
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
```

**Step 2: Run test to verify failure**
Run: `pytest tests/web/test_health.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**
- add `fastapi`, `uvicorn`
- create app
- add `/health`

**Step 4: Run test to verify pass**
Run: `pytest tests/web/test_health.py -v`
Expected: PASS

---

### Task 2: Add report generation API endpoint

**Objective:** 將現有 `generate_stock_report()` 包成 HTTP API。

**Files:**
- Create: `tests/web/test_report_api.py`
- Modify: `src/ai_investment_analyst/web/app.py`

**Step 1: Write failing test**
```python
def test_report_api_returns_report(monkeypatch):
    from fastapi.testclient import TestClient
    from ai_investment_analyst.web.app import app

    monkeypatch.setattr(
        'ai_investment_analyst.web.app.generate_stock_report',
        lambda ticker: 'mock report'
    )

    client = TestClient(app)
    response = client.post('/api/report', json={'ticker': '2330'})
    assert response.status_code == 200
    assert response.json()['ticker'] == '2330'
    assert response.json()['report'] == 'mock report'
```

**Step 2: Run test to verify failure**
Run: `pytest tests/web/test_report_api.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**
- add request/response schema
- add `/api/report`
- validate blank ticker

**Step 4: Run test to verify pass**
Run: `pytest tests/web/test_report_api.py -v`
Expected: PASS

---

### Task 3: Add simple web UI

**Objective:** 做一個你老婆和朋友打開就能用的頁面。

**Files:**
- Create: `src/ai_investment_analyst/web/templates/index.html`
- Modify: `src/ai_investment_analyst/web/app.py`
- Create: `tests/web/test_index_page.py`

**Step 1: Write failing test**
- verify GET `/` returns HTML containing form and input name `ticker`

**Step 2: Run test to verify failure**
Run: `pytest tests/web/test_index_page.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**
- server-rendered page with form
- submit to same page or JS call `/api/report`
- show result panel

**Step 4: Run test to verify pass**
Run: `pytest tests/web/test_index_page.py -v`
Expected: PASS

---

### Task 4: Add Railway startup config

**Objective:** 確保專案能直接部署到 Railway。

**Files:**
- Create: `Procfile` or `railway.json`
- Modify: `README.md`
- Create: `tests/web/test_import_app.py`

**Implementation notes:**
- command example:
```bash
web: uvicorn ai_investment_analyst.web.app:app --host 0.0.0.0 --port ${PORT:-8000}
```
- README 要寫：
  - local run
  - Railway env vars
  - deploy steps

---

### Task 5: Add graceful error handling and disclaimer

**Objective:** 對一般使用者友善，避免 500 與技術堆疊暴露。

**Files:**
- Modify: `src/ai_investment_analyst/web/app.py`
- Modify: `src/ai_investment_analyst/web/templates/index.html`
- Create: `tests/web/test_error_handling.py`

**Requirements:**
- invalid ticker returns friendly error
- empty ticker blocked
- page shows disclaimer: `本內容僅供參考，不構成投資建議`

---

### Task 6: Optional persistent history

**Objective:** 若要讓你老婆和她朋友能回看歷史查詢，加入簡單儲存層。

**Files:**
- Create: `src/ai_investment_analyst/web/history_store.py`
- Create: `tests/web/test_history_store.py`

**Recommendation:** MVP 可以先不做。

---

## Railway deployment steps

1. 在 GitHub 建新 repo
2. push code
3. 到 Railway 建立新 project
4. connect GitHub repo
5. set env vars:
   - `GEMINI_API_KEY`
   - optionally `DATABASE_URL`
6. deploy
7. verify:
   - `/health`
   - homepage load
   - submit `2330`

---

## Product recommendations before public sharing

1. 加上免責聲明
2. 加上 rate limiting
3. 記錄 error logs
4. 避免把 API key 暴露到前端
5. 對 Gemini 429 做 fallback（你現在已經有核心 fallback，可直接沿用）

---

## My recommendation

**是，可以做，而且很適合做成網站。**

最務實的做法是：
- 你開一個新的 GitHub repo
- 我直接幫你做 **FastAPI + 簡單前端 + Railway deploy config**
- 第一版先讓你老婆和她朋友能輸入股票代號拿報告
- 之後再加使用者帳號、歷史查詢、付費功能
