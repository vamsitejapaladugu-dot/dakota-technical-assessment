"""Shared test setup.

The enrichment service is a separate uv project (api/), so its package is not
installed in the root environment; adding api/ to sys.path lets the test
suite exercise it in-process via FastAPI's TestClient without containers.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "api"))

FIXTURES = ROOT / "ingestion" / "fixtures"


@pytest.fixture()
def eia_demand_payload() -> dict:
    return json.loads((FIXTURES / "eia_demand_sample.json").read_text())


@pytest.fixture()
def eia_generation_payload() -> dict:
    return json.loads((FIXTURES / "eia_generation_sample.json").read_text())


@pytest.fixture()
def demo_config(monkeypatch):
    """Config with no EIA key (demo mode) and inert connection targets."""
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    from ingestion.config import load_config

    return load_config()
