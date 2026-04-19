# Delta for Investment Database

## ADDED Requirements

### Requirement: Multi-market symbol master
The system MUST maintain a normalized symbol master that supports at least Taiwan and US markets.

#### Scenario: Register a Taiwan symbol
- GIVEN market metadata for Taiwan exists
- WHEN a Taiwan-listed stock is created
- THEN the symbol record is stored with its market identity
- AND the system can distinguish it from symbols in other markets

#### Scenario: Register a US symbol
- GIVEN market metadata for the US exists
- WHEN a US-listed stock or ETF is created
- THEN the symbol record is stored with its market identity
- AND the record can coexist with symbols from Taiwan without collision

### Requirement: Daily price history storage
The system MUST store daily OHLCV price history for each symbol.

#### Scenario: Insert a daily price row
- GIVEN a valid symbol exists
- WHEN a daily price record is ingested for a trading date
- THEN the record is stored with open, high, low, close, volume, and trading value fields
- AND duplicate rows for the same symbol and date are prevented

### Requirement: Financial report storage
The system MUST store periodic financial report data for each symbol.

#### Scenario: Insert a quarterly report
- GIVEN a valid symbol exists
- WHEN a quarterly financial report is ingested
- THEN the system stores the reporting period, report type, and key financial metrics

### Requirement: Dividend history storage
The system MUST store dividend and ex-right/ex-dividend events for each symbol.

#### Scenario: Record a dividend event
- GIVEN a valid symbol exists
- WHEN a dividend event is ingested
- THEN the system stores cash dividend, stock dividend, and relevant dates when available

### Requirement: News storage and symbol mapping
The system MUST store investment-related news and allow each article to map to zero, one, or many symbols.

#### Scenario: Map one article to multiple symbols
- GIVEN a news article is stored
- WHEN the article mentions multiple symbols
- THEN the system stores the article once
- AND creates multiple symbol mapping records

### Requirement: Source lineage and ingestion auditability
The system MUST track data sources and ingestion run history for imported records.

#### Scenario: Record an ingestion run
- GIVEN a data import job starts
- WHEN the job finishes or fails
- THEN the system stores the run status, source identity, execution time, and error details when present

### Requirement: Trading calendar support
The system SHOULD maintain trading calendar data per market to support validation of trading-day imports.

#### Scenario: Validate a market trading date
- GIVEN a market trading calendar exists
- WHEN a daily price import is prepared
- THEN the system can determine whether the target date is a trading day for that market