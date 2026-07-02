select
    md5(region_code)  as region_key,
    region_code,
    region_name,
    timezone,
    market_type,
    population_served
from {{ ref('stg_enrichment__regions') }}
