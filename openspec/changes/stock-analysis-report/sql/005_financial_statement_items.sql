CREATE TABLE IF NOT EXISTS financial_statement_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID NOT NULL,
    data_source_id UUID NOT NULL,
    ingestion_run_id UUID,
    statement_type VARCHAR(64) NOT NULL,
    report_date DATE NOT NULL,
    item_name VARCHAR(255) NOT NULL,
    item_value NUMERIC(24, 4),
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_financial_statement_items_symbol
        FOREIGN KEY (symbol_id) REFERENCES symbols(id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_financial_statement_items_data_source
        FOREIGN KEY (data_source_id) REFERENCES data_sources(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_financial_statement_items_ingestion_run
        FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_runs(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT uq_financial_statement_items UNIQUE (symbol_id, data_source_id, statement_type, report_date, item_name)
);

CREATE INDEX IF NOT EXISTS idx_financial_statement_items_symbol_date ON financial_statement_items(symbol_id, report_date DESC);
CREATE INDEX IF NOT EXISTS idx_financial_statement_items_type_name ON financial_statement_items(statement_type, item_name);

DROP TRIGGER IF EXISTS trg_financial_statement_items_updated_at ON financial_statement_items;
CREATE TRIGGER trg_financial_statement_items_updated_at
BEFORE UPDATE ON financial_statement_items
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
