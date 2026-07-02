-- Sanity bound: region-level MAPE beyond 50% means the forecast join or the
-- synthetic generator is broken, not that forecasting is merely poor.
select region_code, avg(mean_abs_pct_error) as mape
from {{ ref('agg_daily_region_summary') }}
group by region_code
having avg(mean_abs_pct_error) > 0.5
