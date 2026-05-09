# Design: Decouple Daily Screener Refresh Policy

## Technical Approach
將現有 `daily_screener_job` 的資料刷新責任拆開：價格資料維持每日增量更新；月營收與財報改為依資料新鮮度判斷是否需要抓取。daily screener 主流程只在必要時觸發輕量 fundamentals refresh，平常只讀取 DB 既有資料生成 snapshot。

## Architecture Decisions

### Decision: Keep daily price refresh inside the screener job
`price_daily_canonical` 是每日篩選的必要輸入，因此保留在 `run_daily_screener_job(...)` 內做增量 refresh，延續既有 `load_twse_tpex_stock_price(...)` 與 `_price_refresh_start_date(...)`。

### Decision: Gate monthly revenue refresh by latest covered month
月營收不再依每日 cron 固定呼叫 `load_monthly_revenue(...)`。改由 DB 查詢是否已覆蓋應有月份；只有落後月份或指定股票缺資料時才觸發 refresh。

### Decision: Gate financial refresh by latest covered quarter / EPS completeness
財報與 EPS refresh 以季度為單位判斷，不再每日無條件呼叫 `load_financial_statements(...)`。若最新季度已存在，則 skip；若指定股票缺 EPS 或季度資料過舊，才進行補抓。

### Decision: Separate refresh policy selection from loader execution
是否要抓資料的判斷邏輯獨立成 policy/helper 函式，與實際 loader 分離。這讓 daily job、未來獨立 fundamentals job、以及測試都能共用同一套判斷規則。

### Decision: Preserve current storage schema and screener output contract
不調整 `screening_runs`、`screening_results`、`monthly_revenues`、`financial_statement_items` 的既有 schema。這次重構只改 refresh policy 與 job orchestration，避免 production migration 風險。

## Data Flow / File Changes
- 調整 `src/ai_investment_analyst/analysis/daily_screener_job.py`
  - 保留每日價格 refresh
  - 加入月營收 freshness policy
  - 加入財報 / EPS freshness policy
  - 讓 daily screener 預設只在必要時觸發 fundamentals loader
- 視需要新增 helper 函式：
  - 最新月份判斷
  - 最新季度判斷
  - 缺資料 ticker 選擇
  - refresh decision summary
- 更新 `tests/analysis/test_daily_screener_job.py`
  - 驗證 daily job 預設不重打 fundamentals
  - 驗證資料落後時才觸發 loader
  - 驗證指定 tickers override 時仍可強制 refresh
- 如現有 script 需要，調整 `scripts/generate_daily_screener.py` 呼叫行為，但不改既有 entrypoint 名稱