"""Health, permission, query and metadata smoke tests for the local demo."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import psycopg

from scripts.apply_warehouse_ddl import load_dotenv


ROOT = Path(__file__).resolve().parents[1]


def request_json(url: str, *, data: dict | None = None, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = json.dumps(data).encode("utf-8") if data is not None else None
    request = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def expect_denied(cur: psycopg.Cursor, statement: str) -> None:
    cur.execute("SAVEPOINT permission_test")
    try:
        cur.execute(statement)
    except psycopg.Error:
        cur.execute("ROLLBACK TO SAVEPOINT permission_test")
        return
    cur.execute("ROLLBACK TO SAVEPOINT permission_test")
    raise AssertionError(f"Statement unexpectedly succeeded: {statement}")


def database_smoke_tests() -> dict[str, object]:
    conninfo = {
        "host": "127.0.0.1",
        "port": os.environ.get("POSTGRES_WAREHOUSE_PORT", "5434"),
        "dbname": os.environ["SUPERSET_WAREHOUSE_DB"],
        "user": os.environ["SUPERSET_WAREHOUSE_USER"],
        "password": os.environ["SUPERSET_WAREHOUSE_PASSWORD"],
    }
    results: dict[str, object] = {}
    with psycopg.connect(**conninfo) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user")
            results["warehouse_user"] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*), COALESCE(SUM(total_amount), 0) FROM analytics.trip_pickup")
            trip_count, revenue = cur.fetchone()
            if trip_count <= 0:
                raise AssertionError("analytics.trip_pickup is empty")
            results["trip_count"] = trip_count
            results["total_revenue"] = str(revenue)

            cur.execute("SELECT COUNT(*) FROM analytics.trip_dropoff")
            if cur.fetchone()[0] != trip_count:
                raise AssertionError("pickup/dropoff dataset counts do not match")

            cur.execute("SELECT COUNT(*) FROM analytics.shift")
            results["shift_count"] = cur.fetchone()[0]

            cur.execute("SELECT COALESCE(SUM(issue_count), 0) FROM analytics.dq_summary")
            results["dq_issue_count"] = int(cur.fetchone()[0])

            expect_denied(cur, "SELECT COUNT(*) FROM dds.fact_driver_trip")
            expect_denied(cur, "CREATE TABLE analytics._superset_write_probe(id integer)")
            expect_denied(cur, "INSERT INTO analytics.trip_pickup(trip_id) VALUES ('probe')")
    return results


def superset_smoke_tests() -> dict[str, object]:
    port = os.environ.get("SUPERSET_PORT", "8088")
    base_url = f"http://127.0.0.1:{port}"
    with urllib.request.urlopen(f"{base_url}/health", timeout=30) as response:
        health = response.read().decode("utf-8").strip()
    if health != "OK":
        raise AssertionError(f"Unexpected Superset health response: {health}")

    login = request_json(
        f"{base_url}/api/v1/security/login",
        data={
            "username": os.environ["SUPERSET_ADMIN_USERNAME"],
            "password": os.environ["SUPERSET_ADMIN_PASSWORD"],
            "provider": "db",
            "refresh": True,
        },
    )
    token = login["access_token"]

    dashboard_query = urllib.parse.quote(
        json.dumps({"filters": [{"col": "slug", "opr": "eq", "value": "green-taxi-driver-operations"}]})
    )
    dashboards = request_json(
        f"{base_url}/api/v1/dashboard/?q={dashboard_query}",
        token=token,
    )
    if dashboards.get("count") != 1:
        raise AssertionError("Certified Green Taxi dashboard was not found")

    dataset_query = urllib.parse.quote(
        json.dumps({"filters": [{"col": "schema", "opr": "eq", "value": "analytics"}]})
    )
    datasets = request_json(
        f"{base_url}/api/v1/dataset/?q={dataset_query}",
        token=token,
    )
    dataset_names = {item["table_name"] for item in datasets.get("result", [])}
    expected = {
        "trip_pickup",
        "trip_dropoff",
        "shift",
        "dq_summary",
        "pareto_pickup_zone",
        "driver_performance_summary",
    }
    if not expected.issubset(dataset_names):
        raise AssertionError(f"Missing Superset datasets: {sorted(expected - dataset_names)}")

    dashboard_id = dashboards["result"][0]["id"]
    chart_query = urllib.parse.quote(
        json.dumps(
            {
                "filters": [
                    {"col": "dashboards", "opr": "rel_m_m", "value": dashboard_id}
                ],
                "page_size": 100,
            }
        )
    )
    charts = request_json(f"{base_url}/api/v1/chart/?q={chart_query}", token=token)
    if charts.get("count") != 32:
        raise AssertionError(f"Expected 32 dashboard charts, found {charts.get('count')}")
    viz_types = {item["viz_type"] for item in charts.get("result", [])}
    if "heatmap_v2" not in viz_types or "heatmap" in viz_types:
        raise AssertionError(f"Unexpected heatmap viz types: {sorted(viz_types)}")

    metric_count = 0
    for dataset in datasets.get("result", []):
        if dataset["table_name"] not in expected:
            continue
        detail = request_json(
            f"{base_url}/api/v1/dataset/{dataset['id']}",
            token=token,
        )
        metric_count += len(detail["result"].get("metrics", []))
    if metric_count != 51:
        raise AssertionError(f"Expected 51 metric instances, found {metric_count}")

    dashboard_detail = request_json(
        f"{base_url}/api/v1/dashboard/{dashboard_id}",
        token=token,
    )
    metadata = json.loads(dashboard_detail["result"]["json_metadata"])
    native_filters = metadata.get("native_filter_configuration", [])
    if native_filters:
        raise AssertionError(
            "Superset 6.1.0 native time filters are disabled because its "
            f"time_range API rejects the frontend request; found {len(native_filters)}"
        )

    # Parse position_json and verify the monitoring layout.
    pos_json_str = dashboard_detail["result"].get("position_json")
    if not pos_json_str:
        raise AssertionError("Dashboard position_json is empty")
    pos_json = json.loads(pos_json_str)

    tabs = [k for k, v in pos_json.items() if isinstance(v, dict) and v.get("type") == "TAB"]
    markdown_cards = [
        key
        for key, value in pos_json.items()
        if isinstance(value, dict) and value.get("type") == "MARKDOWN"
    ]

    expected_tabs = {"TAB-1", "TAB-2", "TAB-3", "TAB-4"}
    if not expected_tabs.issubset(set(tabs)):
        raise AssertionError(f"Missing expected dashboard tabs: {expected_tabs - set(tabs)}")

    if markdown_cards:
        raise AssertionError(f"Dashboard must not contain narrative cards: {markdown_cards}")

    required_charts = {
        "Monthly Revenue & Trip Volume": "echarts_timeseries_line",
        "Demand by Weekday & Hour": "heatmap_v2",
        "Zone Concentration by Trips": "table",
        "Driver Performance Matrix": "bubble",
        "Driver Review Queue": "table",
        "DQ Issues over Time": "echarts_timeseries_line",
    }
    chart_by_name = {
        chart["slice_name"]: chart for chart in charts.get("result", [])
    }
    for chart_name, expected_viz_type in required_charts.items():
        chart = chart_by_name.get(chart_name)
        if chart is None:
            raise AssertionError(f"Missing required chart: {chart_name}")
        if chart["viz_type"] != expected_viz_type:
            raise AssertionError(
                f"{chart_name} must use {expected_viz_type}, found {chart['viz_type']}"
            )

    c_driver_table = chart_by_name["Driver Review Queue"]
    driver_params = json.loads(c_driver_table.get("params") or "{}")
    driver_filters = driver_params.get("adhoc_filters", [])
    if not any(
        item.get("filterOptionName") == "driver_review_rule"
        and item.get("subject") == "needs_review"
        and item.get("comparator") is True
        for item in driver_filters
    ):
        raise AssertionError("Driver Review Queue is missing its peer-review filter")

    # 3. Check benchmark results file
    bench_file = ROOT / "deliverables" / "benchmark" / "superset_benchmark_results.json"
    if not bench_file.exists():
        raise AssertionError(f"Benchmark results file not found at: {bench_file}")

    with open(bench_file, "r", encoding="utf-8") as bf:
        bench_data = json.load(bf)
    if bench_data.get("total_charts") != 32:
        raise AssertionError(
            f"Expected benchmark to cover 32 charts, found {bench_data.get('total_charts')}"
        )
    if len(bench_data.get("charts", {})) != 32:
        raise AssertionError(
            f"Benchmark contains {len(bench_data.get('charts', {}))} charts, expected 32"
        )

    return {
        "health": health,
        "dashboard_count": dashboards["count"],
        "dataset_count": len(expected),
        "metric_instance_count": metric_count,
        "chart_count": charts["count"],
        "native_filter_count": len(native_filters),
    }


def main() -> int:
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / ".env.superset")
    try:
        database_results = database_smoke_tests()
        superset_results = superset_smoke_tests()
    except (AssertionError, KeyError, psycopg.Error, urllib.error.URLError) as exc:
        print(f"Superset smoke tests failed: {exc}", file=sys.stderr)
        return 1

    print("Superset smoke tests passed.")
    print(json.dumps({**database_results, **superset_results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
