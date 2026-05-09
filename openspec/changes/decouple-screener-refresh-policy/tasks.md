# Tasks

## 1. Refresh policy design in code
- [x] 1.1 Define monthly revenue freshness helpers and decision rules
- [x] 1.2 Define financial / EPS freshness helpers and decision rules
- [x] 1.3 Separate refresh-policy selection from loader execution in `daily_screener_job.py`

## 2. Daily screener orchestration changes
- [x] 2.1 Keep daily price refresh as default behavior
- [x] 2.2 Make full-universe daily runs skip fundamentals when DB coverage is fresh
- [x] 2.3 Allow targeted fundamentals refresh only for stale or missing data
- [x] 2.4 Preserve explicit ticker override behavior for manual / recovery runs

## 3. Verification
- [x] 3.1 Update tests for freshness-based skip behavior
- [x] 3.2 Update tests for targeted refresh behavior when data is stale
- [x] 3.3 Run compile/test verification for changed files
