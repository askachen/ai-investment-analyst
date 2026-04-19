# Tasks

## 1. OpenSpec artifacts
- [x] 1.1 建立 multi-source price strategy proposal
- [x] 1.2 建立 multi-source price strategy design
- [x] 1.3 建立 delta spec
- [x] 1.4 建立 tasks 清單

## 2. Schema planning
- [ ] 2.1 定義 `price_daily_raw` 結構
- [ ] 2.2 定義 `price_daily_canonical` 結構
- [ ] 2.3 設計來源優先與唯一鍵規則
- [ ] 2.4 規劃舊 `price_daily` 過渡方案

## 3. Loader integration planning
- [ ] 3.1 定義 yfinance raw 寫入流程
- [ ] 3.2 定義 FinMind raw 寫入流程
- [ ] 3.3 定義 FinLab raw 寫入流程
- [ ] 3.4 定義 canonical 更新流程

## 4. Validation
- [ ] 4.1 確認策略符合台股/美股分工
- [ ] 4.2 確認不同來源同日資料可並存
- [ ] 4.3 確認 canonical 可追溯原始來源