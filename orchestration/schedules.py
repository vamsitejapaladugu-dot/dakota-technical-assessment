from dagster import ScheduleDefinition

from .jobs import eia_job, enrichment_job

# Two deliberately different cadences:
#   - EIA: daily batch (source publishes hourly data with lag; daily pull is
#     the right cost/freshness tradeoff for an analytics-grade mart)
#   - Enrichment: every 15 minutes (simulates a frequently-updating service)
daily_eia_schedule = ScheduleDefinition(
    job=eia_job, cron_schedule="0 6 * * *", execution_timezone="UTC",
)

enrichment_schedule = ScheduleDefinition(
    job=enrichment_job, cron_schedule="*/15 * * * *", execution_timezone="UTC",
)
