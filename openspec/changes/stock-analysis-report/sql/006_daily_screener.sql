CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS screening_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_date DATE NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    universe_size INTEGER NOT NULL DEFAULT 0,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'completed',
    criteria JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS screening_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    screening_run_id UUID NOT NULL,
    rank INTEGER NOT NULL,
    ticker VARCHAR(32) NOT NULL,
    total_score NUMERIC(8, 2) NOT NULL,
    close_price NUMERIC(18, 6),
    factor_scores JSONB NOT NULL DEFAULT '{}'::jsonb,
    reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_screening_results_run
        FOREIGN KEY (screening_run_id) REFERENCES screening_runs(id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT uq_screening_results_run_rank UNIQUE (screening_run_id, rank),
    CONSTRAINT uq_screening_results_run_ticker UNIQUE (screening_run_id, ticker)
);

CREATE INDEX IF NOT EXISTS idx_screening_runs_generated_at ON screening_runs(generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_screening_results_run_rank ON screening_results(screening_run_id, rank ASC);
CREATE INDEX IF NOT EXISTS idx_screening_results_ticker ON screening_results(ticker);

DROP TRIGGER IF EXISTS trg_screening_runs_updated_at ON screening_runs;
CREATE TRIGGER trg_screening_runs_updated_at
BEFORE UPDATE ON screening_runs
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
