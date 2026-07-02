"""Report tests: insight generation and template rendering with canned data.

PDF conversion (WeasyPrint) is intentionally not unit-tested: it depends on
system libraries and is exercised by `make run` on every pipeline execution.
"""

from datetime import date

from jinja2 import Environment, FileSystemLoader

from reports.generate_report import TEMPLATE_DIR, _build_insights

KPIS = {
    "region_count": 3,
    "period_start": date(2026, 6, 1),
    "period_end": date(2026, 6, 30),
    "total_demand_mwh": 90_000_000.0,
    "avg_renewable_share": 0.31,
    "total_co2_tonnes": 12_500_000.0,
    "overall_mape": 0.142,
    "anomaly_days": 2,
}

REGION_ROWS = [
    {"region_code": "MISO", "total_demand_mwh": 50_000_000.0, "peak_demand_mwh": 98_000.0,
     "avg_renewable_share": 0.21, "est_co2_tonnes": 7_000_000.0, "mape": 0.15, "anomaly_days": 1},
    {"region_code": "ERCO", "total_demand_mwh": 30_000_000.0, "peak_demand_mwh": 72_000.0,
     "avg_renewable_share": 0.33, "est_co2_tonnes": 4_000_000.0, "mape": 0.12, "anomaly_days": 1},
]

ANOMALIES = [{"region_code": "MISO", "summary_date": date(2026, 6, 28), "total_demand_mwh": 2_100_000.0}]


def test_insights_reference_data_facts():
    insights = _build_insights(KPIS, REGION_ROWS, ANOMALIES)
    text = " ".join(insights)
    assert "MISO" in text            # largest region named
    assert "ERCO" in text            # best forecast named
    assert "2 anomalous" in text


def test_insights_handle_no_anomalies():
    insights = _build_insights(KPIS, REGION_ROWS, [])
    assert any("No anomalous" in i for i in insights)


def test_template_renders_kpis_and_demo_banner():
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    template = env.get_template("report.html.j2")
    html = template.render(
        generated_at="2026-07-02 12:00 UTC",
        period="Jun 01 – Jun 30, 2026",
        demo_mode=True,
        kpis=KPIS,
        region_rows=REGION_ROWS,
        insights=_build_insights(KPIS, REGION_ROWS, ANOMALIES),
        charts={k: "file:///dev/null" for k in
                ("demand_trend", "fuel_mix", "renewable_share", "forecast_accuracy")},
        freshness=[],
    )
    assert "Grid Operations Executive Summary" in html
    assert "demo mode" in html
    assert "31%" in html or "0.31" in html or "31" in html  # renewable KPI present
