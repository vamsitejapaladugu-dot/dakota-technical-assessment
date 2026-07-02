# Architecture

## Overview

The system is a local, containerized analytics platform with four moving parts:

1. **Enrichment service** (FastAPI) — serves region metadata, fuel attributes
   (renewable flags, CO₂ emission factors), and deterministic synthetic hourly
   demand forecasts.
2. **Ingestion** (Python) — pulls hourly demand and generation-by-fuel data
   from EIA API v2 and all enrichment endpoints; validates, quarantines,
   and idempotently upserts into Postgres.
3. **Transformation** (dbt on PostgreSQL) — medallion-style layers from raw
   to analytics-ready marts, with tests at every layer.
4. **Orchestration & reporting** (Dagster) — one asset graph spanning
   ingestion → dbt models → PDF report, with schedules, retries, and
   data-quality checks.

## Data flow

```
EIA API v2 ─────────────┐
                        ├─► raw schema ─► staging views ─► marts tables ─► PDF report
Enrichment service ─────┘        │                                  ▲
                                 └─► ops schema (audit, quarantine)─┘ (freshness cited in report footer)
```

### Medallion layers

| Layer | Schema | Owner | Contract |
|---|---|---|---|
| Bronze | `raw` | ingestion code | Source-shaped, typed records with lineage columns (`_run_id`, `_ingested_at`, `_source`, `_record_hash`). Append-plus-upsert; never deleted by transformations. |
| Silver | `staging` | dbt (views) | Renamed, cast, analytically filtered (e.g. null/negative demand removed). One model per source entity. |
| Gold | `marts` | dbt (tables) | Dimensional models and aggregates. The report reads **only** from gold. |
| — | `ops` | ingestion code | Run audit + rejected-record quarantine. Not part of the medallion flow; consumed by the report footer and operators. |

Raw-layer uniqueness is enforced *physically* (UNIQUE constraints in
`database/init/02_raw_tables.sql`), which is why staging models don't
re-deduplicate — the invariant is guaranteed below them.

## Orchestration design

Everything is a **Dagster asset**, giving one continuous lineage graph:

- Five ingestion assets (`raw_eia_demand`, `raw_eia_generation`, three
  enrichment assets), each following the same lifecycle:
  *resolve incremental window → fetch → validate → quarantine rejects →
  upsert → write audit row → emit row-count metadata*.
- dbt models load as assets from the manifest via `dagster-dbt`; a custom
  translator maps dbt sources onto the ingestion assets so lineage is
  continuous from API call to report. dbt models materialize under two-part
  asset keys (`staging/...`, `marts/...`) reflecting their schemas.
- `executive_report` depends on the gold marts and renders the PDF.

**Two cadences** reflect the sources' natures: a daily batch schedule for EIA
(the source publishes with lag; daily is the right cost/freshness tradeoff
for analytics), and a 15-minute schedule for the enrichment service
(simulating a frequently-updating internal service). A `full_pipeline` job
runs everything in dependency order for evaluation.

**Failure handling** is layered deliberately:
- tenacity retries *inside* HTTP calls handle transient network/5xx blips
  (exponential backoff + jitter, max 4 attempts, never on 4xx);
- Dagster `RetryPolicy` on EIA assets handles whole-asset failures;
- failed runs still write a `failed` row to `ops.pipeline_runs` before
  re-raising, so the audit trail has no gaps.

## Quality gates

1. **Edge validation:** Pydantic models validate every inbound record; bad
   rows are quarantined with reasons, not dropped or fatal.
2. **Raw-layer asset checks:** row counts (blocking), freshness, null-rate
   thresholds — visible pass/fail in the Dagster UI.
3. **dbt tests via `dbt build`:** tests run interleaved with models, so a
   failing staging test halts before marts build on bad data. 29 tests:
   keys, grains (custom `unique_combination` generic test), relationships,
   accepted values, and singular tests (non-negative demand, forecast
   coverage ≥95%, MAPE sanity bound).

## Deployment shape

Docker Compose runs three services — `postgres` (self-initializing from
`database/init/`), `enrichment-api`, and `dagster` (`dagster dev`:
webserver + daemon in one process, appropriate for local evaluation) — with
health-check-gated startup ordering. The dbt manifest is compiled at image
build time so definitions load deterministically. The report output
directory is volume-mounted to the host.
