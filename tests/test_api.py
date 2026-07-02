"""Enrichment service tests: contract shapes, validation, and determinism."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FORECAST_PARAMS = {
    "region": "ERCO",
    "start": "2026-06-01T00:00:00Z",
    "end": "2026-06-01T23:00:00Z",
}


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_regions_shape():
    body = client.get("/regions").json()
    codes = {r["region_code"] for r in body}
    assert {"ERCO", "CISO", "MISO"} <= codes
    assert all("population_served" in r for r in body)


def test_fuel_types_include_discovered_codes():
    """BAT and GEO were added after real EIA data surfaced them; this pins
    the fix so the reference set cannot silently regress."""
    codes = {f["fuel_code"] for f in client.get("/fuel-types").json()}
    assert {"NG", "WND", "SUN", "BAT", "GEO"} <= codes


def test_forecast_determinism():
    first = client.get("/forecasts", params=FORECAST_PARAMS).json()
    second = client.get("/forecasts", params=FORECAST_PARAMS).json()
    assert first == second
    assert len(first) == 24


def test_forecast_unknown_region_rejected():
    response = client.get("/forecasts", params={**FORECAST_PARAMS, "region": "NOPE"})
    assert response.status_code == 422


def test_forecast_inverted_range_rejected():
    response = client.get(
        "/forecasts",
        params={**FORECAST_PARAMS, "start": "2026-06-02T00:00:00Z", "end": "2026-06-01T00:00:00Z"},
    )
    assert response.status_code == 422
