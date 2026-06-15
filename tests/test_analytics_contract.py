"""Static contract tests for certified analytics documentation and SQL views."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "analytics" / "01_certified_datasets.sql"
SEMANTIC_PATH = ROOT / "docs" / "analytics" / "semantic-contract.md"
METRIC_PATH = ROOT / "docs" / "analytics" / "metric-catalog.md"
DICTIONARY_PATH = ROOT / "docs" / "warehouse" / "dds-data-dictionary.md"
TRACEABILITY_PATH = ROOT / "docs" / "analytics" / "requirements-traceability.md"


class AnalyticsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = SQL_PATH.read_text(encoding="utf-8")
        cls.semantic = SEMANTIC_PATH.read_text(encoding="utf-8")
        cls.metrics = METRIC_PATH.read_text(encoding="utf-8")
        cls.dictionary = DICTIONARY_PATH.read_text(encoding="utf-8")
        cls.traceability = TRACEABILITY_PATH.read_text(encoding="utf-8")

    def test_expected_views_are_declared(self) -> None:
        for view_name in (
            "analytics.trip_pickup",
            "analytics.trip_dropoff",
            "analytics.shift",
            "analytics.shift_trip_aggregate",
            "analytics.dq_summary",
        ):
            self.assertIn(f"CREATE OR REPLACE VIEW {view_name}", self.sql)

    def test_new_time_dimensions_are_exposed(self) -> None:
        self.assertIn("pickup_hour", self.sql.lower())
        self.assertIn("pickup_day_of_week", self.sql.lower())
        self.assertIn("pickup_day_name", self.sql.lower())
        self.assertIn("shift_start_hour", self.sql.lower())
        self.assertIn("shift_start_day_name", self.sql.lower())

    def test_sql_is_read_only_and_explicit(self) -> None:
        self.assertNotRegex(self.sql.upper(), r"\bSELECT\s+\*")
        self.assertNotRegex(self.sql.upper(), r"\b(INSERT|UPDATE|DELETE|TRUNCATE)\b")
        self.assertNotIn("dim_shift", self.sql.lower())

    def test_shift_aggregate_has_protected_grain(self) -> None:
        aggregate = self.sql.split(
            "CREATE OR REPLACE VIEW analytics.shift_trip_aggregate AS", 1
        )[1].split("CREATE OR REPLACE VIEW analytics.dq_summary AS", 1)[0]
        self.assertRegex(aggregate, r"GROUP BY\s+shift_id")
        self.assertNotIn("fact_driver_shift", aggregate)

    def test_required_metrics_are_certified(self) -> None:
        required = {
            "total_trips",
            "completed_shifts",
            "total_revenue",
            "fare_revenue",
            "total_tips",
            "total_distance",
            "total_trip_minutes",
            "average_fare",
            "average_trip_distance",
            "average_trip_duration",
            "trips_per_shift",
            "revenue_per_shift",
            "revenue_per_hour",
            "occupied_minutes",
            "idle_minutes",
            "shift_duration_minutes",
            "utilization_rate",
            "anomaly_trip_count",
            "anomaly_shift_count",
            "anomaly_rate",
            "active_driver_count",
            "active_vehicle_count",
        }
        documented = set(re.findall(r"\| `([a-z0-9_]+)` \|", self.metrics))
        self.assertTrue(required.issubset(documented), required - documented)

    def test_ratio_and_revenue_decisions_are_locked(self) -> None:
        self.assertIn(
            "SUM(occupied_minutes) / NULLIF(SUM(shift_duration_minutes),0)",
            self.metrics,
        )
        self.assertIn("SUM(total_amount)", self.metrics)
        self.assertIn("SUM(fare_amount)", self.metrics)
        self.assertIn("không phải số master có trạng thái `ACTIVE`", self.semantic)

    def test_date_roles_and_dq_boundary_are_explicit(self) -> None:
        self.assertIn("`pickup_datetime`", self.semantic)
        self.assertIn("`dropoff_datetime`", self.semantic)
        self.assertIn("`shift_start`", self.semantic)
        self.assertIn("`shift_end`", self.semantic)
        self.assertIn("`analytics.dq_summary`", self.semantic)
        self.assertNotIn("USERELATIONSHIP", self.semantic)

    def test_final_dictionary_matches_current_dds_contract(self) -> None:
        self.assertIn("**9 bảng, 107 cột**", self.dictionary)
        for table_name in (
            "dim_date",
            "dim_time",
            "dim_driver",
            "dim_vehicle",
            "dim_vendor",
            "dim_location",
            "dim_junk_trip",
            "fact_driver_trip",
            "fact_driver_shift",
        ):
            self.assertIn(f"`dds.{table_name}`", self.dictionary)
        self.assertFalse(
            (ROOT / "docs" / "drafts" / "21-data-dictionary.draft.md").exists()
        )

    def test_traceability_is_reconciled_and_tool_independent(self) -> None:
        self.assertNotIn("PENDING_RECONCILIATION", self.traceability)
        self.assertNotIn("Power BI", self.traceability)
        self.assertIn("analytics.shift_trip_aggregate", self.traceability)


if __name__ == "__main__":
    unittest.main()
