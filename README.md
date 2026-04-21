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

## 分析師風格個股報告

目前已提供分析師風格報告生成器，會整合：
- canonical 價格資料（若 PostgreSQL 可用）
- 月營收與財報摘要（若資料庫已有資料）
- `yfinance` 新聞
- Gemini（若 `.env` 已設定 `GEMINI_API_KEY`）

### 報告生成使用方式
1. 安裝套件：`uv pip install -e .` 或 `pip install -e .`
2. 如要使用資料庫資料，設定 `.env` 中的 `DATABASE_URL`
3. 如要使用 Gemini，設定 `.env` 中的 `GEMINI_API_KEY`
4. 執行：`python scripts/generate_stock_report.py 2330`

### 行為說明
- **優先使用資料庫**：若 PostgreSQL 可連線，會優先讀 canonical 價格、月營收、財報摘要。
- **DB 不可用時 fallback**：若資料庫無法連線，會自動改用 `yfinance` 即時價格與公開資訊生成報告。
- **LLM 可選**：若有 `GEMINI_API_KEY`，會優先呼叫 Gemini 生成更像真人分析師的敘事；若失敗則自動退回 deterministic fallback 報告。
- **台股代號容錯**：像 `2330` 這類純數字 ticker，live fallback 會自動嘗試 `2330.TW`。

## 網站版（Railway 部署）

目前已加入網站版 MVP，可讓一般使用者直接在網頁輸入股票代號取得分析報告。

### 本機啟動
```bash
uv pip install -e .
uvicorn ai_investment_analyst.web.app:app --host 0.0.0.0 --port 8000
```

開啟：`http://localhost:8000`

### 可用端點
- `GET /health`
- `GET /`
- `POST /api/report`

### Railway 部署
1. 將 repo push 到 GitHub
2. 在 Railway 建立新 project 並連接 GitHub repo
3. 設定環境變數：
   - `GEMINI_API_KEY`
   - `WEB_LOGIN_PASSWORD`（建議設定，啟用網站登入保護）
   - `DATABASE_URL`（可選）
   - `FINMIND_API_TOKEN`（可選）
   - `FINLAB_API_KEY`（可選）
4. Railway 會讀取 `Procfile` 啟動服務

### 網站登入保護
- 若未設定 `WEB_LOGIN_PASSWORD`，網站會維持公開可用。
- 若設定了 `WEB_LOGIN_PASSWORD`，使用者必須先經過 `/login` 輸入密碼，才能進入首頁與使用 `POST /api/report`。

### 免責聲明
本內容僅供參考，不構成投資建議。

## Next Steps
- 擴充更多台股/美股標的
- 加入批次 ticker 管理
- 實作更多資料來源匯入器
- 納入法人籌碼、估值與歷史新聞摘要，提升報告深度
