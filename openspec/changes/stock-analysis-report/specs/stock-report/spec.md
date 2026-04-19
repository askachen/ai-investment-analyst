# Delta for Stock Report

## ADDED Requirements

### Requirement: Canonical-price-based stock report
The system MUST generate stock analysis reports based on canonical price data.

#### Scenario: Generate a report for a stock with canonical prices
- GIVEN canonical daily price data exists for a stock
- WHEN a report is requested
- THEN the system generates a report using canonical prices
- AND includes the latest close and recent price changes

### Requirement: Source transparency in report context
The system SHOULD describe which price source was used when generating the report.

#### Scenario: Mention selected provider
- GIVEN canonical price data references an originating provider
- WHEN a report is generated
- THEN the report context can identify the selected provider or source type

### Requirement: Extensible report sections
The system MUST allow future inclusion of fundamental, news, and chip data sections.

#### Scenario: Future section expansion
- GIVEN new data domains are integrated later
- WHEN the report generator is updated
- THEN the report can add new sections without changing the core report workflow