import logging
import time
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Query, Request

from .config import settings
from .models import ForecastPoint, FuelType, HealthResponse, Region
from .synthetic import FUEL_TYPES, REGIONS, generate_forecast

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s enrichment-api %(message)s",
)
logger = logging.getLogger("enrichment-api")

app = FastAPI(
    title="Enrichment Data Service",
    description=(
        "Deterministic synthetic enrichment data for the energy analytics pipeline: "
        "region metadata, fuel attributes, and hourly demand forecasts."
    ),
    version="0.1.0",
)


@app.middleware("http")
async def access_log(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    logger.info(
        "method=%s path=%s status=%s duration_ms=%.1f",
        request.method, request.url.path, response.status_code,
        (time.perf_counter() - started) * 1000,
    )
    return response


@app.get("/health", response_model=HealthResponse, tags=["ops"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="enrichment-api", seed=settings.seed)


@app.get("/regions", response_model=list[Region], tags=["reference"])
def regions() -> list[Region]:
    return list(REGIONS.values())


@app.get("/fuel-types", response_model=list[FuelType], tags=["reference"])
def fuel_types() -> list[FuelType]:
    return list(FUEL_TYPES.values())


@app.get("/forecasts", response_model=list[ForecastPoint], tags=["forecasts"])
def forecasts(
    region: str = Query(..., description="Region code, e.g. ERCO"),
    start: datetime = Query(..., description="Range start (ISO 8601, inclusive)"),
    end: datetime = Query(..., description="Range end (ISO 8601, inclusive)"),
) -> list[ForecastPoint]:
    if region not in REGIONS:
        raise HTTPException(status_code=422, detail=f"Unknown region '{region}'. Known: {sorted(REGIONS)}")
    if end < start:
        raise HTTPException(status_code=422, detail="'end' must not be before 'start'.")
    if end - start > timedelta(days=settings.max_forecast_days):
        raise HTTPException(status_code=422, detail=f"Range exceeds {settings.max_forecast_days} days.")
    return generate_forecast(region, start, end)
