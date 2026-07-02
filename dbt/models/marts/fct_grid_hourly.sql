{{
    config(
        materialized='incremental',
        unique_key=['region_key', 'period_utc'],
        incremental_strategy='delete+insert',
    )
}}

-- Grain: one row per (region, hour). Joins actual demand to the synthetic
-- forecast to enable forecast-accuracy analysis.
--
-- Incremental behavior: on each run, only the trailing 3 days are reprocessed
-- (delete+insert on the unique key). The lookback exists because EIA revises
-- recently published hours; 3 days comfortably covers observed revision lag
-- while keeping incremental runs cheap.

with demand as (

    select
        region_code,
        period_utc,
        demand_mwh
    from {{ ref('stg_eia__demand') }}
    {% if is_incremental() %}
    where period_utc >= (select max(period_utc) - interval '3 days' from {{ this }})
    {% endif %}

),

forecast as (

    select
        region_code,
        period_utc,
        forecast_mwh
    from {{ ref('stg_enrichment__forecasts') }}

)

select
    r.region_key,
    d.region_code,
    d.period_utc,
    d.demand_mwh,
    f.forecast_mwh,
    abs(d.demand_mwh - f.forecast_mwh)                        as abs_error_mwh,
    case
        when d.demand_mwh > 0
        then abs(d.demand_mwh - f.forecast_mwh) / d.demand_mwh
    end                                                       as pct_error
from demand d
inner join {{ ref('dim_region') }} r
    on d.region_code = r.region_code
left join forecast f
    on  d.region_code = f.region_code
    and d.period_utc  = f.period_utc
