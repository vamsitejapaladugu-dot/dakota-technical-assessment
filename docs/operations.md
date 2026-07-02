# Operations

## Logging

All components share one line format (configured in
`ingestion/logging_config.py`):

```
2026-07-02 14:03:11 INFO eia_client route=... offset=0 fetched=5000 total=6480
```

Component loggers: `eia_client`, `enrichment_client`, `loaders`,
`assets.ingestion`, `reports.*`, plus the enrichment service's access log
(method, path, status, duration_ms). View with `make logs` (Dagster
container) or `docker compose logs enrichment-api`.

## Retries — two layers, two failure classes

| Layer | Scope | Policy | Handles |
|---|---|---|---|
| tenacity (`ingestion/http.py`) | single HTTP call | exponential backoff + jitter, max 4 attempts; retries 429/5xx/connection/timeout; **never retries other 4xx** | transient network blips, rate limits, upstream hiccups |
| Dagster `RetryPolicy` | whole asset | 3 retries, exponential, EIA assets | mid-run infrastructure failures (DB drop, container restart) |

Auth failures (403) fail on the first attempt by design: a bad key cannot
succeed on retry, and fast failure gives the operator an actionable error
immediately.

## Failure modes and what happens

| Failure | Behavior |
|---|---|
| EIA unreachable / 5xx storm | tenacity retries → asset fails → Dagster retries → if still failing, run marked failed; `ops.pipeline_runs` row written with `status='failed'` and the error message **before** re-raising |
| Malformed source records | Row-level: validated out, quarantined to `ops.rejected_records` with reason; batch proceeds. Proven in development: a warn-level dbt test surfaced real fuel codes (`BAT`, `GEO`) missing from the enrichment reference; the gap was visible, not silent, and the fix was one line in the service (now pinned by a unit test). |
| dbt test failure | `dbt build` interleaves tests with models: a staging test failure halts before marts build on bad data; error severity fails the Dagster asset |
| Report queries return nothing | Explicit `RuntimeError` with instruction to run the pipeline — not an empty PDF |
| Postgres down at start | Compose health checks gate startup ordering; `make run` waits via `--wait` |

## Data quality — three gates

1. **Edge (Pydantic):** every inbound record validated; failures quarantined
   with reasons.
2. **Raw layer (Dagster asset checks):** rows present (blocking), freshness
   ≤48h (warn), null-rate ≤1% on measure columns (warn). Results visible
   per-materialization in the UI.
3. **Transform layer (dbt, 29 tests):** key uniqueness, composite grains
   (custom `unique_combination` test), relationships, accepted values,
   non-negative demand, forecast coverage ≥95%, MAPE sanity bound (<50%),
   plus source freshness config.

## Re-run strategy

Everything is idempotent; the recovery procedure for any failure is **run it
again** (UI: materialize the failed asset and downstream; CLI: `make run`).

- Raw: natural-key UNIQUE + `ON CONFLICT` upserts — re-ingestion overwrites,
  never duplicates.
- Facts: `delete+insert` incremental on unique keys with a 3-day lookback.
- Backfills: `make psql` → truncate the relevant raw table(s) → next run
  detects the empty watermark and backfills `BACKFILL_DAYS` automatically.
  Full reset: `make clean && make run`.

## Monitoring

Locally observable today: Dagster UI (run history, per-asset materialization
metadata — row counts, fetch windows — and check pass/fails as first-class
UI state) plus the `ops.pipeline_runs` audit table for SQL-queryable history:

```sql
select asset_name, status, rows_processed, rows_rejected, finished_at
from ops.pipeline_runs order by finished_at desc limit 20;
```

The report footer cites per-asset freshness — a stale report announces
itself. Production additions (documented, deliberately not built locally):
Dagster failure sensors → Slack/PagerDuty, freshness SLAs via
`FreshnessPolicy`, and metrics export.
