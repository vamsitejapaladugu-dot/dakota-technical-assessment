"""EIA client tests: validation/quarantine routing, pagination, retry policy."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from ingestion import http
from ingestion.eia_client import EiaClient, EiaDemandRecord


def _no_sleep():
    """Disable tenacity backoff so retry tests run instantly."""
    http.get_json.retry.sleep = lambda _: None


def test_validation_routes_bad_rows_to_rejected(demo_config, eia_demand_payload):
    rows = eia_demand_payload["response"]["data"]
    valid, rejected = EiaClient._validate(rows, EiaDemandRecord, source="test")
    assert len(valid) == 3
    assert len(rejected) == 1
    payload, reason = rejected[0]
    assert payload["value"] == "not-a-number"
    assert "test" in reason


def test_validated_records_are_typed(demo_config, eia_demand_payload):
    rows = eia_demand_payload["response"]["data"]
    valid, _ = EiaClient._validate(rows, EiaDemandRecord, source="test")
    record = valid[0]
    assert isinstance(record["demand_mwh"], float)
    assert record["period_utc"].tzinfo is not None
    assert record["_record_hash"]


def test_pagination_loops_until_total(monkeypatch, demo_config):
    monkeypatch.setenv("EIA_API_KEY", "fake-key")
    from ingestion.config import load_config

    client = EiaClient(load_config())
    pages = [
        {"response": {"total": 3, "data": [{"a": 1}, {"a": 2}]}},
        {"response": {"total": 3, "data": [{"a": 3}]}},
    ]
    with patch("ingestion.eia_client.get_json", side_effect=pages) as mocked:
        rows = client._fetch_paginated("route/", start=None, end=None, page_length=2)
    assert mocked.call_count == 2
    assert len(rows) == 3


def test_retry_on_500_then_success():
    _no_sleep()
    session = MagicMock()
    ok = MagicMock(status_code=200)
    ok.json.return_value = {"fine": True}
    session.get.side_effect = [MagicMock(status_code=500), MagicMock(status_code=502), ok]
    assert http.get_json(session, "http://x") == {"fine": True}
    assert session.get.call_count == 3


def test_no_retry_on_403():
    _no_sleep()
    session = MagicMock()
    forbidden = MagicMock(status_code=403)
    forbidden.raise_for_status.side_effect = requests.HTTPError("403")
    session.get.return_value = forbidden
    with pytest.raises(requests.HTTPError):
        http.get_json(session, "http://x")
    assert session.get.call_count == 1  # fail fast: no retry budget on auth errors


def test_demo_mode_is_deterministic(demo_config):
    from datetime import datetime, timedelta, timezone

    client = EiaClient(demo_config)
    end = datetime(2026, 6, 2, tzinfo=timezone.utc)
    start = end - timedelta(hours=5)
    first, _ = client.fetch_demand(start, end)
    second, _ = client.fetch_demand(start, end)
    assert first == second
