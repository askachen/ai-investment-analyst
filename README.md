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

## YFinance 最新資料匯入
目前已提供一支示範腳本，可用 `yfinance` 抓取以下標的的最新日線資料並寫入 PostgreSQL：
- `^TWII`：台股加權指數
- `^IXIC`：納斯達克綜合指數
- `^DJI`：道瓊工業指數
- `2454.TW`：聯發科
- `2330.TW`：台積電

### 使用方式
1. 建立並啟用虛擬環境
2. 安裝套件：`pip install -e .`
3. 設定 `.env` 中的 `DATABASE_URL`
4. 若 schema 尚未建立，先執行：`python scripts/apply_schema.py`
5. 執行：`python scripts/load_yfinance_latest.py`

匯入過程會自動：
- 確保 `data_sources` 有 `yfinance`
- 建立/更新 `symbols`
- 寫入最新一筆 `price_daily`
- 記錄 `ingestion_runs`

## FinMind 台股日成交匯入
目前已提供 FinMind 台股日成交示範匯入器，會讀取 `.env` 內的 `FINMIND_API_TOKEN`，並抓取 `2330`、`2454` 的 `TaiwanStockPrice` 資料寫入 PostgreSQL。

### `.env` 範例
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/investment
FINMIND_API_TOKEN=your_finmind_token
```

### 使用方式
1. 安裝套件：`pip install -e .`
2. 確認 schema 已建立：`python scripts/apply_schema.py`
3. 執行：`python scripts/load_finmind_tw_price.py`

匯入過程會自動：
- 確保 `data_sources` 有 `finmind`
- 建立/更新 `symbols`
- 批次寫入 `price_daily`
- 記錄 `ingestion_runs`

## FinLab 台股價格匯入
目前已提供 FinLab Python SDK 示範匯入器，會讀取 `.env` 內的 `FINLAB_API_KEY`，使用 `data.get(...)` 抓取台股收盤價與成交股數，並將 `2330`、`2454` 最近 10 筆資料寫入 PostgreSQL。

### `.env` 範例
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/investment
FINLAB_API_KEY=your_finlab_api_key
```

### 使用方式
1. 安裝套件：`pip install -e .`
2. 確認 schema 已建立：`python scripts/apply_schema.py`
3. 執行：`python scripts/load_finlab_price.py`

## Next Steps
- 擴充更多台股/美股標的
- 加入批次 ticker 管理
- 實作更多資料來源匯入器
