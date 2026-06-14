# -*- coding: utf-8 -*-
"""Unit tests for the MonitoringRepository class."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.monitoring.repository import MonitoringRepository, sanitize_for_display


class TestMonitoringRepository(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = MonitoringRepository()

    @patch("pymysql.connect")
    @patch("src.monitoring.repository.MongoClient")
    @patch("psycopg2.connect")
    def test_test_connections_success(self, mock_psycopg, mock_mongo, mock_mysql) -> None:
        # Arrange
        mock_mysql.return_value = MagicMock()
        mock_mongo_client = MagicMock()
        mock_mongo.return_value = mock_mongo_client
        mock_psycopg.return_value = MagicMock()

        # Act
        results = self.repo.test_connections()

        # Assert
        self.assertTrue(results["mysql_hr"]["connected"])
        self.assertTrue(results["mongodb_fleet"]["connected"])
        self.assertTrue(results["postgres_dispatch"]["connected"])
        self.assertTrue(results["postgres_warehouse"]["connected"])
        self.assertIsNone(results["mysql_hr"]["error"])

    @patch("pymysql.connect")
    @patch("src.monitoring.repository.MongoClient")
    @patch("psycopg2.connect")
    def test_test_connections_failure(self, mock_psycopg, mock_mongo, mock_mysql) -> None:
        # Arrange
        mock_mysql.side_effect = Exception("MySQL connection failed with password=supersecret")
        mock_mongo.side_effect = Exception("Mongo connection failed")
        mock_psycopg.side_effect = Exception("Postgres connection failed")

        # Act
        results = self.repo.test_connections()

        # Assert
        self.assertFalse(results["mysql_hr"]["connected"])
        self.assertFalse(results["mongodb_fleet"]["connected"])
        self.assertFalse(results["postgres_dispatch"]["connected"])
        self.assertFalse(results["postgres_warehouse"]["connected"])

        # Check secret sanitization
        self.assertNotIn("supersecret", results["mysql_hr"]["error"])
        self.assertIn("***", results["mysql_hr"]["error"])

    def test_get_source_sample_whitelist_validation(self) -> None:
        # Accessing an unauthorized system/entity should raise ValueError
        with self.assertRaises(ValueError):
            self.repo.get_source_sample("mysql_hr", "unauthorized_table")

        with self.assertRaises(ValueError):
            self.repo.get_source_sample("invalid_system", "drivers")

    @patch("pymysql.connect")
    def test_get_source_sample_limit_coercion_and_param(self, mock_mysql) -> None:
        # Arrange
        mock_conn = MagicMock()
        mock_mysql.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [("driver_id",), ("display_name",)]
        mock_cursor.fetchall.return_value = [("DRV000001", "Driver A")]

        # Act - pass limit greater than 100
        results = self.repo.get_source_sample("mysql_hr", "drivers", limit=150)

        # Assert limit was coerced to 100
        mock_cursor.execute.assert_called_with("SELECT * FROM drivers LIMIT %s", (100,))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["driver_id"], "DRV000001")

        # Act - pass limit less than 1
        self.repo.get_source_sample("mysql_hr", "drivers", limit=-5)
        mock_cursor.execute.assert_called_with("SELECT * FROM drivers LIMIT %s", (1,))

    @patch("psycopg2.connect")
    def test_get_warehouse_row_counts_handles_missing_tables(self, mock_psycopg) -> None:
        # Arrange
        mock_conn = MagicMock()
        mock_psycopg.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Simulate exception on some queries (e.g. UndefinedTable)
        class MockUndefinedTable(Exception):
            pass

        mock_cursor.execute.side_effect = [
            None,  # First query succeeds
            MockUndefinedTable("Relation does not exist"),  # Second query fails
            None,
        ]

        # Act
        with patch.object(self.repo, "_parse_entities_config") as mock_parse:
            mock_parse.return_value = {
                "staging": ["staging.stg_hr_drivers", "staging.stg_fleet_vehicles"],
                "nds": ["nds.nds_driver"],
                "dds": []
            }
            counts = self.repo.get_warehouse_row_counts()

        # Assert
        # Check that we handled the failure gracefully and returned -1 for the failed table
        self.assertIn("staging.stg_hr_drivers", counts["staging"])
        self.assertIn("staging.stg_fleet_vehicles", counts["staging"])
        self.assertEqual(counts["staging"]["staging_table" if "staging_table" in counts["staging"] else "staging.stg_fleet_vehicles"], -1)
        mock_conn.rollback.assert_called()

    def test_sanitize_message_secrets(self) -> None:
        from src.monitoring.repository import sanitize_message

        # Test password format
        self.assertNotIn("secret123", sanitize_message("password=secret123"))
        self.assertIn("password=***", sanitize_message("password=secret123"))

        # Test token format
        self.assertNotIn("token456", sanitize_message("token=token456"))
        self.assertIn("token=***", sanitize_message("token=token456"))

        # Test URI credentials
        uri = "postgres://user:super-pass@host/db"
        sanitized = sanitize_message(uri)
        self.assertNotIn("super-pass", sanitized)
        self.assertIn("postgres://user:***@host/db", sanitized)

    def test_sanitize_for_display_redacts_nested_secret_fields(self) -> None:
        payload = {
            "username": "demo",
            "password": "plain-text",
            "nested": {"api_key": "abc123", "message": "token=def456"},
        }

        sanitized = sanitize_for_display(payload)

        self.assertEqual(sanitized["password"], "***")
        self.assertEqual(sanitized["nested"]["api_key"], "***")
        self.assertNotIn("def456", sanitized["nested"]["message"])

    def test_is_dds_ready_scenarios(self) -> None:
        from src.monitoring.repository import is_dds_ready

        # Helper to create mock runs
        class MockRun:
            def __init__(self, status, steps):
                self.status = status
                self.steps = steps

        class MockStep:
            def __init__(self, step_name, status):
                self.step_name = step_name
                self.status = status

        # Scenario 1: Successful real run with successful mark_dds_ready -> True
        run1 = MockRun("SUCCEEDED", [MockStep("load_dds", "SUCCEEDED"), MockStep("mark_dds_ready", "SUCCEEDED")])
        self.assertTrue(is_dds_ready(run1, dry_run=False))

        # Scenario 2: Dry-run -> False
        self.assertFalse(is_dds_ready(run1, dry_run=True))

        # Scenario 3: Failed run -> False
        run2 = MockRun("FAILED", [MockStep("load_dds", "SUCCEEDED"), MockStep("mark_dds_ready", "SUCCEEDED")])
        self.assertFalse(is_dds_ready(run2, dry_run=False))

        # Scenario 4: Successful run but missing mark_dds_ready -> False
        run3 = MockRun("SUCCEEDED", [MockStep("load_dds", "SUCCEEDED")])
        self.assertFalse(is_dds_ready(run3, dry_run=False))

        # Scenario 5: mark_dds_ready is SKIPPED/DRY_RUN/FAILED -> False
        run4 = MockRun("SUCCEEDED", [MockStep("mark_dds_ready", "FAILED")])
        self.assertFalse(is_dds_ready(run4, dry_run=False))


if __name__ == "__main__":
    unittest.main()
