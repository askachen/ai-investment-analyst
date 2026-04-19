# Design: Stock Analysis Report Generator

## Technical Approach
個股分析報告生成器不直接從多個來源即時抓資料，而是以資料庫中的 canonical 資料作為主要依據，確保同一股票同一天只有一份標準價格。報告生成分成資料聚合與文字輸出兩步，避免 LLM 直接碰觸未整理資料而產生幻覺。

## Architecture Decisions

### Decision: Use canonical price data as the report foundation
報告中的價格結論一律來自 `price_daily_canonical`，避免 raw multi-source 重複值造成混亂。

### Decision: Separate context building from report rendering
先產出結構化 context，再轉成報告字串。這樣未來可替換成 CLI、API、Web UI，甚至讓 LLM 只負責潤稿。

### Decision: Keep report sections explicit and extensible
第一版報告先包含：
- 股票代號
- 最新收盤
- 近 5 日/10 日價格變化
- 可用資料來源說明
- 初步風險提醒

之後可擴充：
- 月營收摘要
- 財報摘要
- 新聞摘要
- 法人/籌碼摘要
- 技術指標

## Data Flow / File Changes
- 新增 `analysis/stock_report.py`
- 新增 `scripts/generate_stock_report.py`
- 讀取 `price_daily_canonical`
- 可選讀取 `price_daily_raw` 做來源說明
- 後續擴充 context builder 模組