-- Schema layout maps to the medallion layers plus an operational schema.
-- Executed automatically by the postgres container on first startup
-- (mounted into /docker-entrypoint-initdb.d, runs in filename order).

CREATE SCHEMA IF NOT EXISTS raw;      -- bronze: landed source data, append-only + idempotent upserts
CREATE SCHEMA IF NOT EXISTS staging;  -- silver: dbt-managed typed/deduplicated views
CREATE SCHEMA IF NOT EXISTS marts;    -- gold:   dbt-managed analytics tables
CREATE SCHEMA IF NOT EXISTS ops;      -- pipeline audit + quarantine (not part of the medallion flow)

COMMENT ON SCHEMA raw     IS 'Bronze layer: source-shaped records with ingestion lineage columns.';
COMMENT ON SCHEMA staging IS 'Silver layer: cleaned, typed, deduplicated models (dbt views).';
COMMENT ON SCHEMA marts   IS 'Gold layer: dimensional models and aggregates (dbt tables).';
COMMENT ON SCHEMA ops     IS 'Operational metadata: run audit and rejected-record quarantine.';
