# Proposal: Productize Investment Assistant

## Intent（意圖）
將 `ai-investment-analyst` 從可展示報告與推薦榜的 MVP，升級為可持續使用的家庭投資決策輔助工具。重點不是生成更多文字，而是提升資料可信度、策略可驗證性、UI 可用性，以及工程品質，讓使用者能每天穩定使用並逐步建立信任。

## Scope（範圍）
### In scope
- 建立產品與工程總體 roadmap
- 以 TDD / `pytest` 為優先的開發基線
- 優先規劃策略驗證、資料新鮮度、watchlist、個股決策卡、每日摘要
- 規劃前端資訊架構與 dashboard 體驗升級
- 規劃背景排程：定期審查、資料刷新、摘要輸出

### Out of scope
- 宣稱保證獲利或提供法規意義上的投資建議
- 自動下單 / 券商整合
- 高風險、無測試保護的自動化大改

## Approach（方案）
採四條主線並行推進：
1. **Trust & Validation**：先做策略追蹤、資料新鮮度、結果回顧。
2. **Decision UX**：重構首頁與個股頁，讓資訊對投資決策更直接。
3. **Research Depth**：補基本面、估值、風險與產業脈絡。
4. **Engineering Reliability**：補 `pytest`、提高測試覆蓋、分離 UI/API/ETL 責任、使用定期審查任務推進 backlog。