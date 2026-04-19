# AI Investment Analyst

AI Investment Analyst 是一個以 PostgreSQL + Python ETL 為核心的投資資料平台，第一階段先建立台股與美股資料庫底座，後續逐步擴充資料抓取、清洗、分析與 AI 能力。

## Current Scope
- 支援台股與美股市場主檔
- 建立 PostgreSQL schema
- 為後續 Python ETL 與爬蟲保留擴充空間

## Project Structure
- `openspec/`：需求、設計、tasks 與 delta specs
- `src/ai_investment_analyst/`：Python 原始碼
- `scripts/`：開發/初始化腳本
- `tests/`：測試

## Database Bootstrap
1. 建立 PostgreSQL 資料庫
2. 執行 `openspec/changes/ai-investment-analyst-db/sql/001_initial_schema.sql`
3. 執行 `openspec/changes/ai-investment-analyst-db/sql/002_seed_markets.sql`

## Next Steps
- 建立 Python ETL 專案骨架
- 新增 `.env` / config 管理
- 實作第一批資料來源匯入器
