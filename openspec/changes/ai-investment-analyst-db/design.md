# Design: AI Investment Analyst Database Foundation

## Technical Approach
第一版採用 PostgreSQL 作為主資料庫，建立一組以 `markets` 與 `symbols` 為核心的標準化 schema。所有跨市場資料均以 market + symbol identity 管理，讓台股與美股能共享後續分析流程與匯入架構。

## Architecture Decisions

### Decision: Separate market metadata from symbol master
將 `markets` 與 `symbols` 分離，方便統一支援 TW / US，並保留不同市場規則、交易所、幣別、時區等資訊。

### Decision: Use normalized tables for time-series and domain data
將日線、財報、股利、新聞拆成不同 domain tables，避免單一巨表膨脹，也便於後續依資料源分批匯入與維護。

### Decision: Track source lineage and ingestion history
加入 `data_sources` 與 `ingestion_runs`，保留每次匯入來源、狀態、批次時間與錯誤訊息，方便追查資料品質與 ETL 問題。

### Decision: Support future AI workflows without coupling now
先把資料庫設計成對 AI 友善，但不直接耦合 LLM workflow。後續若要加 embeddings、事件摘要、特徵表，可另外擴充 schema。

## Data Flow / File Changes
- `markets`: 市場主檔（TW / US）
- `symbols`: 股票/ETF/ADR 等標的基本資料
- `trading_calendar`: 市場交易日曆
- `price_daily`: 每日 OHLCV 與成交資訊
- `financial_reports`: 財報與關鍵財務指標
- `dividends`: 股利與除權息資料
- `news_articles`: 新聞主檔
- `symbol_news`: 新聞與標的多對多關聯
- `data_sources`: 資料來源設定
- `ingestion_runs`: 每次匯入執行紀錄

後續實作階段將補上 PostgreSQL DDL、索引策略、唯一鍵與外鍵約束。