select
    md5(fuel_code)  as fuel_key,
    fuel_code,
    fuel_name,
    is_renewable,
    co2_emission_kg_per_mwh
from {{ ref('stg_enrichment__fuel_types') }}
