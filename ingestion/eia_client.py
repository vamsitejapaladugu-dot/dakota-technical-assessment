"""EIA API v2 client for hourly RTO demand and generation-by-fuel data.

Notes on the source:
  - frequency=hourly returns UTC period stamps in the form 'YYYY-MM-DDTHH'.
  - Responses are paginated; 'length' caps at 5000 rows, so fetches loop on
    'offset' until the reported total is exhausted.
  - Records failing validation are returned for quarantine, not raised:
    one malformed row must not sink a 5000-row batch.

Demo mode: with no EIA_API_KEY, deterministic synthetic 'actuals' are
generated locally so the full pipeline can be evaluated without credentials.
This is clearly logged and documented in the README.
"""

import hashlib
import json
import logging
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from .config import Config
from .http import get_json, make_session

logger = logging.getLogger("eia_client")

PAGE_LENGTH = 5000
_PERIOD_FORMAT = "%Y-%m-%dT%H"

RejectedRecord = tuple[dict[str, Any], str]  # (raw payload, reason)


class EiaDemandRecord(BaseModel):
    respondent: str
    respondent_name: str | None = Field(default=None, alias="respondent-name")
    period_utc: datetime = Field(alias="period")
    demand_mwh: float | None = Field(default=None, alias="value")

    @field_validator("period_utc", mode="before")
    @classmethod
    def _parse_period(cls, v: Any) -> datetime:
        if isinstance(v, str):
            return datetime.strptime(v, _PERIOD_FORMAT).replace(tzinfo=timezone.utc)
        return v

    @field_validator("demand_mwh", mode="before")
    @classmethod
    def _coerce_value(cls, v: Any) -> float | None:
        return None if v in (None, "") else float(v)


class EiaGenerationRecord(BaseModel):
    respondent: str
    respondent_name: str | None = Field(default=None, alias="respondent-name")
    fuel_type: str = Field(alias="fueltype")
    fuel_type_name: str | None = Field(default=None, alias="type-name")
    period_utc: datetime = Field(alias="period")
    generation_mwh: float | None = Field(default=None, alias="value")

    @field_validator("period_utc", mode="before")
    @classmethod
    def _parse_period_v(cls, v: Any) -> datetime:
        if isinstance(v, str):
            return datetime.strptime(v, _PERIOD_FORMAT).replace(tzinfo=timezone.utc)
        return v

    @field_validator("generation_mwh", mode="before")
    @classmethod
    def _coerce_value(cls, v: Any) -> float | None:
        return None if v in (None, "") else float(v)


def record_hash(record: dict[str, Any]) -> str:
    canonical = json.dumps(record, sort_keys=True, default=str)
    return hashlib.md5(canonical.encode()).hexdigest()


class EiaClient:
    def __init__(self, config: Config):
        self._config = config
        self._session = make_session()

    # ------------------------------------------------------------------ fetch

    def fetch_demand(
        self, start: datetime, end: datetime
    ) -> tuple[list[dict[str, Any]], list[RejectedRecord]]:
        if self._config.demo_mode:
            logger.warning("EIA_API_KEY not set -> DEMO MODE: synthesizing demand data.")
            return self._demo_demand(start, end), []
        raw = self._fetch_paginated(
            route="electricity/rto/region-data/data/",
            start=start,
            end=end,
            extra_facets={"type": ["D"]},  # D = demand
        )
        return self._validate(raw, EiaDemandRecord, source="eia_demand")

    def fetch_generation(
        self, start: datetime, end: datetime
    ) -> tuple[list[dict[str, Any]], list[RejectedRecord]]:
        if self._config.demo_mode:
            logger.warning("EIA_API_KEY not set -> DEMO MODE: synthesizing generation data.")
            return self._demo_generation(start, end), []
        raw = self._fetch_paginated(
            route="electricity/rto/fuel-type-data/data/",
            start=start,
            end=end,
        )
        return self._validate(raw, EiaGenerationRecord, source="eia_generation")

    # -------------------------------------------------------------- internals

    def _fetch_paginated(
        self,
        route: str,
        start: datetime,
        end: datetime,
        extra_facets: dict[str, list[str]] | None = None,
        page_length: int = PAGE_LENGTH,
    ) -> list[dict[str, Any]]:
        url = f"{self._config.eia_base_url}/{route}"
        params: dict[str, Any] = {
            "api_key": self._config.eia_api_key,
            "frequency": "hourly",
            "data[0]": "value",
            "start": start.strftime(_PERIOD_FORMAT) if start else "",
            "end": end.strftime(_PERIOD_FORMAT) if end else "",
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "length": page_length,
        }
        for i, respondent in enumerate(self._config.eia_respondents):
            params[f"facets[respondent][{i}]"] = respondent
        for facet, values in (extra_facets or {}).items():
            for i, value in enumerate(values):
                params[f"facets[{facet}][{i}]"] = value

        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            payload = get_json(self._session, url, {**params, "offset": offset})
            batch = payload.get("response", {}).get("data", [])
            total = int(payload.get("response", {}).get("total", 0))
            rows.extend(batch)
            logger.info(
                "route=%s offset=%s fetched=%s total=%s", route, offset, len(batch), total
            )
            offset += page_length
            if not batch or offset >= total:
                return rows

    @staticmethod
    def _validate(
        raw_rows: list[dict[str, Any]],
        model: type[BaseModel],
        source: str,
    ) -> tuple[list[dict[str, Any]], list[RejectedRecord]]:
        valid: list[dict[str, Any]] = []
        rejected: list[RejectedRecord] = []
        for row in raw_rows:
            try:
                record = model.model_validate(row).model_dump()
                record["_record_hash"] = record_hash(row)
                valid.append(record)
            except ValidationError as exc:
                rejected.append((row, f"{source}: {exc.errors()[0]['msg']}"))
        if rejected:
            logger.warning("source=%s rejected=%s of %s rows", source, len(rejected), len(raw_rows))
        return valid, rejected

    # -------------------------------------------------------------- demo mode

    _DEMO_BASELINE = {"ERCO": 50_000.0, "CISO": 28_000.0, "MISO": 75_000.0}
    _DEMO_FUEL_SHARES = {  # crude but plausible average mixes
        "ERCO": {"NG": 0.42, "WND": 0.24, "SUN": 0.09, "COL": 0.13, "NUC": 0.10, "OTH": 0.02},
        "CISO": {"NG": 0.38, "SUN": 0.20, "WAT": 0.12, "WND": 0.11, "NUC": 0.08, "OTH": 0.11},
        "MISO": {"COL": 0.30, "NG": 0.33, "WND": 0.14, "NUC": 0.14, "WAT": 0.02, "OTH": 0.07},
    }

    def _demo_hours(self, start: datetime, end: datetime):
        current = start.replace(minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        while current <= end:
            yield current
            current += timedelta(hours=1)

    def _demo_demand_value(self, respondent: str, hour: datetime) -> float:
        local_hour = (hour.hour - 6) % 24
        daily = 1.0 + 0.22 * math.sin((local_hour - 9) * math.pi / 12)
        weekly = 0.93 if hour.weekday() >= 5 else 1.0
        rng = random.Random(f"demo-actuals:{respondent}:{hour.isoformat()}")
        return round(self._DEMO_BASELINE[respondent] * daily * weekly * (1 + rng.gauss(0, 0.05)), 2)

    def _demo_demand(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        records = []
        for respondent in self._config.eia_respondents:
            for hour in self._demo_hours(start, end):
                row = {
                    "respondent": respondent,
                    "respondent_name": f"{respondent} (demo)",
                    "period_utc": hour,
                    "demand_mwh": self._demo_demand_value(respondent, hour),
                }
                row["_record_hash"] = record_hash(row)
                records.append(row)
        return records

    def _demo_generation(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        records = []
        for respondent in self._config.eia_respondents:
            shares = self._DEMO_FUEL_SHARES[respondent]
            for hour in self._demo_hours(start, end):
                demand = self._demo_demand_value(respondent, hour)
                solar_shape = max(0.0, math.sin((hour.hour - 12) * math.pi / 12) + 0.2)
                for fuel, share in shares.items():
                    value = demand * share * (solar_shape if fuel == "SUN" else 1.0)
                    row = {
                        "respondent": respondent,
                        "respondent_name": f"{respondent} (demo)",
                        "fuel_type": fuel,
                        "fuel_type_name": fuel,
                        "period_utc": hour,
                        "generation_mwh": round(value, 2),
                    }
                    row["_record_hash"] = record_hash(row)
                    records.append(row)
        return records


if __name__ == "__main__":  # smoke test: fetch the last 6 hours
    from .logging_config import configure_logging
    from .config import load_config

    configure_logging()
    client = EiaClient(load_config())
    end = datetime.now(timezone.utc) - timedelta(hours=2)  # EIA publishes with lag
    records, rejects = client.fetch_demand(end - timedelta(hours=6), end)
    logger.info("smoke: demand records=%s rejected=%s", len(records), len(rejects))
    if records:
        logger.info("sample: %s", records[0])
