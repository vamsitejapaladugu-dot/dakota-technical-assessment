from datetime import datetime

from pydantic import BaseModel, Field


class Region(BaseModel):
    region_code: str = Field(examples=["ERCO"])
    region_name: str
    timezone: str
    market_type: str
    population_served: int


class FuelType(BaseModel):
    fuel_code: str = Field(examples=["WND"])
    fuel_name: str
    is_renewable: bool
    co2_emission_kg_per_mwh: float


class ForecastPoint(BaseModel):
    region_code: str
    period_utc: datetime
    forecast_mwh: float
    forecast_run: str


class HealthResponse(BaseModel):
    status: str
    service: str
    seed: int
