# Tasks

## 1. OpenSpec artifacts
- [x] 1.1 建立 proposal.md 並確認第一版範圍
- [x] 1.2 建立 database foundation 的 delta spec
- [x] 1.3 建立 design.md 說明資料模型與技術決策
- [x] 1.4 建立 tasks.md 作為後續實作清單

## 2. Database schema design
- [x] 2.1 定義 markets 與 symbols 主資料表
- [x] 2.2 定義 trading_calendar 與 price_daily 時序資料表
- [x] 2.3 定義 financial_reports 與 dividends 財務資料表
- [x] 2.4 定義 news_articles 與 symbol_news 關聯表
- [x] 2.5 定義 data_sources 與 ingestion_runs 追蹤表
- [x] 2.6 規劃主鍵、唯一鍵、外鍵與必要索引

## 3. Initial PostgreSQL implementation
- [x] 3.1 建立第一版 schema SQL 檔案
- [x] 3.2 準備初始資料（markets 基本資料）
- [x] 3.3 檢查 schema 是否符合後續 Python ETL 匯入需求

## 4. Validation
- [ ] 4.1 與需求比對，確認已涵蓋台股與美股核心資料
- [ ] 4.2 確認 schema 能支援後續新聞、財報、行情匯入
- [ ] 4.3 確認第一版不包含前端與交易功能
