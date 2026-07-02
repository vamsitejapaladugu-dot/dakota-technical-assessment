# Architecture decisions

Format: decision, reasoning, tradeoffs accepted. These are the choices an
evaluator is most likely to question.

## Dagster over Airflow

**Decision:** orchestrate with Dagster software-defined assets.

**Reasoning:** the pipeline is fundamentally a dependency graph of *data
artifacts* (raw tables → models → report), which is exactly Dagster's asset
abstraction. Concretely, that buys: first-class dbt integration
(`dagster-dbt` loads every model as an asset, with dbt tests surfacing as
checks — one lineage graph from API call to PDF); asset checks as a native
data-quality primitive; materialization metadata (row counts, fetch windows)
recorded per run in the UI; and a light local footprint — one container runs
webserver and daemon, versus Airflow's scheduler/webserver/metadata-DB
spread, which matters for a project evaluators run on laptops.

**Tradeoffs:** Airflow has a larger operator ecosystem and hiring pool. For
task-centric, integration-heavy workloads it remains a fine choice; nothing
here depends on Dagster-only capabilities, and the ingestion layer is
deliberately orchestrator-agnostic (plain Python, no Dagster imports), so
switching would touch only the `orchestration/` package.

## PostgreSQL as the warehouse

**Decision:** a single Postgres 16 instance holds all layers.

**Reasoning:** the evaluator must run this locally; Postgres is the only
serious zero-cost, zero-account option with full dbt support. At this volume
(~100–200K raw rows for 30 days × 3 regions) it is comfortably
overqualified. Schemas (`raw`/`staging`/`marts`/`ops`) provide the layer
isolation that databases would provide in a cloud warehouse.

**Tradeoffs:** row-store Postgres is not a columnar analytics engine. At
production scale the marts layer would move to a warehouse (Snowflake,
BigQuery, Databricks SQL) or Postgres would gain partitioning — see
"deferred" below.

## dbt for transformations

**Decision:** all transformation logic lives in dbt; ingestion writes only
to `raw`.

**Reasoning:** SQL transformations with version control, testing, lineage,
and docs generation. The staging/marts split keeps cleaning rules separate
from business logic. Tests-as-code (29 of them) make the quality bar
executable rather than aspirational.

**Tradeoffs:** none material at this scope. We deliberately use **no dbt
packages**: the two utilities needed (composite-key uniqueness, schema
routing) are ~10-line macros, and each package is another network
dependency during evaluator setup.

## FastAPI for the enrichment service

**Decision:** a small FastAPI service with three endpoints and **fully
deterministic** synthetic data (seeded per `(seed, region, hour)`).

**Reasoning:** FastAPI gives Pydantic-validated contracts and free OpenAPI
docs. Determinism is the important choice: independent runs — including the
evaluator's — produce identical enrichment data, so results are reproducible
and diffable. Per-hour seeding (rather than sequence-based RNG) means any
window is reproducible regardless of request order or range boundaries.

**Tradeoffs:** synthetic forecasts are generic sinusoids, so forecast error
against real grid data is realistic-looking but not meaningful as an actual
forecast benchmark. The report treats MAPE as a *pipeline capability
demonstration*, and says so.

## Medallion architecture (and why not straight Kimball)

**Decision:** raw → staging → marts schemas, with dims/facts *inside* the
gold layer.

**Reasoning:** medallion answers "how does data flow and where is it
trustworthy"; Kimball answers "how is the analytical layer shaped." They
compose: bronze preserves the source faithfully (replayable, auditable),
silver applies fitness rules once, and gold is dimensional
(`dim_region`, `dim_fuel_type`, two facts, one aggregate). Skipping bronze
would couple ingestion to modeling; skipping dimensional modeling in gold
would push joins and business rules into the report.

**Tradeoffs:** three layers is one more hop than the minimum. Worth it even
at this scale for the replay property alone: every silver/gold structure can
be rebuilt from bronze without re-calling APIs.

## Two other choices worth defending

**Validation-with-quarantine over fail-fast:** a 5,000-row EIA batch with
one malformed row loads 4,999 rows and quarantines one with a reason in
`ops.rejected_records`. Rationale: availability of good data shouldn't be
hostage to a source's worst record — but nothing is silently dropped.

**`delete+insert` incremental strategy with a 3-day lookback:** EIA revises
recently published hours. Each incremental run reprocesses a trailing
window, and upserts absorb revisions in place. The lookback size trades
compute for revision coverage; 3 days comfortably exceeds observed revision
lag at negligible cost.

## Deliberately deferred (and what production would add)

- **Table partitioning:** unnecessary below millions of rows; at scale,
  native range partitioning on `period_utc` (or a columnar engine).
- **Great Expectations:** would duplicate what Pydantic + asset checks +
  dbt tests already cover, at the cost of a heavy dependency and config
  surface. Three native mechanisms beat four overlapping ones.
- **Streaming ingestion:** EIA publishes hourly with lag; a 15-minute
  schedule already exceeds the source's real freshness.
- **Secrets management:** local `.env` is appropriate here; production would
  use a secrets manager and never bake credentials into images (this project
  doesn't either — keys enter only via environment).
- **Alerting:** failures are visible in the UI and audit table; production
  would add failure sensors paging to Slack/PagerDuty.
