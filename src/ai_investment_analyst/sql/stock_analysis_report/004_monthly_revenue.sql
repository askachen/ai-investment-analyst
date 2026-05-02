CREATE TABLE IF NOT EXISTS monthly_revenues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID NOT NULL,
    data_source_id UUID NOT NULL,
    ingestion_run_id UUID,
    revenue_year INTEGER NOT NULL,
    revenue_month INTEGER NOT NULL,
    revenue_period DATE NOT NULL,
    revenue NUMERIC(24, 4),
    revenue_month_change_percent NUMERIC(10, 4),
    revenue_year_change_percent NUMERIC(10, 4),
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_monthly_revenues_symbol
        FOREIGN KEY (symbol_id) REFERENCES symbols(id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_monthly_revenues_data_source
        FOREIGN KEY (data_source_id) REFERENCES data_sources(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_monthly_revenues_ingestion_run
        FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_runs(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT uq_monthly_revenues_symbol_source_period UNIQUE (symbol_id, data_source_id, revenue_period)
);

CREATE INDEX IF NOT EXISTS idx_monthly_revenues_symbol_period ON monthly_revenues(symbol_id, revenue_period DESC);
CREATE INDEX IF NOT EXISTS idx_monthly_revenues_source_period ON monthly_revenues(data_source_id, revenue_period DESC);

DROP TRIGGER IF EXISTS trg_monthly_revenues_updated_at ON monthly_revenues;
CREATE TRIGGER trg_monthly_revenues_updated_at
BEFORE UPDATE ON monthly_revenues
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
