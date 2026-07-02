select
    region_code,
    period_utc,
    forecast_mwh::numeric as forecast_mwh,
    forecast_run,
    _ingested_at
from {{ source('raw', 'api_demand_forecast') }}
