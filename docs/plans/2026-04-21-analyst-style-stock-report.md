# Analyst-Style Stock Report Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 讓 `ai-investment-analyst` 能輸出更像真人分析師撰寫的個股分析報告，整合價格、月營收、財報摘要、近期新聞與 LLM 觀點。

**Architecture:** 將現有 `stock_report.py` 從單一函式擴充為「資料彙整層 + 新聞抓取層 + LLM 生成層 + deterministic fallback」。報告生成流程先從資料庫與 yfinance 取得結構化資料，再組 prompt 給 Gemini；若未配置 API 或呼叫失敗，仍能輸出高品質規則式報告。

**Tech Stack:** Python 3.11、pytest、requests、yfinance、Gemini REST API、現有 PostgreSQL schema。

---

### Task 1: 建立報告輸出契約測試

**Objective:** 先鎖定新的報告格式與內容要求，確保後續重構有明確驗收標準。

**Files:**
- Create: `tests/analysis/test_stock_report.py`
- Modify: `src/ai_investment_analyst/analysis/stock_report.py`

**Step 1: Write failing test**
- 建立一個不碰資料庫的 pure unit test。
- 測試新的報告必須包含：標題、投資評級/傾向、重點摘要、價格觀察、基本面觀察、新聞與風險、結論。
- 用假資料 context 驗證輸出結構。

**Step 2: Run test to verify failure**

Run: `pytest tests/analysis/test_stock_report.py::test_generate_stock_report_includes_analyst_sections -v`
Expected: FAIL

**Step 3: Write minimal implementation**
- 在 `stock_report.py` 新增可接受預先組好的 context/依賴注入入口，先讓格式過關。

**Step 4: Run test to verify pass**

Run: `pytest tests/analysis/test_stock_report.py::test_generate_stock_report_includes_analyst_sections -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/analysis/test_stock_report.py src/ai_investment_analyst/analysis/stock_report.py
git commit -m "test: define analyst-style stock report contract"
```

### Task 2: 抽出結構化報告資料模型

**Objective:** 將價格、營收、財報、新聞、風險訊號整理成明確 dataclass，讓 LLM 與 fallback 共用同一份輸入。

**Files:**
- Modify: `src/ai_investment_analyst/analysis/stock_report.py`
- Create: `tests/analysis/test_stock_report_context.py`

**Step 1: Write failing test**
- 測試 `build_report_facts(...)` 類型函式會產出：
  - price momentum
  - revenue trend summary
  - financial snapshot
  - risk flags
  - key bullet points

**Step 2: Run test to verify failure**

Run: `pytest tests/analysis/test_stock_report_context.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**
- 新增 dataclass 與 pure helper functions。
- 儘量讓文字判斷集中在 helper，不散落在主流程。

**Step 4: Run test to verify pass**

Run: `pytest tests/analysis/test_stock_report_context.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/analysis/test_stock_report_context.py src/ai_investment_analyst/analysis/stock_report.py
git commit -m "feat: add structured report facts builder"
```

### Task 3: 新增 yfinance 新聞抓取器

**Objective:** 利用 `yfinance.Ticker.get_news()` 抓取個股新聞並轉成穩定格式。

**Files:**
- Create: `src/ai_investment_analyst/analysis/news.py`
- Create: `tests/analysis/test_news.py`
- Modify: `src/ai_investment_analyst/analysis/__init__.py`

**Step 1: Write failing test**
- 對 adapter 做 unit test，不實際打網路。
- 驗證 raw news payload 會被轉成統一欄位：title, publisher, published_at, summary, link。
- 驗證能限制筆數與忽略缺欄位資料。

**Step 2: Run test to verify failure**

Run: `pytest tests/analysis/test_news.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**
- 建立 `NewsItem` dataclass。
- 建立 `normalize_yfinance_news(...)` 與 `fetch_ticker_news(...)`。

**Step 4: Run test to verify pass**

Run: `pytest tests/analysis/test_news.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/analysis/test_news.py src/ai_investment_analyst/analysis/news.py src/ai_investment_analyst/analysis/__init__.py
git commit -m "feat: add yfinance news adapter"
```

### Task 4: 新增 Gemini 報告生成 client 與 fallback

**Objective:** 讓專案可使用 `.env` 中的 `GEMINI_API_KEY` 呼叫 Gemini 產生更像真人分析師的敘事；失敗時使用 deterministic fallback。

**Files:**
- Create: `src/ai_investment_analyst/analysis/llm.py`
- Create: `tests/analysis/test_llm.py`
- Modify: `src/ai_investment_analyst/config.py`

**Step 1: Write failing test**
- 測試 settings 會讀到 `GEMINI_API_KEY`
- 測試 prompt builder 會把 facts/news 組進請求 payload
- 測試 API 無 key 或 request 失敗時，會回 fallback mode 而不是 crash

**Step 2: Run test to verify failure**

Run: `pytest tests/analysis/test_llm.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**
- 新增 `GeminiReportClient`
- 使用 `requests.post` 呼叫 Gemini REST API
- 定義 `generate_analyst_report(...)` 與 fallback 行為

**Step 4: Run test to verify pass**

Run: `pytest tests/analysis/test_llm.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/analysis/test_llm.py src/ai_investment_analyst/analysis/llm.py src/ai_investment_analyst/config.py
git commit -m "feat: add Gemini report generation with fallback"
```

### Task 5: 串接完整報告流程

**Objective:** 把資料庫 context、新聞與 LLM/fallback 串成正式 `generate_stock_report()` 流程。

**Files:**
- Modify: `src/ai_investment_analyst/analysis/stock_report.py`
- Modify: `scripts/generate_stock_report.py`
- Modify: `README.md`
- Create: `tests/analysis/test_generate_stock_report_flow.py`

**Step 1: Write failing test**
- 驗證主流程會：
  - 讀取 DB context
  - 取新聞
  - 組 facts
  - 優先走 LLM
  - LLM 不可用時 fallback
- 使用 monkeypatch/stub，不打 DB、不打網路。

**Step 2: Run test to verify failure**

Run: `pytest tests/analysis/test_generate_stock_report_flow.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**
- 重構 `generate_stock_report(ticker)`
- 在 script 支援 `python scripts/generate_stock_report.py 2330`
- README 補 usage 與環境變數說明

**Step 4: Run test to verify pass**

Run: `pytest tests/analysis/test_generate_stock_report_flow.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/analysis/test_generate_stock_report_flow.py src/ai_investment_analyst/analysis/stock_report.py scripts/generate_stock_report.py README.md
git commit -m "feat: integrate analyst-style stock report pipeline"
```

### Task 6: 執行完整測試與示範驗證

**Objective:** 確認整體功能可用，並產出一份示範報告。

**Files:**
- Modify: none required unless issues found

**Step 1: Run full suite**

Run: `pytest tests/ -q`
Expected: all pass

**Step 2: Run report generation script**

Run: `python scripts/generate_stock_report.py 2330`
Expected: 成功輸出包含分析師風格段落的報告；若 DB 或資料不足，至少有 graceful message。

**Step 3: Fix any integration issues**
- 若失敗，先補 regression tests 再修。

**Step 4: Commit**

```bash
git add -A
git commit -m "test: verify analyst-style report pipeline"
```

---

## Notes
- 嚴格遵守 TDD：每個新增行為都要先有 failing test。
- LLM output 要求：語氣像 sell-side / buy-side 分析師，避免空泛吹捧，需明確列風險。
- 報告格式要穩定，避免全靠 LLM 自由發揮；使用明確 section contract。
- 所有外部依賴（DB / yfinance / Gemini）都要可 stub，避免測試碰網路。
