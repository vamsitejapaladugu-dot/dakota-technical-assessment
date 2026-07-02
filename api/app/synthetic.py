"""Deterministic synthetic data.

Reference data (regions, fuel attributes) is static. Forecasts are generated
on demand from a seeded RNG keyed per (seed, region, hour), so any single hour
is reproducible independently of request order or range boundaries.

Emission factors are rounded lifecycle-combustion approximations in the range
of published EPA eGRID / IPCC figures. They are illustrative enrichment
attributes, not authoritative accounting values.
"""

import math
import random
from datetime import datetime, timedelta, timezone

from .config import settings
from .models import ForecastPoint, FuelType, Region

REGIONS: dict[str, Region] = {
    r.region_code: r
    for r in [
        Region(region_code="ERCO", region_name="Electric Reliability Council of Texas",
               timezone="America/Chicago", market_type="energy_only", population_served=26_000_000),
        Region(region_code="CISO", region_name="California Independent System Operator",
               timezone="America/Los_Angeles", market_type="nodal", population_served=32_000_000),
        Region(region_code="MISO", region_name="Midcontinent Independent System Operator",
               timezone="America/Chicago", market_type="nodal", population_served=45_000_000),
    ]
}

FUEL_TYPES: dict[str, FuelType] = {
    f.fuel_code: f
    for f in [
        FuelType(fuel_code="COL", fuel_name="Coal", is_renewable=False, co2_emission_kg_per_mwh=1000.0),
        FuelType(fuel_code="NG",  fuel_name="Natural Gas", is_renewable=False, co2_emission_kg_per_mwh=450.0),
        FuelType(fuel_code="NUC", fuel_name="Nuclear", is_renewable=False, co2_emission_kg_per_mwh=0.0),
        FuelType(fuel_code="OIL", fuel_name="Petroleum", is_renewable=False, co2_emission_kg_per_mwh=800.0),
        FuelType(fuel_code="SUN", fuel_name="Solar", is_renewable=True, co2_emission_kg_per_mwh=0.0),
        FuelType(fuel_code="WAT", fuel_name="Hydro", is_renewable=True, co2_emission_kg_per_mwh=0.0),
        FuelType(fuel_code="WND", fuel_name="Wind", is_renewable=True, co2_emission_kg_per_mwh=0.0),
        FuelType(fuel_code="OTH", fuel_name="Other", is_renewable=False, co2_emission_kg_per_mwh=600.0),
        FuelType(fuel_code="BAT", fuel_name="Battery Storage", is_renewable=True, co2_emission_kg_per_mwh=0.0),
        FuelType(fuel_code="GEO", fuel_name="Geothermal", is_renewable=True, co2_emission_kg_per_mwh=0.0),
    ]
}

# Baseline hourly demand level per region (MWh), roughly proportional to real
# system sizes so forecast-vs-actual comparisons land in a plausible range.
_REGION_BASELINE_MWH = {"ERCO": 50_000.0, "CISO": 28_000.0, "MISO": 75_000.0}

# Approximate UTC offset used to place the daily peak in local late afternoon.
_REGION_UTC_OFFSET_H = {"ERCO": -6, "CISO": -8, "MISO": -6}


def _hour_floor(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def generate_forecast(region_code: str, start: datetime, end: datetime) -> list[ForecastPoint]:
    baseline = _REGION_BASELINE_MWH[region_code]
    offset = _REGION_UTC_OFFSET_H[region_code]
    forecast_run = f"synthetic-v1-seed{settings.seed}"

    points: list[ForecastPoint] = []
    current = _hour_floor(start)
    end = _hour_floor(end)
    while current <= end:
        local_hour = (current.hour + offset) % 24
        # Daily shape: trough ~04:00 local, peak ~17:00 local.
        daily = 1.0 + 0.22 * math.sin((local_hour - 9) * math.pi / 12)
        # Weekly shape: weekends run ~7% lighter.
        weekly = 0.93 if current.weekday() >= 5 else 1.0
        # Per-hour seeded noise: independent of request order and range.
        rng = random.Random(f"{settings.seed}:{region_code}:{current.isoformat()}")
        noise = rng.gauss(0.0, settings.forecast_noise_pct)

        points.append(
            ForecastPoint(
                region_code=region_code,
                period_utc=current,
                forecast_mwh=round(baseline * daily * weekly * (1.0 + noise), 2),
                forecast_run=forecast_run,
            )
        )
        current += timedelta(hours=1)
    return points
