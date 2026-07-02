"""All report SQL in one reviewable place. Every query reads gold marts or
ops — the report never touches raw/staging, which keeps the medallion
contract honest: presentation consumes gold only."""

DAILY_SUMMARY = """
    select
        region_code,
        summary_date,
        total_demand_mwh,
        peak_demand_mwh,
        mean_abs_pct_error,
        renewable_share,
        est_co2_tonnes,
        is_demand_anomaly
    from marts.agg_daily_region_summary
    where summary_date >= current_date - interval '30 days'
    order by region_code, summary_date
"""

FUEL_MIX_DAILY = """
    select
        region_code,
        period_utc::date        as summary_date,
        fuel_code,
        sum(generation_mwh)     as generation_mwh
    from marts.fct_generation_hourly
    where period_utc >= current_date - interval '30 days'
    group by 1, 2, 3
    order by 1, 2, 3
"""

KPI_HEADLINE = """
    select
        count(distinct region_code)                              as region_count,
        min(summary_date)                                        as period_start,
        max(summary_date)                                        as period_end,
        sum(total_demand_mwh)                                    as total_demand_mwh,
        avg(renewable_share)                                     as avg_renewable_share,
        sum(est_co2_tonnes)                                      as total_co2_tonnes,
        avg(mean_abs_pct_error)                                  as overall_mape,
        count(*) filter (where is_demand_anomaly)                as anomaly_days
    from marts.agg_daily_region_summary
    where summary_date >= current_date - interval '30 days'
"""

REGION_KPIS = """
    select
        region_code,
        sum(total_demand_mwh)                     as total_demand_mwh,
        max(peak_demand_mwh)                      as peak_demand_mwh,
        avg(renewable_share)                      as avg_renewable_share,
        sum(est_co2_tonnes)                       as est_co2_tonnes,
        avg(mean_abs_pct_error)                   as mape,
        count(*) filter (where is_demand_anomaly) as anomaly_days
    from marts.agg_daily_region_summary
    where summary_date >= current_date - interval '30 days'
    group by region_code
    order by total_demand_mwh desc
"""

ANOMALY_DETAIL = """
    select region_code, summary_date, total_demand_mwh
    from marts.agg_daily_region_summary
    where is_demand_anomaly
      and summary_date >= current_date - interval '30 days'
    order by summary_date desc
    limit 10
"""

DATA_FRESHNESS = """
    select
        asset_name,
        max(finished_at)                                   as last_success,
        sum(rows_processed) filter (
            where finished_at >= now() - interval '24 hours'
        )                                                  as rows_last_24h
    from ops.pipeline_runs
    where status = 'success'
    group by asset_name
    order by asset_name
"""
