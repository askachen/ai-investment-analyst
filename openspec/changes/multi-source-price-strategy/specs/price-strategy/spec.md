# Delta for Price Strategy

## ADDED Requirements

### Requirement: Raw price storage for multiple providers
The system MUST store daily price rows from different providers without overwriting one another.

#### Scenario: Same symbol and date from two providers
- GIVEN the same symbol and trading date exist in multiple providers
- WHEN both rows are ingested
- THEN the system stores both raw rows
- AND each row retains its provider identity

### Requirement: Canonical daily price selection
The system MUST maintain a canonical daily price record for each symbol and trading date.

#### Scenario: Select a primary provider value
- GIVEN multiple raw price rows exist for a symbol/date
- WHEN the canonical selection process runs
- THEN the system keeps exactly one canonical row for that symbol/date
- AND records which provider was selected

### Requirement: Market-specific source priority
The system MUST support different source priority rules by market or instrument type.

#### Scenario: Taiwan stock daily data priority
- GIVEN raw daily price rows from FinMind, yfinance, and FinLab for a Taiwan stock
- WHEN canonical selection runs
- THEN FinMind is selected before yfinance and FinLab by default

#### Scenario: US market daily data priority
- GIVEN raw daily price rows from yfinance and another provider for a US symbol
- WHEN canonical selection runs
- THEN yfinance is selected by default

### Requirement: Traceability of canonical prices
The system MUST allow canonical prices to be traced back to original imported rows.

#### Scenario: Audit a canonical row
- GIVEN a canonical price row exists
- WHEN the system inspects its provenance
- THEN it can identify the originating data source and imported raw row