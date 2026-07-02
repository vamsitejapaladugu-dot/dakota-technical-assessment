"""Executive summary generation: gold marts -> charts -> HTML -> PDF.

Runs identically as a Dagster asset or standalone:
    uv run python -m reports.generate_report
The intermediate HTML is kept next to the PDF for debugging and for
evaluators without a PDF viewer handy.
"""

import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from jinja2 import Environment, FileSystemLoader

from ingestion.config import load_config
from ingestion.logging_config import configure_logging

from . import charts, queries

logger = logging.getLogger("reports.generate")

TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = Path(__file__).parent / "output"


def _fetch_all(conn, sql: str) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql)
        return cur.fetchall()


def _fetch_one(conn, sql: str) -> dict:
    return _fetch_all(conn, sql)[0]


def _build_insights(kpis: dict, region_rows: list[dict], anomalies: list[dict]) -> list[str]:
    """Rule-based one-liners. Deliberately simple: each insight is a direct
    restatement of a queryable fact, so nothing in the narrative can drift
    from the data."""
    insights = []
    if region_rows:
        top = region_rows[0]
        insights.append(
            f"{top['region_code']} accounted for the largest share of demand "
            f"({float(top['total_demand_mwh']) / 1000:,.0f} GWh over the period)."
        )
        greenest = max(region_rows, key=lambda r: float(r["avg_renewable_share"] or 0))
        insights.append(
            f"{greenest['region_code']} led on renewable share at "
            f"{float(greenest['avg_renewable_share'] or 0):.0%} of generation."
        )
        best_forecast = min(region_rows, key=lambda r: float(r["mape"] or 1))
        insights.append(
            f"Demand forecasts were most accurate for {best_forecast['region_code']} "
            f"(MAPE {float(best_forecast['mape'] or 0):.1%})."
        )
    if anomalies:
        latest = anomalies[0]
        insights.append(
            f"{int(kpis['anomaly_days'])} anomalous demand day(s) flagged; most recent: "
            f"{latest['region_code']} on {latest['summary_date']:%b %d}."
        )
    else:
        insights.append("No anomalous demand days detected in the reporting window.")
    return insights


def build_report(output_dir: Path = OUTPUT_DIR) -> tuple[Path, str]:
    configure_logging()
    config = load_config()
    output_dir.mkdir(parents=True, exist_ok=True)

    with psycopg.connect(config.database_url) as conn:
        kpis = _fetch_one(conn, queries.KPI_HEADLINE)
        daily = _fetch_all(conn, queries.DAILY_SUMMARY)
        fuel = _fetch_all(conn, queries.FUEL_MIX_DAILY)
        regions = _fetch_all(conn, queries.REGION_KPIS)
        anomalies = _fetch_all(conn, queries.ANOMALY_DETAIL)
        freshness = _fetch_all(conn, queries.DATA_FRESHNESS)

    if not daily:
        raise RuntimeError(
            "No rows in marts.agg_daily_region_summary — run the pipeline (dbt build) first."
        )

    with tempfile.TemporaryDirectory() as tmp:
        chart_dir = Path(tmp)
        chart_paths = {
            "demand_trend": charts.demand_trend(daily, chart_dir),
            "fuel_mix": charts.fuel_mix(fuel, chart_dir),
            "renewable_share": charts.renewable_share(regions, chart_dir),
            "forecast_accuracy": charts.forecast_accuracy(regions, chart_dir),
        }

        env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
        template = env.get_template("report.html.j2")
        period = f"{kpis['period_start']:%b %d} – {kpis['period_end']:%b %d, %Y}"
        html = template.render(
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            period=period,
            demo_mode=config.demo_mode,
            kpis=kpis,
            region_rows=regions,
            insights=_build_insights(kpis, regions, anomalies),
            charts={name: path.as_uri() for name, path in chart_paths.items()},
            freshness=freshness,
        )

        html_path = output_dir / "executive_summary.html"
        html_path.write_text(html)

        from weasyprint import HTML  # deferred: heavy import, needs system libs

        pdf_path = output_dir / f"executive_summary_{datetime.now(timezone.utc):%Y%m%d}.pdf"
        HTML(string=html, base_url=str(chart_dir)).write_pdf(pdf_path)

    logger.info("report generated pdf=%s period=%s", pdf_path, period)
    return pdf_path, period


if __name__ == "__main__":
    path, period = build_report()
    print(f"Report written: {path} ({period})")
