"""Benchmark query performance of the provisioned Superset dashboard charts.

This script executes REST API calls to measure load times, warm-ups,
and P95 response times. Results are saved in deliverables/benchmark/.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
from scripts.apply_warehouse_ddl import load_dotenv


def calculate_p95(runs: list[float]) -> float:
    if not runs:
        return 0.0
    sorted_runs = sorted(runs)
    idx = int(math.ceil(len(sorted_runs) * 0.95)) - 1
    return sorted_runs[max(0, idx)]


def main() -> int:
    # Ensure UTF-8 output on Windows consoles
    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / ".env.superset")

    port = os.environ.get("SUPERSET_PORT", "8088")
    base_url = f"http://127.0.0.1:{port}"

    print("=" * 70)
    print("      NYC GREEN TAXI BI - SUPERSET CHART PERFORMANCE BENCHMARK")
    print("=" * 70)

    # 1. Login
    print("Authenticating with Superset REST API...")
    headers = {"Content-Type": "application/json"}
    login_payload = json.dumps({
        "username": os.environ["SUPERSET_ADMIN_USERNAME"],
        "password": os.environ["SUPERSET_ADMIN_PASSWORD"],
        "provider": "db",
        "refresh": True,
    }).encode("utf-8")

    req = urllib.request.Request(f"{base_url}/api/v1/security/login", data=login_payload, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            token = res["access_token"]
        print("Login successful. Access token obtained.")
    except Exception as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        return 1

    # 2. Get Dashboard ID
    print("Resolving dashboard 'green-taxi-driver-operations'...")
    q = urllib.parse.quote(json.dumps({
        "filters": [{"col": "slug", "opr": "eq", "value": "green-taxi-driver-operations"}]
    }))
    req = urllib.request.Request(f"{base_url}/api/v1/dashboard/?q={q}", headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            dashboards = json.loads(resp.read().decode("utf-8"))
            if dashboards["count"] == 0:
                print("Dashboard not found!", file=sys.stderr)
                return 1
            db_id = dashboards["result"][0]["id"]
            db_title = dashboards["result"][0]["dashboard_title"]
            print(f"Found Dashboard: '{db_title}' (ID: {db_id})")
    except Exception as e:
        print(f"Failed to query dashboard: {e}", file=sys.stderr)
        return 1

    # 3. Get all charts (slices) of the dashboard
    print("Querying all charts belonging to the dashboard...")
    q_chart = urllib.parse.quote(json.dumps({
        "filters": [{"col": "dashboards", "opr": "rel_m_m", "value": db_id}],
        "page_size": 100
    }))
    req = urllib.request.Request(f"{base_url}/api/v1/chart/?q={q_chart}", headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            charts_res = json.loads(resp.read().decode("utf-8"))
            charts = charts_res.get("result", [])
            print(f"Total charts to benchmark: {len(charts)}")
    except Exception as e:
        print(f"Failed to query charts: {e}", file=sys.stderr)
        return 1

    if not charts:
        print("No charts found on dashboard to benchmark.", file=sys.stderr)
        return 1

    # 4. Perform Benchmark
    results = {}
    failed_charts = []
    total_charts = len(charts)

    print("\nStarting benchmark execution (2 warm-ups + 20 runs per chart)...")
    print("-" * 75)
    print(f"{'No.':<4} | {'Chart Name':<45} | {'Min (s)':<8} | {'Avg (s)':<8} | {'P95 (s)':<8}")
    print("-" * 75)

    for idx, chart in enumerate(charts, 1):
        chart_id = chart["id"]
        chart_name = chart["slice_name"]

        # Warm-up (2 runs)
        url = f"{base_url}/api/v1/chart/{chart_id}/data/"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})

        # Warm-up 1
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp.read()
        except Exception as e:
            print(f"\nWarning: Warm-up 1 failed for '{chart_name}': {e}", file=sys.stderr)

        # Warm-up 2
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp.read()
        except Exception as e:
            pass

        # Measurement Runs (20 runs)
        runs = []
        for run_idx in range(20):
            start_time = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    resp.read()
                duration = time.perf_counter() - start_time
                runs.append(duration)
            except Exception as e:
                print(f"\nError: Run {run_idx+1} failed for '{chart_name}': {e}", file=sys.stderr)
                break
            # Small cool down
            time.sleep(0.05)

        if len(runs) == 20:
            min_t = min(runs)
            max_t = max(runs)
            avg_t = sum(runs) / len(runs)
            p95_t = calculate_p95(runs)

            results[chart_name] = {
                "chart_id": chart_id,
                "viz_type": chart.get("viz_type"),
                "min": min_t,
                "max": max_t,
                "avg": avg_t,
                "p95": p95_t,
                "runs": runs
            }
            # Shorten chart name for display if needed
            disp_name = chart_name[:42] + "..." if len(chart_name) > 45 else chart_name
            print(f"{idx:<4} | {disp_name:<45} | {min_t:<8.3f} | {avg_t:<8.3f} | {p95_t:<8.3f}")
        else:
            print(f"{idx:<4} | {chart_name[:45]:<45} | Failed to complete 20 runs.")
            failed_charts.append(chart_name)

    # 5. Summarize and Write Output
    if failed_charts:
        print("\nBenchmark failed; some charts did not complete all runs:", file=sys.stderr)
        for chart_name in failed_charts:
            print(f"  - {chart_name}", file=sys.stderr)
        print("Existing benchmark artifact was left unchanged.", file=sys.stderr)
        return 1

    if results:
        overall_p95 = sum(r["p95"] for r in results.values()) / len(results)
        max_p95_chart = max(results.keys(), key=lambda k: results[k]["p95"])
        max_p95_val = results[max_p95_chart]["p95"]

        print("-" * 75)
        print(f"Benchmark Summary:")
        print(f"  - Overall Average P95 Load Time: {overall_p95:.3f} seconds")
        print(f"  - Slowest Chart (P95): '{max_p95_chart}' ({max_p95_val:.3f} seconds)")
        print("-" * 75)

        # Save to deliverables/benchmark/
        dest_dir = ROOT / "deliverables" / "benchmark"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / "superset_benchmark_results.json"

        output_data = {
            "dashboard_slug": "green-taxi-driver-operations",
            "dashboard_id": db_id,
            "total_charts": len(results),
            "summary": {
                "overall_average_p95": overall_p95,
                "slowest_chart_p95": {
                    "chart_name": max_p95_chart,
                    "p95": max_p95_val
                }
            },
            "charts": results
        }

        dest_file.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nSuccessfully saved benchmark results to: {dest_file.resolve()}")
    else:
        print("\nBenchmark failed; no results recorded.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
