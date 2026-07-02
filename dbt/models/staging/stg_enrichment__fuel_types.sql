select
    fuel_code,
    fuel_name,
    is_renewable,
    co2_emission_kg_per_mwh::numeric as co2_emission_kg_per_mwh,
    _ingested_at
from {{ source('raw', 'api_fuel_types') }}
