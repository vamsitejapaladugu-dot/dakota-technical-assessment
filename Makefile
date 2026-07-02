# Evaluation interface. Typical flow:
#   make setup    one-time: env file + images
#   make run      end-to-end pipeline, writes reports/output/*.pdf
#   make test     unit tests (no Docker or database required)
#   make report   regenerate the report + dbt docs
#   make clean    remove containers, volumes, and generated outputs

SHELL := /bin/bash
COMPOSE := docker compose

.PHONY: setup run test report clean logs psql dbt-docs

setup:
	@command -v docker >/dev/null || { echo "ERROR: docker is required"; exit 1; }
	@test -f .env || { cp .env.example .env; echo "Created .env from .env.example (edit to add EIA_API_KEY)"; }
	$(COMPOSE) build
	@echo "Setup complete. Next: make run"

run:
	$(COMPOSE) up -d --wait
	@echo "Services healthy. Executing full pipeline (first run ingests $${BACKFILL_DAYS:-30} days; allow a few minutes)..."
	$(COMPOSE) exec dagster dagster job execute -m orchestration.definitions -j full_pipeline
	@echo ""
	@echo "Pipeline complete."
	@echo "  Report:     $$(ls -t reports/output/*.pdf 2>/dev/null | head -1)"
	@echo "  Dagster UI: http://localhost:3000  (asset graph, checks, run history)"
	@echo "  API docs:   http://localhost:8001/docs"

test:
	uv sync --quiet
	uv run pytest

report:
	$(COMPOSE) exec dagster python -m reports.generate_report
	$(COMPOSE) exec dagster bash -c "cd dbt && dbt docs generate --profiles-dir ."
	@echo "Report: $$(ls -t reports/output/*.pdf | head -1)"

clean:
	$(COMPOSE) down -v
	rm -rf reports/output/* dbt/target dbt/logs
	@echo "Cleaned containers, volumes, and generated outputs."

# --- conveniences (not part of the required interface) -------------------

logs:
	$(COMPOSE) logs -f dagster

psql:
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-dakota} -d $${POSTGRES_DB:-energy}

dbt-docs:
	$(COMPOSE) exec dagster bash -c "cd dbt && dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir . --host 0.0.0.0 --port 8080"
