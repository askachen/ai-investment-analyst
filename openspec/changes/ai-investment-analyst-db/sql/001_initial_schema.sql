CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS markets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(16) NOT NULL UNIQUE,
    name VARCHAR(64) NOT NULL,
    region VARCHAR(64),
    currency_code VARCHAR(8) NOT NULL,
    timezone VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS data_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    source_type VARCHAR(32) NOT NULL,
    base_url TEXT,
    market_code VARCHAR(16),
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_data_sources_market_code
        FOREIGN KEY (market_code) REFERENCES markets(code)
        ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS symbols (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_id UUID NOT NULL,
    ticker VARCHAR(32) NOT NULL,
    name VARCHAR(255) NOT NULL,
    local_name VARCHAR(255),
    instrument_type VARCHAR(32) NOT NULL DEFAULT 'stock',
    exchange VARCHAR(64),
    sector VARCHAR(128),
    industry VARCHAR(128),
    isin VARCHAR(32),
    cusip VARCHAR(32),
    currency_code VARCHAR(8),
    country_code VARCHAR(8),
    listing_date DATE,
    delisted_date DATE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_symbols_market
        FOREIGN KEY (market_id) REFERENCES markets(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT uq_symbols_market_ticker UNIQUE (market_id, ticker)
);

CREATE TABLE IF NOT EXISTS trading_calendar (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_id UUID NOT NULL,
    trading_date DATE NOT NULL,
    is_trading_day BOOLEAN NOT NULL,
    session_type VARCHAR(32) NOT NULL DEFAULT 'regular',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_trading_calendar_market
        FOREIGN KEY (market_id) REFERENCES markets(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT uq_trading_calendar_market_date UNIQUE (market_id, trading_date)
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data_source_id UUID NOT NULL,
    run_type VARCHAR(64) NOT NULL,
    target_table VARCHAR(64) NOT NULL,
    market_id UUID,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL,
    records_received INTEGER NOT NULL DEFAULT 0,
    records_inserted INTEGER NOT NULL DEFAULT 0,
    records_updated INTEGER NOT NULL DEFAULT 0,
    records_failed INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_ingestion_runs_data_source
        FOREIGN KEY (data_source_id) REFERENCES data_sources(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_ingestion_runs_market
        FOREIGN KEY (market_id) REFERENCES markets(id)
        ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS price_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID NOT NULL,
    trading_date DATE NOT NULL,
    open_price NUMERIC(18, 6),
    high_price NUMERIC(18, 6),
    low_price NUMERIC(18, 6),
    close_price NUMERIC(18, 6),
    adjusted_close NUMERIC(18, 6),
    price_change NUMERIC(18, 6),
    change_percent NUMERIC(10, 4),
    volume BIGINT,
    turnover_value NUMERIC(24, 4),
    trade_count BIGINT,
    ingestion_run_id UUID,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_price_daily_symbol
        FOREIGN KEY (symbol_id) REFERENCES symbols(id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_price_daily_ingestion_run
        FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_runs(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT uq_price_daily_symbol_date UNIQUE (symbol_id, trading_date)
);

CREATE TABLE IF NOT EXISTS financial_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID NOT NULL,
    fiscal_year INTEGER NOT NULL,
    fiscal_period VARCHAR(16) NOT NULL,
    report_type VARCHAR(32) NOT NULL,
    period_start_date DATE,
    period_end_date DATE NOT NULL,
    filing_date DATE,
    revenue NUMERIC(24, 4),
    gross_profit NUMERIC(24, 4),
    operating_income NUMERIC(24, 4),
    net_income NUMERIC(24, 4),
    eps NUMERIC(18, 6),
    total_assets NUMERIC(24, 4),
    total_liabilities NUMERIC(24, 4),
    shareholders_equity NUMERIC(24, 4),
    operating_cash_flow NUMERIC(24, 4),
    investing_cash_flow NUMERIC(24, 4),
    financing_cash_flow NUMERIC(24, 4),
    ingestion_run_id UUID,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_financial_reports_symbol
        FOREIGN KEY (symbol_id) REFERENCES symbols(id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_financial_reports_ingestion_run
        FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_runs(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT uq_financial_reports_symbol_period UNIQUE (symbol_id, fiscal_year, fiscal_period, report_type)
);

CREATE TABLE IF NOT EXISTS dividends (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID NOT NULL,
    announcement_date DATE,
    ex_dividend_date DATE,
    record_date DATE,
    payment_date DATE,
    fiscal_year INTEGER,
    cash_dividend NUMERIC(18, 6),
    stock_dividend NUMERIC(18, 6),
    dividend_currency VARCHAR(8),
    payout_ratio NUMERIC(10, 4),
    dividend_yield NUMERIC(10, 4),
    ingestion_run_id UUID,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_dividends_symbol
        FOREIGN KEY (symbol_id) REFERENCES symbols(id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_dividends_ingestion_run
        FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_runs(id)
        ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS news_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_article_key VARCHAR(255),
    data_source_id UUID,
    title TEXT NOT NULL,
    summary TEXT,
    content TEXT,
    source_name VARCHAR(128),
    author_name VARCHAR(128),
    published_at TIMESTAMPTZ,
    article_url TEXT,
    language_code VARCHAR(16),
    sentiment_label VARCHAR(32),
    ingestion_run_id UUID,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_news_articles_data_source
        FOREIGN KEY (data_source_id) REFERENCES data_sources(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_news_articles_ingestion_run
        FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_runs(id)
        ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS symbol_news (
    symbol_id UUID NOT NULL,
    news_article_id UUID NOT NULL,
    relevance_score NUMERIC(6, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (symbol_id, news_article_id),
    CONSTRAINT fk_symbol_news_symbol
        FOREIGN KEY (symbol_id) REFERENCES symbols(id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_symbol_news_article
        FOREIGN KEY (news_article_id) REFERENCES news_articles(id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_symbols_market_id ON symbols(market_id);
CREATE INDEX IF NOT EXISTS idx_symbols_ticker ON symbols(ticker);
CREATE INDEX IF NOT EXISTS idx_trading_calendar_market_date ON trading_calendar(market_id, trading_date);
CREATE INDEX IF NOT EXISTS idx_price_daily_symbol_date ON price_daily(symbol_id, trading_date DESC);
CREATE INDEX IF NOT EXISTS idx_financial_reports_symbol_period_end ON financial_reports(symbol_id, period_end_date DESC);
CREATE INDEX IF NOT EXISTS idx_dividends_symbol_ex_date ON dividends(symbol_id, ex_dividend_date DESC);
CREATE INDEX IF NOT EXISTS idx_news_articles_published_at ON news_articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_articles_source_article_key ON news_articles(source_article_key);
CREATE INDEX IF NOT EXISTS idx_symbol_news_news_article_id ON symbol_news(news_article_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_runs_data_source_started_at ON ingestion_runs(data_source_id, started_at DESC);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_markets_updated_at ON markets;
CREATE TRIGGER trg_markets_updated_at
BEFORE UPDATE ON markets
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_data_sources_updated_at ON data_sources;
CREATE TRIGGER trg_data_sources_updated_at
BEFORE UPDATE ON data_sources
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_symbols_updated_at ON symbols;
CREATE TRIGGER trg_symbols_updated_at
BEFORE UPDATE ON symbols
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_trading_calendar_updated_at ON trading_calendar;
CREATE TRIGGER trg_trading_calendar_updated_at
BEFORE UPDATE ON trading_calendar
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_ingestion_runs_updated_at ON ingestion_runs;
CREATE TRIGGER trg_ingestion_runs_updated_at
BEFORE UPDATE ON ingestion_runs
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_price_daily_updated_at ON price_daily;
CREATE TRIGGER trg_price_daily_updated_at
BEFORE UPDATE ON price_daily
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_financial_reports_updated_at ON financial_reports;
CREATE TRIGGER trg_financial_reports_updated_at
BEFORE UPDATE ON financial_reports
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_dividends_updated_at ON dividends;
CREATE TRIGGER trg_dividends_updated_at
BEFORE UPDATE ON dividends
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_news_articles_updated_at ON news_articles;
CREATE TRIGGER trg_news_articles_updated_at
BEFORE UPDATE ON news_articles
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
