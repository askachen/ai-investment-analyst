# Design: Productize Investment Assistant

## Technical Approach
專案接下來不再以單點功能堆疊為主，而是改成產品化路線。核心設計原則為：
- 所有影響投資判斷的功能，先有資料新鮮度與驗證機制，再談敘事與 UI。
- 所有高頻改動，先補 `pytest` 與 fixture，再進入功能重構。
- Daily experience 以 dashboard / watchlist / decision cards 為中心，而不是單次輸入 ticker 取報告。

## Architecture Decisions

### Decision: Build a trust layer before deeper recommendation logic
優先建立策略歷史追蹤、命中率、資料新鮮度與缺漏標示。沒有 trust layer 的情況下，即使推薦邏輯更複雜，也不適合稱為日常投資輔助工具。

### Decision: Promote dashboard and stock detail pages into decision surfaces
首頁與個股頁都應從「展示文字」轉為「幫助決策」。首頁優先呈現市場概況、推薦榜、自選股與異動；個股頁優先呈現結論、依據、風險、催化與歷史變化。

### Decision: Separate background review/optimization from production deployment
每小時排程可負責審查 backlog、提出下一步、整理規格與測試缺口；是否進行 code push 應由當前工作流程控制，不讓背景任務無限制發散。

### Decision: Establish pytest as the default safety rail
先補 `pytest` 執行能力與針對核心模組的測試，再進一步重構 screener、report、web UI helper 與 ETL policy。重大功能以先寫測試或先補 regression test 為原則。

## Workstreams
1. **Validation & Analytics**
   - screener hit-rate tracking
   - recommendation outcome snapshots
   - strategy comparison
2. **Decision UX**
   - dashboard IA redesign
   - stock detail decision cards
   - watchlist / alerts / summaries
3. **Research Engine**
   - richer financial factors
   - valuation model refinement
   - sector-aware templates
4. **Reliability & Tooling**
   - pytest baseline
   - test fixtures
   - refactor boundaries
   - cron-assisted backlog review

## Data Flow / File Changes
- 新增 roadmap / delta specs 描述產品化方向
- 後續將優先變更：
  - `src/ai_investment_analyst/web/*`
  - `src/ai_investment_analyst/analysis/*`
  - `tests/*`
- 視需要新增 watchlist / validation / audit 模組與對應資料表或 snapshot 儲存邏輯