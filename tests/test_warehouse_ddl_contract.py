# -*- coding: utf-8 -*-
"""Static contract tests for warehouse executable DDL.

These tests intentionally avoid Docker/PostgreSQL so the migration contract can
be checked in normal unit-test runs.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from scripts import apply_warehouse_ddl


REPO_ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_SQL = REPO_ROOT / "sql" / "warehouse"


def read_sql(file_name: str) -> str:
    return (WAREHOUSE_SQL / file_name).read_text(encoding="utf-8")


class WarehouseDdlContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.nds_sql = read_sql("03_nds_tables.sql")
        self.dds_sql = read_sql("04_dds_tables.sql")
        self.dq_sql = read_sql("05_dq_quarantine.sql")
        self.all_sql = "\n".join((self.nds_sql, self.dds_sql, self.dq_sql))
        self.all_sql_lower = self.all_sql.lower()

    def assertRegexIgnoreCase(self, text: str, pattern: str) -> None:
        self.assertRegex(text, re.compile(pattern, re.IGNORECASE | re.DOTALL))

    def test_default_files_include_nds_dds_and_dq_in_dependency_order(self) -> None:
        self.assertEqual(
            apply_warehouse_ddl.DEFAULT_FILES,
            (
                "00_create_schemas.sql",
                "01_audit_metadata.sql",
                "02_staging_tables.sql",
                "03_nds_tables.sql",
                "04_dds_tables.sql",
                "05_dq_quarantine.sql",
            ),
        )

    def test_verification_covers_all_warehouse_schemas(self) -> None:
        self.assertEqual(
            apply_warehouse_ddl.VERIFY_SCHEMAS,
            ("staging", "audit", "dq", "nds", "dds"),
        )

    def test_nds_creates_schema_and_ref_source_system_seed(self) -> None:
        self.assertIn("CREATE SCHEMA IF NOT EXISTS nds;", self.nds_sql)
        self.assertRegexIgnoreCase(
            self.nds_sql,
            r"source_system_code\s+VARCHAR\(50\)\s+PRIMARY\s+KEY",
        )
        self.assertIn("ON CONFLICT (source_system_code) DO UPDATE", self.nds_sql)
        for source_code in (
            "HR_MYSQL",
            "FLEET_MONGODB",
            "DISPATCH_POSTGRES",
            "TLC_FILE",
            "LOOKUP_FILE",
        ):
            self.assertIn(source_code, self.nds_sql)

    def test_nds_trip_key_contract_is_preserved_as_text(self) -> None:
        self.assertRegexIgnoreCase(
            self.nds_sql,
            r"CREATE TABLE IF NOT EXISTS nds\.nds_trip\s*\([^;]*trip_nk\s+TEXT\s+NOT NULL",
        )
        self.assertNotIn("trip_nk VARCHAR", self.nds_sql)

    def test_source_system_code_columns_are_varchar_50_and_fk(self) -> None:
        matches = re.findall(
            r"source_system_code\s+VARCHAR\(50\)\s+NOT\s+NULL\s+REFERENCES\s+nds\.ref_source_system\s*\(source_system_code\)",
            self.all_sql,
            flags=re.IGNORECASE,
        )
        self.assertGreaterEqual(len(matches), 8)

    def test_dds_has_required_facts_and_no_dim_shift(self) -> None:
        self.assertIn("CREATE SCHEMA IF NOT EXISTS dds;", self.dds_sql)
        self.assertRegexIgnoreCase(self.dds_sql, r"CREATE TABLE IF NOT EXISTS dds\.fact_driver_trip")
        self.assertRegexIgnoreCase(self.dds_sql, r"CREATE TABLE IF NOT EXISTS dds\.fact_driver_shift")
        self.assertRegexIgnoreCase(self.dds_sql, r"shift_id\s+VARCHAR\(50\)\s+NOT\s+NULL")
        self.assertNotRegex(self.dds_sql, re.compile(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+dds\.dim_shift", re.IGNORECASE))

    def test_scd2_partial_unique_current_indexes_exist(self) -> None:
        self.assertRegexIgnoreCase(
            self.dds_sql,
            r"CREATE UNIQUE INDEX IF NOT EXISTS ux_dim_driver_current\s+ON dds\.dim_driver \(driver_id\) WHERE is_current",
        )
        self.assertRegexIgnoreCase(
            self.dds_sql,
            r"CREATE UNIQUE INDEX IF NOT EXISTS ux_dim_vehicle_current\s+ON dds\.dim_vehicle \(vehicle_id\) WHERE is_current",
        )
        self.assertIn("CONSTRAINT ux_dim_driver_change_identity", self.dds_sql)
        self.assertIn("CONSTRAINT ux_dim_vehicle_change_identity", self.dds_sql)

    def test_dq_invalid_enum_error_can_be_quarantined(self) -> None:
        self.assertIn("DQ_INVALID_ENUM", self.dq_sql)
        self.assertRegexIgnoreCase(
            self.dq_sql,
            r"severity\s+TEXT\s+NOT NULL DEFAULT 'ERROR'\s+CHECK \(severity = 'ERROR'\)",
        )
        self.assertRegexIgnoreCase(self.dq_sql, r"CREATE TABLE IF NOT EXISTS dq\.quarantine_record")

    def test_no_batch_delete_rollback_pattern_in_scd_tables(self) -> None:
        self.assertNotRegex(self.dds_sql, re.compile(r"DELETE\s+FROM\s+dds\.dim_(driver|vehicle).*batch_id", re.IGNORECASE | re.DOTALL))

    def test_trip_distance_preserves_source_outliers(self) -> None:
        self.assertRegexIgnoreCase(
            self.nds_sql,
            r"trip_distance\s+DECIMAL\(12,\s*4\)",
        )
        self.assertRegexIgnoreCase(
            self.dds_sql,
            r"trip_distance\s+DECIMAL\(12,\s*4\)",
        )


if __name__ == "__main__":
    unittest.main()
