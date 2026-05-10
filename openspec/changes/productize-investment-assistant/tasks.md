# Tasks

## 1. Foundation
- [x] 1.1 Establish `pytest` as runnable local test baseline
- [x] 1.2 Identify high-risk modules lacking regression coverage (`web/app.py`, `analysis/stock_report.py`, `analysis/screener.py`, `etl/twse_tpex_loader.py`)
- [x] 1.3 Define product roadmap priorities in specs

## 2. Trust & Validation
- [x] 2.1 Design strategy outcome tracking for screener runs
- [x] 2.2 Design data freshness / completeness surfaces for UI
- [x] 2.3 Define recommendation confidence and evidence display rules

## 3. Decision UX
- [x] 3.1 Redesign dashboard information architecture
- [x] 3.2 Redesign stock detail page into decision card layout
- [x] 3.3 Plan watchlist and alert workflow

## 4. Research Depth
- [x] 4.1 Plan richer fundamental factor set
  - Implemented normalized factor schema for profitability, cash-flow quality, leverage risk, and revision/trend signals.
  - Added pure analysis tests for factor normalization, missing-data penalties, and factor-to-evidence summaries.
- [x] 4.2 Plan valuation improvements beyond simple PE heuristics
  - Implemented multi-anchor valuation model blending PE multiple, PB/ROE, and growth-based anchors with missing-method confidence.
- [x] 4.3 Plan sector-specific analysis templates
  - Implemented sector templates for general, semiconductor, financial, and consumer analysis guidance.

## 5. Delivery rhythm
- [x] 5.1 Add hourly audit/review automation for backlog grooming
- [x] 5.2 Use TDD-first implementation for upcoming high-priority features
  - Added failing tests first for stock report research-engine evidence before integrating factor, valuation, and sector-template outputs.
- [x] 5.3 Report progress in small validated increments
  - Delivered a validated increment with targeted tests and full regression suite passing before commit/push.
