-- Typed, renamed pass over raw demand. Rows with null demand are excluded
-- here (not deleted upstream): the raw layer preserves the source faithfully,
-- the silver layer applies analytical fitness rules.

select
    respondent                as region_code,
    respondent_name,
    period_utc,
    demand_mwh::numeric       as demand_mwh,
    _ingested_at
from {{ source('raw', 'eia_demand_hourly') }}
where demand_mwh is not null
  and demand_mwh >= 0
