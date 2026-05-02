CREATE TABLE IF NOT EXISTS price_daily_raw (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID NOT NULL,
    data_source_id UUID NOT NULL,
    ingestion_run_id UUID,
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
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_price_daily_raw_symbol
        FOREIGN KEY (symbol_id) REFERENCES symbols(id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_price_daily_raw_data_source
        FOREIGN KEY (data_source_id) REFERENCES data_sources(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_price_daily_raw_ingestion_run
        FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_runs(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT uq_price_daily_raw_symbol_source_date UNIQUE (symbol_id, data_source_id, trading_date)
);

CREATE TABLE IF NOT EXISTS price_daily_canonical (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID NOT NULL,
    trading_date DATE NOT NULL,
    selected_raw_id UUID,
    data_source_id UUID NOT NULL,
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
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_price_daily_canonical_symbol
        FOREIGN KEY (symbol_id) REFERENCES symbols(id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_price_daily_canonical_selected_raw
        FOREIGN KEY (selected_raw_id) REFERENCES price_daily_raw(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_price_daily_canonical_data_source
        FOREIGN KEY (data_source_id) REFERENCES data_sources(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT uq_price_daily_canonical_symbol_date UNIQUE (symbol_id, trading_date)
);

CREATE INDEX IF NOT EXISTS idx_price_daily_raw_symbol_date ON price_daily_raw(symbol_id, trading_date DESC);
CREATE INDEX IF NOT EXISTS idx_price_daily_raw_source_date ON price_daily_raw(data_source_id, trading_date DESC);
CREATE INDEX IF NOT EXISTS idx_price_daily_canonical_symbol_date ON price_daily_canonical(symbol_id, trading_date DESC);
CREATE INDEX IF NOT EXISTS idx_price_daily_canonical_source_date ON price_daily_canonical(data_source_id, trading_date DESC);

DROP TRIGGER IF EXISTS trg_price_daily_raw_updated_at ON price_daily_raw;
CREATE TRIGGER trg_price_daily_raw_updated_at
BEFORE UPDATE ON price_daily_raw
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_price_daily_canonical_updated_at ON price_daily_canonical;
CREATE TRIGGER trg_price_daily_canonical_updated_at
BEFORE UPDATE ON price_daily_canonical
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
