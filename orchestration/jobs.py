from dagster import AssetSelection, define_asset_job

# The evaluator's one-shot path: everything, in dependency order.
full_pipeline_job = define_asset_job(
    name="full_pipeline",
    selection=AssetSelection.all(),
    description="End-to-end run: ingestion -> dbt build -> executive report.",
)

eia_job = define_asset_job(
    name="eia_daily",
    selection=AssetSelection.groups("eia").downstream(),
    description="Daily EIA batch plus all downstream transformations and reporting.",
)

enrichment_job = define_asset_job(
    name="enrichment_refresh",
    selection=AssetSelection.groups("enrichment"),
    description="Frequent refresh of enrichment reference data and forecasts.",
)
