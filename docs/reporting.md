# Reporting

## Business questions

The executive summary (`reports/output/executive_summary_<date>.pdf`)
answers, for ERCOT, CAISO, and MISO over the trailing 30 days:

1. **How is demand trending, and which days were anomalous?** Daily demand
   per region with anomaly markers (\|day − 14-day rolling mean\| > 2.5σ).
2. **What is the fuel mix?** Stacked daily generation by fuel, plus average
   renewable share per region.
3. **What are the emissions consequences?** Estimated CO₂ from generation ×
   per-fuel emission factors (enrichment data).
4. **How good are the demand forecasts?** MAPE per region, actuals vs. the
   enrichment service's forecast.

## Metric definitions

| Metric | Definition | Source |
|---|---|---|
| Total / peak demand | sum / max of hourly `demand_mwh` per day | `fct_grid_hourly` |
| Renewable share | renewable generation ÷ total generation | `fct_generation_hourly` via `dim_fuel_type.is_renewable` |
| Est. CO₂ | Σ `generation_mwh × co2_emission_kg_per_mwh` | enrichment emission factors |
| MAPE | mean of hourly \|actual − forecast\| ÷ actual | `fct_grid_hourly.pct_error` |
| Anomaly day | daily total beyond 2.5 rolling σ (14-day window, current day excluded) | `agg_daily_region_summary` |

## Generation approach

Gold marts → SQL (all queries in `reports/queries.py`; the report never
reads raw/staging) → matplotlib charts → Jinja2 HTML → WeasyPrint PDF. The
intermediate HTML is kept beside the PDF for debugging. Runs identically as
the `executive_report` Dagster asset or standalone
(`python -m reports.generate_report`).

"Key findings" are rule-based restatements of query results — each sentence
maps to a queryable fact, so the narrative cannot drift from the data.

## How to interpret it honestly

- **Emission figures are estimates** from illustrative per-fuel factors
  (rounded from public reference ranges), suitable for comparing regions and
  trends, not for regulatory accounting. The report footer says so.
- **MAPE will look mediocre (~10–25%)** because the forecast is synthetic
  (seasonal shape + noise) while actuals are real grid data. That is the
  point: the pipeline demonstrates forecast-accuracy *measurement*; the
  forecast itself is a stand-in. In demo mode, MAPE is much lower because
  actuals and forecasts share structure.
- **Anomaly flags need history:** the rolling window can't flag the first
  days of a fresh backfill; expect few or no anomalies until the window
  fills.
- **Demo mode is watermarked** with a banner; absence of the banner means
  real EIA data.
