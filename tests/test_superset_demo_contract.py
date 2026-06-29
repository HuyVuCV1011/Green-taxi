"""Static contract tests for the reproducible Superset local demo."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SupersetDemoContractTests(unittest.TestCase):
    def test_compose_pins_superset_and_has_healthcheck(self) -> None:
        compose = (ROOT / "docker-compose.superset.yml").read_text(encoding="utf-8")
        dockerfile = (ROOT / "docker" / "superset" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        self.assertIn("apache/superset:6.1.0", dockerfile)
        self.assertIn("psycopg2-binary==2.9.11", dockerfile)
        self.assertIn("superset_metadata_db:", compose)
        self.assertIn("superset_init:", compose)
        self.assertIn("superset_app:", compose)
        self.assertIn("/health", compose)

    def test_readonly_role_exposes_only_analytics(self) -> None:
        grants = (
            ROOT / "sql" / "analytics" / "02_superset_readonly_role.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("GRANT USAGE ON SCHEMA analytics TO superset_ro", grants)
        self.assertIn("GRANT SELECT ON ALL TABLES IN SCHEMA analytics", grants)
        for schema in ("staging", "audit", "dq", "nds", "dds"):
            self.assertIn(schema, grants)
        self.assertNotIn("GRANT SELECT ON ALL TABLES IN SCHEMA dds", grants)

    def test_certified_datasets_and_monitoring_dashboard_are_provisioned(self) -> None:
        script = (ROOT / "scripts" / "provision_superset.py").read_text(
            encoding="utf-8"
        )
        for dataset in (
            "trip_pickup",
            "trip_dropoff",
            "shift",
            "dq_summary",
            "pareto_pickup_zone",
            "driver_performance_summary",
            "olap_trip_cube",
            "olap_shift_cube",
            "driver_segments",
            "route_association_rules",
        ):
            self.assertIn(f'"{dataset}"', script)
        for metric in (
            "total_trips",
            "total_revenue",
            "utilization_rate",
            "revenue_per_hour",
            "anomaly_rate",
            "dq_issue_count",
            "quarantine_count",
        ):
            self.assertIn(f'"{metric}"', script)
        self.assertIn("if metric_name not in definitions", script)
        self.assertIn("green-taxi-driver-operations", script)
        self.assertIn("GreenTaxiViewer", script)
        self.assertIn("SUPERSET_VIEWER_PASSWORD", script)
        self.assertIn("CERTIFIED_BY", script)
        self.assertIn("CHART_DESCRIPTIONS", script)
        self.assertIn("BQ01 demand heatmap", script)
        self.assertIn('"heatmap_v2"', script)
        self.assertNotIn('"heatmap", {', script)
        self.assertIn('"native_filter_configuration": []', script)
        self.assertNotIn('"filterType": "filter_time"', script)
        self.assertIn("from werkzeug.security import generate_password_hash", script)
        self.assertIn("viewer.password = generate_password_hash(password)", script)
        self.assertIn("driver_review_rule", script)
        self.assertIn("db.session.delete(slc)", script)
        self.assertNotIn('"type": "MARKDOWN"', script)
        self.assertIn('"x_axis": "pickup_weekday_label"', script)
        self.assertIn('"groupby": "pickup_weekday_label"', script)
        self.assertIn("Driver Performance Matrix", script)
        self.assertIn("Average Trip Distance by Borough", script)
        self.assertIn("OLAP Slice - Monthly Pickup Borough Revenue", script)
        self.assertIn("OLAP Dice - Month Borough Vehicle", script)
        self.assertIn("OLAP Drill-down - Time Hierarchy", script)
        self.assertIn("OLAP Roll-up - Zone to Borough Utilization", script)
        self.assertIn("OLAP Pivot - Borough by Hour Bucket", script)
        self.assertIn("Total Segmented Drivers", script)
        self.assertIn("Total Rules Found", script)
        self.assertIn("Driver Segments Analysis", script)
        self.assertIn("Driver Segments Profile", script)
        self.assertIn("Top Route & Demand Association Rules", script)
        self.assertIn('"pivot_table_v2"', script)
        self.assertIn("#f4f6f8", script)

    def test_smoke_suite_checks_read_and_write_boundaries(self) -> None:
        smoke = (ROOT / "scripts" / "smoke_test_superset.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("/health", smoke)
        self.assertIn("/api/v1/security/login", smoke)
        self.assertIn("analytics.trip_pickup", smoke)
        self.assertIn("dds.fact_driver_trip", smoke)
        self.assertIn("CREATE TABLE analytics._superset_write_probe", smoke)
        self.assertIn('"dq_summary"', smoke)
        self.assertIn("Expected 42 dashboard charts", smoke)
        self.assertIn("Expected 88 metric instances", smoke)
        self.assertIn("Benchmark artifact is stale", smoke)
        self.assertIn('"benchmark_is_current"', smoke)
        self.assertIn("if native_filters:", smoke)

    def test_warehouse_has_dashboard_shared_memory(self) -> None:
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("shm_size: 1gb", compose)


if __name__ == "__main__":
    unittest.main()
