"""Raw-layer ingestion assets.

Every asset follows the same lifecycle:
    run_id -> resolve fetch window -> fetch + validate -> quarantine rejects
    -> idempotent upsert -> audit row in ops.pipeline_runs -> MaterializeResult

Two retry layers exist by design and act on different failure classes:
  - tenacity inside ingestion.http: transient network/5xx blips within a call
  - Dagster RetryPolicy here: whole-asset failures (e.g. DB connection drop)
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dagster import (
    AssetExecutionContext,
    Backoff,
    MaterializeResult,
    RetryPolicy,
    asset,
)

from ingestion import loaders
from ingestion.eia_client import EiaClient
from ingestion.enrichment_client import EnrichmentClient
from ingestion.logging_config import configure_logging

from ..resources import PipelineConfigResource

configure_logging()
logger = logging.getLogger("assets.ingestion")

_EIA_RETRY = RetryPolicy(max_retries=3, delay=10, backoff=Backoff.EXPONENTIAL)


def _fetch_window(conn, table: str, config) -> tuple[datetime, datetime]:
    """Incremental watermark: pull from max(period) - lookback, else full backfill.

    The lookback re-fetches a trailing window on purpose: EIA revises recent
    hours, and the ON CONFLICT upsert absorbs those revisions in place.
    """
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    end = now - timedelta(hours=2)  # EIA publishes with ~1-2h lag
    watermark = loaders.get_max_period(conn, table)
    if watermark is None:
        start = end - timedelta(days=config.backfill_days)
    else:
        start = watermark - timedelta(hours=config.incremental_lookback_hours)
    return start, end


def _run_ingestion(
    context: AssetExecutionContext,
    pipeline_config: PipelineConfigResource,
    asset_name: str,
    table: str,
    conflict_cols: list[str],
    fetcher,  # (client objects, start, end) -> (records, rejected)
    temporal: bool = True,
) -> MaterializeResult:
    config = pipeline_config.get()
    run_id = uuid4()
    started_at = datetime.now(timezone.utc)

    with loaders.connect(config.database_url) as conn:
        if temporal:
            start, end = _fetch_window(conn, table, config)
        else:
            start, end = None, None
        try:
            records, rejected = fetcher(config, start, end)
            rejected_count = loaders.quarantine(conn, asset_name, rejected, run_id)
            upserted = loaders.upsert_records(conn, table, records, conflict_cols, run_id)
            loaders.record_run(
                conn, run_id, asset_name, "success", upserted, rejected_count,
                start, end, started_at,
            )
        except Exception as exc:
            loaders.record_run(
                conn, run_id, asset_name, "failed", 0, 0, start, end, started_at,
                error_message=str(exc)[:2000],
            )
            raise  # let Dagster's RetryPolicy and failure surfacing take over

    context.log.info(f"{asset_name}: upserted={upserted} rejected={rejected_count}")
    return MaterializeResult(
        metadata={
            "rows_upserted": upserted,
            "rows_rejected": rejected_count,
            "window_start": start.isoformat() if start else None,
            "window_end": end.isoformat() if end else None,
            "demo_mode": config.demo_mode,
        }
    )


# ------------------------------------------------------------------ EIA assets

@asset(group_name="eia", retry_policy=_EIA_RETRY, kinds={"python", "postgres"})
def raw_eia_demand(
    context: AssetExecutionContext, pipeline_config: PipelineConfigResource
) -> MaterializeResult:
    """Hourly electricity demand by balancing authority (EIA RTO region-data)."""
    return _run_ingestion(
        context, pipeline_config,
        asset_name="raw_eia_demand",
        table="raw.eia_demand_hourly",
        conflict_cols=["respondent", "period_utc"],
        fetcher=lambda cfg, s, e: EiaClient(cfg).fetch_demand(s, e),
    )


@asset(group_name="eia", retry_policy=_EIA_RETRY, kinds={"python", "postgres"})
def raw_eia_generation(
    context: AssetExecutionContext, pipeline_config: PipelineConfigResource
) -> MaterializeResult:
    """Hourly generation by fuel type (EIA RTO fuel-type-data)."""
    return _run_ingestion(
        context, pipeline_config,
        asset_name="raw_eia_generation",
        table="raw.eia_generation_hourly",
        conflict_cols=["respondent", "fuel_type", "period_utc"],
        fetcher=lambda cfg, s, e: EiaClient(cfg).fetch_generation(s, e),
    )


# ----------------------------------------------------------- enrichment assets

@asset(group_name="enrichment", kinds={"python", "postgres"})
def raw_enrichment_regions(
    context: AssetExecutionContext, pipeline_config: PipelineConfigResource
) -> MaterializeResult:
    """Region reference data from the enrichment service."""
    return _run_ingestion(
        context, pipeline_config,
        asset_name="raw_enrichment_regions",
        table="raw.api_regions",
        conflict_cols=["region_code"],
        fetcher=lambda cfg, s, e: (EnrichmentClient(cfg).get_regions(), []),
        temporal=False,
    )


@asset(group_name="enrichment", kinds={"python", "postgres"})
def raw_enrichment_fuel_types(
    context: AssetExecutionContext, pipeline_config: PipelineConfigResource
) -> MaterializeResult:
    """Fuel attributes (renewable flag, emission factors) from the enrichment service."""
    return _run_ingestion(
        context, pipeline_config,
        asset_name="raw_enrichment_fuel_types",
        table="raw.api_fuel_types",
        conflict_cols=["fuel_code"],
        fetcher=lambda cfg, s, e: (EnrichmentClient(cfg).get_fuel_types(), []),
        temporal=False,
    )


@asset(group_name="enrichment", kinds={"python", "postgres"})
def raw_enrichment_forecasts(
    context: AssetExecutionContext, pipeline_config: PipelineConfigResource
) -> MaterializeResult:
    """Synthetic hourly demand forecasts, fetched per region over the same window as actuals."""

    def _fetch(cfg, start, end):
        client = EnrichmentClient(cfg)
        records = []
        for region in cfg.eia_respondents:
            records.extend(client.get_forecasts(region, start, end))
        return records, []

    return _run_ingestion(
        context, pipeline_config,
        asset_name="raw_enrichment_forecasts",
        table="raw.api_demand_forecast",
        conflict_cols=["region_code", "period_utc", "forecast_run"],
        fetcher=_fetch,
    )
