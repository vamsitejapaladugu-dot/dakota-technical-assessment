"""Chart rendering. Matplotlib with the Agg backend (no display server in
containers). Charts return file paths; layout/narrative live in the template."""

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

logger = logging.getLogger("reports.charts")

# One muted, consistent palette across all charts.
REGION_COLORS = {"ERCO": "#2f6f8f", "CISO": "#c98a3d", "MISO": "#5f7f5a"}
_FALLBACK = "#777777"

FUEL_COLORS = {
    "NG": "#8f8f8f", "COL": "#4a4a4a", "NUC": "#7d5ba6", "OIL": "#6b4c3a",
    "WND": "#5fa8d3", "SUN": "#e9c46a", "WAT": "#457b9d", "GEO": "#b5651d",
    "BAT": "#2a9d8f", "OTH": "#c0c0c0",
}


def _region_color(code: str) -> str:
    return REGION_COLORS.get(code, _FALLBACK)


def _finish(fig, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    logger.info("chart written path=%s", path)
    return path


def demand_trend(daily_rows: list[dict], out_dir: Path) -> Path:
    """Daily demand per region; anomalous days marked."""
    fig, ax = plt.subplots(figsize=(9, 3.6))
    regions = sorted({r["region_code"] for r in daily_rows})
    for region in regions:
        series = [r for r in daily_rows if r["region_code"] == region]
        dates = [r["summary_date"] for r in series]
        values = [float(r["total_demand_mwh"] or 0) / 1000 for r in series]
        ax.plot(dates, values, label=region, color=_region_color(region), linewidth=1.6)
        anomalies = [r for r in series if r["is_demand_anomaly"]]
        if anomalies:
            ax.scatter(
                [r["summary_date"] for r in anomalies],
                [float(r["total_demand_mwh"]) / 1000 for r in anomalies],
                color="#c0392b", zorder=5, s=28, label=f"{region} anomaly",
            )
    ax.set_ylabel("Daily demand (GWh)")
    ax.legend(fontsize=8, ncols=3)
    ax.grid(alpha=0.25)
    fig.autofmt_xdate(rotation=30)
    return _finish(fig, out_dir / "demand_trend.png")


def fuel_mix(fuel_rows: list[dict], out_dir: Path) -> Path:
    """Stacked daily fuel mix, aggregated across regions."""
    dates = sorted({r["summary_date"] for r in fuel_rows})
    fuels = sorted({r["fuel_code"] for r in fuel_rows})
    by_fuel = {
        fuel: [
            sum(float(r["generation_mwh"] or 0) for r in fuel_rows
                if r["fuel_code"] == fuel and r["summary_date"] == d) / 1000
            for d in dates
        ]
        for fuel in fuels
    }
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.stackplot(
        dates, by_fuel.values(),
        labels=by_fuel.keys(),
        colors=[FUEL_COLORS.get(f, _FALLBACK) for f in fuels],
        alpha=0.9,
    )
    ax.set_ylabel("Generation (GWh)")
    ax.legend(fontsize=7, ncols=5, loc="upper left")
    ax.grid(alpha=0.25)
    fig.autofmt_xdate(rotation=30)
    return _finish(fig, out_dir / "fuel_mix.png")


def renewable_share(region_rows: list[dict], out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(4.4, 3.2))
    regions = [r["region_code"] for r in region_rows]
    shares = [float(r["avg_renewable_share"] or 0) for r in region_rows]
    ax.bar(regions, shares, color=[_region_color(r) for r in regions])
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0))
    ax.set_ylabel("Avg renewable share")
    ax.grid(alpha=0.25, axis="y")
    return _finish(fig, out_dir / "renewable_share.png")


def forecast_accuracy(region_rows: list[dict], out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(4.4, 3.2))
    regions = [r["region_code"] for r in region_rows]
    mapes = [float(r["mape"] or 0) for r in region_rows]
    ax.bar(regions, mapes, color=[_region_color(r) for r in regions])
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0))
    ax.set_ylabel("MAPE (lower is better)")
    ax.grid(alpha=0.25, axis="y")
    return _finish(fig, out_dir / "forecast_accuracy.png")
