{{
    config(
        materialized='incremental',
        unique_key=['region_key', 'fuel_key', 'period_utc'],
        incremental_strategy='delete+insert',
    )
}}

-- Grain: one row per (region, fuel, hour). The join to dim_fuel_type is the
-- enrichment payoff: emission factors turn raw generation into estimated CO2.

with generation as (

    select
        region_code,
        fuel_code,
        period_utc,
        generation_mwh
    from {{ ref('stg_eia__generation') }}
    {% if is_incremental() %}
    where period_utc >= (select max(period_utc) - interval '3 days' from {{ this }})
    {% endif %}

)

select
    r.region_key,
    ft.fuel_key,
    g.region_code,
    g.fuel_code,
    g.period_utc,
    g.generation_mwh,
    ft.is_renewable,
    g.generation_mwh * ft.co2_emission_kg_per_mwh             as est_co2_kg
from generation g
inner join {{ ref('dim_region') }} r
    on g.region_code = r.region_code
inner join {{ ref('dim_fuel_type') }} ft
    on g.fuel_code = ft.fuel_code
