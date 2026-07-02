select
    respondent                 as region_code,
    respondent_name,
    fuel_type                  as fuel_code,
    fuel_type_name,
    period_utc,
    generation_mwh::numeric    as generation_mwh,
    _ingested_at
from {{ source('raw', 'eia_generation_hourly') }}
where generation_mwh is not null
