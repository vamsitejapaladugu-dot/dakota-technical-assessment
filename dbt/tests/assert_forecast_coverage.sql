-- At least 95% of demand hours should have a matching forecast. Lower
-- coverage means the forecast ingestion window has drifted from the
-- actuals window — a silent join failure this test makes loud.
with coverage as (
    select
        count(*)                                   as total_hours,
        count(forecast_mwh)                        as forecast_hours
    from {{ ref('fct_grid_hourly') }}
)
select *
from coverage
where forecast_hours::numeric / nullif(total_hours, 0) < 0.95
