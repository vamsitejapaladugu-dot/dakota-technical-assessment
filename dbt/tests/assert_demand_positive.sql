-- Gold-layer guard: negative demand in the fact means an upstream filter
-- regressed. (Negative *generation* is legitimate; negative demand is not.)
select region_code, period_utc, demand_mwh
from {{ ref('fct_grid_hourly') }}
where demand_mwh < 0
