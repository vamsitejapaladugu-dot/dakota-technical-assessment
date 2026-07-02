-- Grain: one row per (region, day). The report reads almost exclusively
-- from this model.
--
-- Anomaly definition: |daily total - 14-day rolling mean| > 2.5 rolling
-- stddev. Simple, explainable, and window-function-only: appropriate rigor
-- for an executive flag, not a forecasting system.

with daily as (

    select
        region_key,
        region_code,
        period_utc::date                         as summary_date,
        sum(demand_mwh)                          as total_demand_mwh,
        max(demand_mwh)                          as peak_demand_mwh,
        avg(pct_error)                           as mean_abs_pct_error
    from {{ ref('fct_grid_hourly') }}
    group by 1, 2, 3

),

daily_generation as (

    select
        region_key,
        period_utc::date                                              as summary_date,
        sum(generation_mwh)                                           as total_generation_mwh,
        sum(generation_mwh) filter (where is_renewable)               as renewable_generation_mwh,
        sum(est_co2_kg) / 1000.0                                      as est_co2_tonnes
    from {{ ref('fct_generation_hourly') }}
    group by 1, 2

),

with_rolling as (

    select
        d.*,
        avg(d.total_demand_mwh) over (
            partition by d.region_key
            order by d.summary_date
            rows between 14 preceding and 1 preceding
        )                                        as rolling_mean_demand,
        stddev_samp(d.total_demand_mwh) over (
            partition by d.region_key
            order by d.summary_date
            rows between 14 preceding and 1 preceding
        )                                        as rolling_stddev_demand
    from daily d

)

select
    w.region_key,
    w.region_code,
    w.summary_date,
    w.total_demand_mwh,
    w.peak_demand_mwh,
    w.mean_abs_pct_error,
    g.total_generation_mwh,
    g.renewable_generation_mwh,
    case
        when g.total_generation_mwh > 0
        then g.renewable_generation_mwh / g.total_generation_mwh
    end                                          as renewable_share,
    g.est_co2_tonnes,
    coalesce(
        w.rolling_stddev_demand > 0
        and abs(w.total_demand_mwh - w.rolling_mean_demand) > 2.5 * w.rolling_stddev_demand,
        false
    )                                            as is_demand_anomaly
from with_rolling w
left join daily_generation g
    on  w.region_key   = g.region_key
    and w.summary_date = g.summary_date
