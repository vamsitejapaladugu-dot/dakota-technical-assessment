"""Loads every dbt model as a Dagster asset from the dbt manifest.

dagster-dbt wires model dependencies automatically, and the source mapping
below attaches dbt's `raw.*` sources to the ingestion assets above — giving
one continuous lineage graph from API call to gold mart. dbt tests surface
as asset checks in the UI.
"""

from dagster import AssetExecutionContext, AssetKey
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, dbt_assets

from ..resources import DBT_PROJECT_DIR

MANIFEST_PATH = DBT_PROJECT_DIR / "target" / "manifest.json"

_SOURCE_TO_ASSET = {
    "eia_demand_hourly": "raw_eia_demand",
    "eia_generation_hourly": "raw_eia_generation",
    "api_regions": "raw_enrichment_regions",
    "api_fuel_types": "raw_enrichment_fuel_types",
    "api_demand_forecast": "raw_enrichment_forecasts",
}


class PipelineDbtTranslator(DagsterDbtTranslator):
    def get_asset_key(self, dbt_resource_props) -> AssetKey:
        if dbt_resource_props["resource_type"] == "source":
            return AssetKey(_SOURCE_TO_ASSET[dbt_resource_props["name"]])
        return super().get_asset_key(dbt_resource_props)


@dbt_assets(manifest=MANIFEST_PATH, dagster_dbt_translator=PipelineDbtTranslator())
def energy_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()
