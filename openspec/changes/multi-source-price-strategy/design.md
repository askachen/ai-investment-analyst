# Design: Multi-source Price Data Strategy

## Technical Approach
現有 `price_daily` 表直接承載匯入結果，對單一來源尚可，但當多來源並存時，會出現同一個 symbol/date 只能留一筆的限制，導致資料覆蓋與來源遺失。為解決此問題，價格資料改為 raw/canonical 分層。

## Architecture Decisions

### Decision: Separate raw imported prices from canonical prices
新增 `price_daily_raw` 儲存所有來源的原始價格資料，讓不同 provider 的同日資料可以並存。再由 `price_daily_canonical` 承接最終採用值，供查詢與分析使用。

### Decision: Record provider identity on every price row
每筆 raw/canonical 價格資料都記錄 `data_source_id`，canonical 也記錄 `selected_from_raw_id` 或等價來源欄位，確保可追溯。

### Decision: Encode source priority by market and instrument category
資料選主規則不做成硬編碼散落在 loader，而是集中成可調整策略。第一版先文件化：
- TW stock daily: FinMind > yfinance > FinLab
- US stock/index daily: yfinance > FinMind
- FinLab 預設作為研究/驗證來源，不主動覆寫 canonical

### Decision: Preserve current loaders with a migration path
短期內現有 loader 可維持運作，但新一版會逐步改成：先寫 raw，再更新 canonical。必要時保留舊 `price_daily` 作為過渡層，最後再決定淘汰或改名。

## Data Flow / File Changes
- 新增 `price_daily_raw`
- 新增 `price_daily_canonical`
- 評估 `price_daily` 過渡策略（保留/改造/淘汰）
- loader 調整為 raw-first
- 增加來源優先規則文件或設定表
