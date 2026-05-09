# Delta for Stock Report

## ADDED Requirements

### Requirement: Daily screener MUST prioritize price freshness over fundamentals refresh
The system MUST update required daily price data before generating daily screener snapshots, even when monthly revenue and financial refresh are skipped.

#### Scenario: Daily run with fresh fundamentals
- GIVEN `price_daily_canonical` is behind the latest trading sessions
- AND monthly revenue and financial data are already fresh enough for screening
- WHEN the daily screener job runs
- THEN the system refreshes price data first
- AND skips fundamentals refresh
- AND still generates screener snapshots from DB-backed data

### Requirement: Monthly revenue refresh MUST be gated by data freshness
The system MUST NOT call the monthly revenue loader on every daily screener run. It MUST only refresh monthly revenue when the database is behind the latest expected revenue period or when targeted tickers are missing required revenue rows.

#### Scenario: Monthly revenue already current
- GIVEN the database already contains the latest required monthly revenue period for the target tickers
- WHEN the daily screener job runs
- THEN the system skips monthly revenue refresh

#### Scenario: Monthly revenue is stale or missing
- GIVEN the database is missing the latest required monthly revenue period for one or more target tickers
- WHEN the daily screener job runs
- THEN the system refreshes monthly revenue only for the stale or missing target tickers

### Requirement: Financial refresh MUST be gated by quarter freshness and EPS completeness
The system MUST NOT call the financial loader on every daily screener run. It MUST only refresh financial statements when the database is behind the latest required reporting quarter or when targeted tickers are missing EPS-complete data required for screening.

#### Scenario: Financial data already current
- GIVEN the database already contains current-enough financial statement coverage for the target tickers
- WHEN the daily screener job runs
- THEN the system skips financial refresh

#### Scenario: Financial data is stale or EPS is missing
- GIVEN one or more target tickers are missing current financial coverage or EPS-complete rows
- WHEN the daily screener job runs
- THEN the system refreshes financial statements only for those stale or incomplete tickers

## MODIFIED Requirements

### Requirement: Canonical-price-based stock report
(Previously: The system MUST generate stock analysis reports based on canonical price data.)

The system MUST generate stock analysis reports and daily screener snapshots from DB-backed canonical price data without requiring a full fundamentals re-import on every daily run.

#### Scenario: Generate daily screener outputs from existing DB coverage
- GIVEN canonical price data and previously imported fundamentals already exist in the database
- WHEN the daily screener job runs on a normal trading day
- THEN the system uses the existing DB coverage
- AND only refreshes the sources that are stale according to refresh policy
- AND generates screener outputs without forcing a full fundamentals reload