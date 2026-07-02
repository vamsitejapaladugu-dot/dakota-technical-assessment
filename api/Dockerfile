FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /srv/app

# Dependency layer first for cache efficiency.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app

ENV PATH="/srv/app/.venv/bin:$PATH"

HEALTHCHECK --interval=5s --timeout=3s --retries=10 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health', timeout=2)"

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
