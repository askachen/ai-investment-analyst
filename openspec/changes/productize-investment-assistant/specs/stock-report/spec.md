# Delta for Stock Report

## ADDED Requirements

### Requirement: The system MUST expose investment-decision evidence, not only prose
The system MUST present recommendation evidence in a structured form, including data freshness, confidence, core signals, and risk factors, so users can judge whether a report is actionable.

#### Scenario: View a stock detail page
- GIVEN a stock detail page is rendered
- WHEN the user reviews the report
- THEN the UI shows decision evidence such as freshness, confidence, signals, and risk factors
- AND does not rely only on long-form narrative text

### Requirement: The system MUST track recommendation outcomes over time
The system MUST preserve daily screener outputs in a way that allows later comparison against forward returns or outcome metrics.

#### Scenario: Review a previous screener run
- GIVEN the system has stored a historical screener run
- WHEN the user reviews strategy performance
- THEN the system can compare that run against later market outcomes
- AND summarize hit-rate or follow-up performance by strategy

### Requirement: The system MUST visually disclose data freshness and completeness
The system MUST show whether price, revenue, financial, and news inputs are current enough for decision support.

#### Scenario: Inputs are partially stale
- GIVEN some data domains are fresh and others are stale or missing
- WHEN the user opens the dashboard or a stock report
- THEN the system shows freshness/completeness status per domain
- AND lowers confidence or warns appropriately when evidence is incomplete

## MODIFIED Requirements

### Requirement: Canonical-price-based stock report
(Previously: The system MUST generate stock analysis reports and daily screener snapshots from DB-backed canonical price data without requiring a full fundamentals re-import on every daily run.)

The system MUST generate stock analysis outputs from DB-backed canonical price data and supporting fundamentals, while also surfacing evidence quality, data freshness, and recommendation confidence for end users.

#### Scenario: Generate a trustworthy stock analysis output
- GIVEN the report has access to canonical price and available supporting data
- WHEN the system generates analysis for end users
- THEN it includes structured evidence quality and confidence indicators
- AND clearly signals when any important domain is stale or missing