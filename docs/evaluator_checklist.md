# Evaluator checklist

A 10-minute path through every assessment requirement.

## Run it (3 commands)

```bash
make setup          # creates .env — optionally add EIA_API_KEY
make run            # end-to-end; first run ~2–4 min
make test           # 19 unit tests, no Docker/DB/network needed
```

## Verify each requirement

| Requirement | Where to look |
|---|---|
| FastAPI service (health check, docs) | http://localhost:8001/docs — try `/health`, `/forecasts` |
| Ingestion w/ error handling, retries, logging | `ingestion/http.py` (retry policy), `ingestion/eia_client.py` (validation/quarantine), `make logs` |
| Orchestration, two cadences | http://localhost:3000 → Overview → Schedules (daily EIA, 15-min enrichment); Assets → lineage graph |
| Database design + init scripts | `database/init/*.sql`; ER diagram: `docs/er_diagram.png` |
| Medallion dbt transformations | `dbt/models/{staging,marts}`; incremental facts: `fct_*.sql` |
| Data quality tests | `make run` output shows 29 dbt tests; asset checks in UI; `select * from ops.rejected_records;` |
| Automated reporting (PDF) | `reports/output/executive_summary_<date>.pdf` |
| Documentation | `docs/` + this file |
| Docker Compose, uv, startup script | `docker-compose.yml`, `pyproject.toml`/`uv.lock`, `run.sh`/`run.bat`/`Makefile` |
| Idempotency (bonus) | run `make run` twice — second run is incremental, zero errors |
| Audit trail (bonus) | `make psql` → `select * from ops.pipeline_runs order by finished_at desc;` |

## Design rationale shortcuts

Why Dagster / Postgres / dbt / medallion / no Great Expectations →
`docs/decisions.md`. Data model and grains → `docs/data_model.md`.
Failure modes and re-runs → `docs/operations.md`.
