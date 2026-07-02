"""Single Dagster entry point (referenced by workspace.yaml)."""

from dagster import Definitions

from .assets.dbt_assets import energy_dbt_assets
from .assets.ingestion_assets import (
    raw_eia_demand,
    raw_eia_generation,
    raw_enrichment_forecasts,
    raw_enrichment_fuel_types,
    raw_enrichment_regions,
)
from .assets.report_asset import executive_report
from .checks.raw_checks import raw_layer_checks
from .jobs import eia_job, enrichment_job, full_pipeline_job
from .resources import PipelineConfigResource, dbt_resource
from .schedules import daily_eia_schedule, enrichment_schedule

defs = Definitions(
    assets=[
        raw_eia_demand,
        raw_eia_generation,
        raw_enrichment_regions,
        raw_enrichment_fuel_types,
        raw_enrichment_forecasts,
        energy_dbt_assets,
        executive_report,
    ],
    asset_checks=raw_layer_checks,
    jobs=[full_pipeline_job, eia_job, enrichment_job],
    schedules=[daily_eia_schedule, enrichment_schedule],
    resources={"pipeline_config": PipelineConfigResource(), "dbt": dbt_resource},
)
