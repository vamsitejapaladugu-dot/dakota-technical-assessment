-- Operational metadata.
-- ops.pipeline_runs is written once per asset materialization and is the
-- backbone of the observability story: the executive report footer cites it,
-- and it supports "what ran, when, how many rows" questions without log-diving.

CREATE TABLE IF NOT EXISTS ops.pipeline_runs (
    run_id          uuid        NOT NULL,
    asset_name      text        NOT NULL,
    status          text        NOT NULL CHECK (status IN ('success', 'failed')),
    rows_processed  integer     NOT NULL DEFAULT 0,
    rows_rejected   integer     NOT NULL DEFAULT 0,
    window_start    timestamptz,
    window_end      timestamptz,
    started_at      timestamptz NOT NULL,
    finished_at     timestamptz NOT NULL DEFAULT now(),
    error_message   text,
    PRIMARY KEY (run_id, asset_name)
);

CREATE INDEX IF NOT EXISTS ix_pipeline_runs_asset_finished
    ON ops.pipeline_runs (asset_name, finished_at DESC);

-- Records that failed schema validation at ingestion time. They are kept,
-- not dropped: quarantining preserves the evidence needed to debug upstream
-- changes without blocking the healthy portion of a batch.
CREATE TABLE IF NOT EXISTS ops.rejected_records (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source           text        NOT NULL,
    raw_payload      jsonb       NOT NULL,
    rejection_reason text        NOT NULL,
    _run_id          uuid        NOT NULL,
    rejected_at      timestamptz NOT NULL DEFAULT now()
);
