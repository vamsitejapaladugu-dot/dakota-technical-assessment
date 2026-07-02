FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# WeasyPrint system libraries (report generation runs inside this container).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/pipeline

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY ingestion ./ingestion
COPY orchestration ./orchestration
COPY reports ./reports
COPY dbt ./dbt

ENV PATH="/opt/pipeline/.venv/bin:$PATH" \
    DAGSTER_HOME=/opt/dagster_home \
    PYTHONPATH=/opt/pipeline

RUN mkdir -p $DAGSTER_HOME && cp orchestration/dagster.yaml $DAGSTER_HOME/

# Parse the dbt project at build time so the manifest exists before
# definitions.py loads it. --no-partial-parse keeps it hermetic.
RUN cd dbt && dbt parse --no-partial-parse --profiles-dir .

EXPOSE 3000
CMD ["dagster", "dev", "-w", "orchestration/workspace.yaml", "--host", "0.0.0.0", "--port", "3000"]
