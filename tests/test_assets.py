"""Orchestration tests: the ingestion asset lifecycle with all I/O faked.

Verifies the contract that matters: fetch -> quarantine -> upsert -> audit,
with row counts surfaced as Dagster metadata.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from dagster import build_asset_context

from orchestration.assets import ingestion_assets
from orchestration.resources import PipelineConfigResource


def _fake_conn():
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    return conn


def test_ingestion_asset_lifecycle(monkeypatch):
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    fake_records = [{"respondent": "ERCO"}] * 5
    fake_rejected = [({"bad": True}, "reason")]

    with patch.object(ingestion_assets.loaders, "connect", return_value=_fake_conn()), \
         patch.object(ingestion_assets.loaders, "get_max_period", return_value=None), \
         patch.object(ingestion_assets.loaders, "quarantine", return_value=1) as quarantine, \
         patch.object(ingestion_assets.loaders, "upsert_records", return_value=5) as upsert, \
         patch.object(ingestion_assets.loaders, "record_run") as record_run, \
         patch.object(ingestion_assets, "EiaClient") as client_cls:
        client_cls.return_value.fetch_demand.return_value = (fake_records, fake_rejected)

        result = ingestion_assets.raw_eia_demand(
            build_asset_context(), PipelineConfigResource()
        )

    assert result.metadata["rows_upserted"] == 5
    assert result.metadata["rows_rejected"] == 1
    upsert.assert_called_once()
    quarantine.assert_called_once()
    audit_kwargs = record_run.call_args
    assert "success" in audit_kwargs.args or audit_kwargs.kwargs.get("status") == "success"


def test_ingestion_asset_records_failure(monkeypatch):
    monkeypatch.delenv("EIA_API_KEY", raising=False)

    with patch.object(ingestion_assets.loaders, "connect", return_value=_fake_conn()), \
         patch.object(ingestion_assets.loaders, "get_max_period", return_value=None), \
         patch.object(ingestion_assets.loaders, "record_run") as record_run, \
         patch.object(ingestion_assets, "EiaClient") as client_cls:
        client_cls.return_value.fetch_demand.side_effect = RuntimeError("EIA down")

        try:
            ingestion_assets.raw_eia_demand(build_asset_context(), PipelineConfigResource())
            raised = False
        except RuntimeError:
            raised = True

    assert raised, "asset must re-raise so Dagster retry policy engages"
    assert record_run.call_args.args[3] == "failed" or \
        record_run.call_args.kwargs.get("status") == "failed"


def test_fetch_window_backfills_when_table_empty(monkeypatch):
    monkeypatch.setenv("BACKFILL_DAYS", "30")
    from ingestion.config import load_config

    conn = _fake_conn()
    with patch.object(ingestion_assets.loaders, "get_max_period", return_value=None):
        start, end = ingestion_assets._fetch_window(conn, "raw.x", load_config())
    assert (end - start).days == 30


def test_fetch_window_uses_lookback_when_watermarked(monkeypatch):
    monkeypatch.setenv("INCREMENTAL_LOOKBACK_HOURS", "72")
    from ingestion.config import load_config

    watermark = datetime(2026, 6, 30, 12, tzinfo=timezone.utc)
    conn = _fake_conn()
    with patch.object(ingestion_assets.loaders, "get_max_period", return_value=watermark):
        start, _ = ingestion_assets._fetch_window(conn, "raw.x", load_config())
    assert (watermark - start).total_seconds() == 72 * 3600
