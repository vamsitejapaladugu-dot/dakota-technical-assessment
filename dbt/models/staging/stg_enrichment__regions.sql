select
    region_code,
    region_name,
    timezone,
    market_type,
    population_served,
    _ingested_at
from {{ source('raw', 'api_regions') }}
