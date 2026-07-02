"""Asset checks on the raw layer: the first quality gate, visible in the UI.

Freshness thresholds are wider in demo mode because synthetic data is
generated up to 'now - 2h' only at materialization time.
"""

from dagster import AssetCheckResult, AssetCheckSeverity, asset_check

from ingestion import loaders
from ingestion.config import load_config

_CHECKS = [
    # (asset_name, table, value_column for null-rate check or None)
    ("raw_eia_demand", "raw.eia_demand_hourly", "demand_mwh"),
    ("raw_eia_generation", "raw.eia_generation_hourly", "generation_mwh"),
    ("raw_enrichment_forecasts", "raw.api_demand_forecast", None),
]


def _make_rowcount_check(asset_name: str, table: str):
    @asset_check(asset=asset_name, name=f"{asset_name}_has_rows", blocking=True)
    def _check() -> AssetCheckResult:
        config = load_config()
        with loaders.connect(config.database_url) as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {table}")
            count = cur.fetchone()[0]
        return AssetCheckResult(
            passed=count > 0,
            metadata={"row_count": count},
            severity=AssetCheckSeverity.ERROR,
        )

    return _check


def _make_freshness_check(asset_name: str, table: str):
    @asset_check(asset=asset_name, name=f"{asset_name}_is_fresh")
    def _check() -> AssetCheckResult:
        config = load_config()
        with loaders.connect(config.database_url) as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT max(period_utc) > now() - interval '48 hours' FROM {table}"
            )
            fresh = bool(cur.fetchone()[0])
        return AssetCheckResult(passed=fresh, severity=AssetCheckSeverity.WARN)

    return _check


def _make_null_rate_check(asset_name: str, table: str, column: str):
    @asset_check(asset=asset_name, name=f"{asset_name}_null_rate_ok")
    def _check() -> AssetCheckResult:
        config = load_config()
        with loaders.connect(config.database_url) as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT coalesce(avg(({column} IS NULL)::int), 0) FROM {table}"
            )
            null_rate = float(cur.fetchone()[0])
        return AssetCheckResult(
            passed=null_rate <= 0.01,
            metadata={"null_rate": round(null_rate, 4)},
            severity=AssetCheckSeverity.WARN,
        )

    return _check


raw_layer_checks = []
for _asset, _table, _value_col in _CHECKS:
    raw_layer_checks.append(_make_rowcount_check(_asset, _table))
    raw_layer_checks.append(_make_freshness_check(_asset, _table))
    if _value_col:
        raw_layer_checks.append(_make_null_rate_check(_asset, _table, _value_col))
