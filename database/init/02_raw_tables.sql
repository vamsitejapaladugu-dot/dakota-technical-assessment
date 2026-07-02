-- Raw (bronze) tables.
-- Design rules applied to every table:
--   1. Natural-key UNIQUE constraint -> physical guarantee of idempotent re-runs
--      (loaders use ON CONFLICT ... DO UPDATE).
--   2. Lineage columns (_run_id, _ingested_at, _source, _record_hash) on every row.
--   3. Types are applied at landing (EIA payloads are validated before insert),
--      but business logic (dedup rules, filtering) is deferred to the staging layer.

CREATE TABLE IF NOT EXISTS raw.eia_demand_hourly (
    respondent      text        NOT NULL,   -- EIA balancing authority code, e.g. ERCO
    respondent_name text,
    period_utc      timestamptz NOT NULL,   -- hour beginning, UTC
    demand_mwh      numeric,                -- nullable: EIA occasionally publishes gaps
    _run_id         uuid        NOT NULL,
    _ingested_at    timestamptz NOT NULL DEFAULT now(),
    _source         text        NOT NULL DEFAULT 'eia_api_v2',
    _record_hash    text        NOT NULL,
    CONSTRAINT uq_eia_demand_natural_key UNIQUE (respondent, period_utc)
);

CREATE INDEX IF NOT EXISTS ix_eia_demand_respondent_period
    ON raw.eia_demand_hourly (respondent, period_utc);

CREATE TABLE IF NOT EXISTS raw.eia_generation_hourly (
    respondent      text        NOT NULL,
    respondent_name text,
    fuel_type       text        NOT NULL,   -- EIA fuel code, e.g. NG, WND, SUN
    fuel_type_name  text,
    period_utc      timestamptz NOT NULL,
    generation_mwh  numeric,
    _run_id         uuid        NOT NULL,
    _ingested_at    timestamptz NOT NULL DEFAULT now(),
    _source         text        NOT NULL DEFAULT 'eia_api_v2',
    _record_hash    text        NOT NULL,
    CONSTRAINT uq_eia_generation_natural_key UNIQUE (respondent, fuel_type, period_utc)
);

CREATE INDEX IF NOT EXISTS ix_eia_generation_respondent_period
    ON raw.eia_generation_hourly (respondent, period_utc);

CREATE TABLE IF NOT EXISTS raw.api_regions (
    region_code       text        NOT NULL,
    region_name       text        NOT NULL,
    timezone          text        NOT NULL,
    market_type       text        NOT NULL,
    population_served bigint,
    _run_id           uuid        NOT NULL,
    _ingested_at      timestamptz NOT NULL DEFAULT now(),
    _source           text        NOT NULL DEFAULT 'enrichment_api',
    _record_hash      text        NOT NULL,
    CONSTRAINT uq_api_regions_natural_key UNIQUE (region_code)
);

CREATE TABLE IF NOT EXISTS raw.api_fuel_types (
    fuel_code             text        NOT NULL,
    fuel_name             text        NOT NULL,
    is_renewable          boolean     NOT NULL,
    co2_emission_kg_per_mwh numeric   NOT NULL,
    _run_id               uuid        NOT NULL,
    _ingested_at          timestamptz NOT NULL DEFAULT now(),
    _source               text        NOT NULL DEFAULT 'enrichment_api',
    _record_hash          text        NOT NULL,
    CONSTRAINT uq_api_fuel_types_natural_key UNIQUE (fuel_code)
);

CREATE TABLE IF NOT EXISTS raw.api_demand_forecast (
    region_code   text        NOT NULL,
    period_utc    timestamptz NOT NULL,
    forecast_mwh  numeric     NOT NULL,
    forecast_run  text        NOT NULL,   -- identifies the synthetic forecast vintage
    _run_id       uuid        NOT NULL,
    _ingested_at  timestamptz NOT NULL DEFAULT now(),
    _source       text        NOT NULL DEFAULT 'enrichment_api',
    _record_hash  text        NOT NULL,
    CONSTRAINT uq_api_forecast_natural_key UNIQUE (region_code, period_utc, forecast_run)
);

CREATE INDEX IF NOT EXISTS ix_api_forecast_region_period
    ON raw.api_demand_forecast (region_code, period_utc);
