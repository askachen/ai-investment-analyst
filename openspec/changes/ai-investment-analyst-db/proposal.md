# Proposal: AI Investment Analyst Database Foundation

## Intent（意圖）
建立一套供「AI 投資分析師」使用的投資資料庫基礎，先以 PostgreSQL 建立可擴充、可追蹤資料來源的結構，支援台股與美股資料的後續匯入、查詢與分析。

## Scope（範圍）
### In scope
- 定義支援台股與美股的核心資料模型
- 建立 PostgreSQL schema 與主要資料表關聯
- 納入股價、公司基本資料、財報、股利、新聞、資料來源與匯入紀錄等基礎結構
- 為後續 Python ETL / 爬蟲腳本預留擴充空間
- 先以每日資料與結構化資料為主

### Out of scope
- 前端介面與管理後台
- AI 分析邏輯、RAG、選股策略與報表生成
- 自動下單、券商串接與交易功能
- 即時行情串流
- 實際資料抓取腳本與排程

## Approach（方案）
先以 OpenSpec 方式定義第一版資料庫變更，建立 market-aware 的資料表設計，讓台股與美股能共用一致結構。資料模型會以 symbols 為核心，向外串接日線行情、財報、股利、新聞與匯入紀錄，並透過 data_sources 與 ingestion_runs 保留資料來源與處理歷程，方便後續 Python 腳本匯入與除錯。