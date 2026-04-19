# Proposal: Multi-source Price Data Strategy

## Intent（意圖）
為 AI Investment Analyst 專案建立明確的多資料來源策略，避免 yfinance、FinMind、FinLab 在價格資料重疊時互相覆蓋，並保留原始來源與 canonical 結果，讓後續分析、驗證與除錯有一致基礎。

## Scope（範圍）
### In scope
- 定義多資料來源角色（primary / secondary / research）
- 規劃原始價格資料與 canonical 價格資料的分層模型
- 設計 price source metadata 與去重/選主規則
- 為現有台股與美股價格匯入器提供一致落地方式

### Out of scope
- 實作完整資料比對與衝突告警系統
- 處理非價格資料（如財報、新聞、法人）的 canonical 邏輯
- 建立即時串流或版本化回滾 UI

## Approach（方案）
導入雙層價格模型：
1. `price_daily_raw` 儲存每個 provider 回來的原始日線資料，保留來源、匯入批次與 payload。
2. `price_daily_canonical` 儲存系統選定的標準價格資料，每個 symbol/date 僅保留一筆，並記錄採用來源。

來源優先順序先定義為：
- 台股價格：FinMind 為 primary，FinLab 為 research，yfinance 為 secondary
- 美股/國際指數：yfinance 為 primary

後續所有 loader 先寫入 raw，再由規則產出 canonical。