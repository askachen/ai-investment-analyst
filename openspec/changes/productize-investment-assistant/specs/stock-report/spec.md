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

### Requirement: The system MUST plan watchlist and alert actions from decision evidence
The system MUST convert stock recommendations, confidence, data quality, and price targets into a watchlist action plan before sending alerts.

#### Scenario: High-confidence buy with fresh data
- GIVEN a stock has a positive rating, sufficient confidence, fresh data, and a target price
- WHEN the watchlist workflow is planned
- THEN the system recommends adding it to the watchlist
- AND creates price and data-staleness alert rules

#### Scenario: Recommendation has incomplete evidence
- GIVEN a stock has a positive rating but incomplete or stale data
- WHEN the watchlist workflow is planned
- THEN the system requires review before adding it to the watchlist
- AND includes a data-quality review alert

### Requirement: The system MUST normalize richer fundamental factors before using them in recommendations
The system MUST convert margin, return, cash-flow, leverage, and revision/trend inputs into bounded factor scores with missing-data status and evidence summaries.

#### Scenario: Rich fundamental inputs are available
- GIVEN margin, ROE/ROA, cash-flow, leverage, and trend inputs are present
- WHEN the system normalizes fundamental factors
- THEN it produces bounded scores, a composite score, and evidence summaries for each factor family

#### Scenario: Some fundamental inputs are missing
- GIVEN only partial fundamental inputs are available
- WHEN the system normalizes fundamental factors
- THEN it marks missing or partial factor families
- AND applies conservative scores instead of pretending the evidence is complete

### Requirement: The system MUST estimate valuation with multiple anchors, not only fixed PE
The system MUST blend PE multiple, PB/ROE, and growth-based valuation anchors when available, and disclose missing methods.

#### Scenario: Multiple valuation anchors are available
- GIVEN current price, EPS, book value, ROE, growth, and market or sector multiples are available
- WHEN the system estimates intrinsic value
- THEN it produces a blended target price, fair-value range, margin of safety, label, confidence, and method evidence

#### Scenario: Some valuation anchors are unavailable
- GIVEN only EPS and a market multiple are available
- WHEN the system estimates intrinsic value
- THEN it still uses a PE anchor
- AND marks PB/ROE or growth anchors as missing with lower confidence

### Requirement: The system MUST apply sector-specific analysis templates
The system MUST choose analysis prompts, core metrics, valuation methods, catalysts, and risks based on the stock's sector when sector evidence is available.

#### Scenario: Semiconductor stock report
- GIVEN a stock belongs to the semiconductor sector
- WHEN the system builds analysis guidance
- THEN it highlights semiconductor-specific metrics such as margins, capex, utilization, inventory, and product mix
- AND includes sector-specific catalysts and risks such as AI demand, advanced-node ramp, cycle reversal, and capex risk

#### Scenario: Unknown sector stock report
- GIVEN the system cannot resolve a stock's sector
- WHEN the system builds analysis guidance
- THEN it falls back to a general template
- AND still provides core metrics, valuation methods, catalysts, risks, and evidence checks

## MODIFIED Requirements

### Requirement: Canonical-price-based stock report
(Previously: The system MUST generate stock analysis reports and daily screener snapshots from DB-backed canonical price data without requiring a full fundamentals re-import on every daily run.)

The system MUST generate stock analysis outputs from DB-backed canonical price data and supporting fundamentals, while also surfacing evidence quality, data freshness, and recommendation confidence for end users.

#### Scenario: Generate a trustworthy stock analysis output
- GIVEN the report has access to canonical price and available supporting data
- WHEN the system generates analysis for end users
- THEN it includes structured evidence quality and confidence indicators
- AND clearly signals when any important domain is stale or missing