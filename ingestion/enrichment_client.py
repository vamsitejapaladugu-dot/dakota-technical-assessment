"""Typed client for the local enrichment service.

Models are intentionally redeclared here rather than imported from api/:
the two components are separately deployable, and each side validating its
own contract is exactly how this would work across a real service boundary.
"""

import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from .config import Config
from .eia_client import record_hash
from .http import get_json, make_session

logger = logging.getLogger("enrichment_client")


class RegionRecord(BaseModel):
    region_code: str
    region_name: str
    timezone: str
    market_type: str
    population_served: int


class FuelTypeRecord(BaseModel):
    fuel_code: str
    fuel_name: str
    is_renewable: bool
    co2_emission_kg_per_mwh: float


class ForecastRecord(BaseModel):
    region_code: str
    period_utc: datetime
    forecast_mwh: float
    forecast_run: str


class EnrichmentClient:
    def __init__(self, config: Config):
        self._base = config.enrichment_api_url.rstrip("/")
        self._session = make_session()

    def _get_validated(self, path: str, model: type[BaseModel], params: dict | None = None) -> list[dict[str, Any]]:
        payload = get_json(self._session, f"{self._base}{path}", params)
        records = []
        for row in payload:
            record = model.model_validate(row).model_dump()
            record["_record_hash"] = record_hash(row)
            records.append(record)
        logger.info("path=%s records=%s", path, len(records))
        return records

    def get_regions(self) -> list[dict[str, Any]]:
        return self._get_validated("/regions", RegionRecord)

    def get_fuel_types(self) -> list[dict[str, Any]]:
        return self._get_validated("/fuel-types", FuelTypeRecord)

    def get_forecasts(self, region: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
        return self._get_validated(
            "/forecasts",
            ForecastRecord,
            params={"region": region, "start": start.isoformat(), "end": end.isoformat()},
        )
