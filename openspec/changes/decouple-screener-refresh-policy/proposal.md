# Proposal: Decouple Daily Screener Refresh Policy

## Intent（意圖）
將 `daily_screener_job` 從「同時抓價格、月營收、財報再做篩選」重構為穩定的 production refresh policy，避免 daily cron 每天重打 FinMind API，造成 quota 浪費、執行時間過長，或 Railway cron timeout。

## Scope（範圍）
### In scope
- 重新定義 daily screener 的資料刷新責任
- 讓每日 job 只負責價格更新與 screener 產生
- 為月營收建立「新月份才抓」的 refresh policy
- 為財報 / EPS 建立「新季度或缺資料才抓」的 refresh policy
- 設計 FinMind refresh 的分批、節流、可續跑策略
- 保持與既有 `screening_runs` / `screening_results` 相容

### Out of scope
- 重做 screener ranking / scoring 規則
- 調整 web UI 或報表頁面
- 大幅重構 production schema
- 更換 FinMind / TWSE / TPEx 以外的新資料源
- 引入新的外部排程平台

## Approach（方案）
採三段式策略：
1. **Daily price refresh**：每日以 `twse_tpex` 為主做價格增量更新。
2. **Fundamentals refresh policy**：
   - 月營收僅在 DB 未覆蓋最新月份時才抓。
   - 財報 / EPS 僅在 DB 未覆蓋最新季度或指定股票缺資料時才抓。
3. **Daily screener generation**：daily screener 只消費 DB 既有資料，不再在主流程內扛大範圍 FinMind fundamentals 抓取。

第一版優先在現有程式結構內完成責任分離；若有需要，再補獨立 script / cron entrypoint。