# -*- coding: utf-8 -*-
"""Unit tests for NDS Loader functionality."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, date
from uuid import UUID, uuid4

from src.warehouse.nds_loader import NDSLoader


class TestNDSLoaderDQAndLogic(unittest.TestCase):

    def setUp(self) -> None:
        self.release_id = "green-taxi-full-v1"
        self.batch_id = uuid4()
        self.loader = NDSLoader(self.release_id, self.batch_id)
        self.loader.prepopulate_caches = MagicMock()

    @patch("src.warehouse.nds_loader.NDSLoader.connect_warehouse")
    def test_init_nds_schema(self, mock_connect: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        self.loader.init_nds_schema()
        
        # Verify schema/table creation SQLs were executed
        self.assertTrue(mock_cur.execute.called)
        self.assertTrue(mock_conn.commit.called)

    @patch("src.warehouse.nds_loader.NDSLoader.connect_warehouse")
    def test_get_vendor_sk_cached(self, mock_connect: MagicMock) -> None:
        # If cached, should return immediately without query
        self.loader.vendor_cache[1] = 42
        
        sk = self.loader.get_vendor_sk(None, 1)
        self.assertEqual(sk, 42)
        mock_connect.assert_not_called()

    @patch("src.warehouse.nds_loader.NDSLoader.connect_warehouse")
    def test_get_vendor_sk_uncached_found(self, mock_connect: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchone.return_value = (10,)

        sk = self.loader.get_vendor_sk(mock_conn, 2)
        self.assertEqual(sk, 10)
        self.assertEqual(self.loader.vendor_cache[2], 10)
        mock_cur.execute.assert_called_once_with(
            "SELECT vendor_sk FROM nds.nds_vendor WHERE vendor_nk = %s", (2,)
        )

    @patch("src.warehouse.nds_loader.NDSLoader.connect_warehouse")
    def test_get_vendor_sk_uncached_not_found_fallback(self, mock_connect: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        
        # First call for vendor 2 returns None, second call for vendor 0 returns 1
        mock_cur.fetchone.side_effect = [None, (1,)]

        sk = self.loader.get_vendor_sk(mock_conn, 2)
        self.assertEqual(sk, 1)
        self.assertEqual(self.loader.vendor_cache[0], 1)

    @patch("src.warehouse.nds_loader.NDSLoader.connect_warehouse")
    def test_get_or_create_location_sk(self, mock_connect: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        
        # Scenario: location not cached and not in DB -> created
        mock_cur.fetchone.side_effect = [None, (99,)]

        sk = self.loader.get_or_create_location_sk(mock_conn, 50)
        self.assertEqual(sk, 99)
        self.assertEqual(self.loader.location_cache[50], 99)
        
        # Verify it inserted a skeleton location
        insert_query = mock_cur.execute.call_args_list[1][0][0]
        self.assertIn("INSERT INTO nds.nds_location", insert_query)
        self.assertIn("location_nk", insert_query)

    @patch("src.warehouse.nds_loader.NDSLoader.connect_warehouse")
    @patch("src.warehouse.nds_loader.NDSLoader.log_dq_issue")
    def test_get_or_create_driver_sk_inferred(self, mock_log: MagicMock, mock_connect: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        
        # Mock vendor lookup inside inferred driver creation
        self.loader.vendor_cache[0] = 5
        mock_cur.fetchone.side_effect = [None, (15,)]

        sk = self.loader.get_or_create_driver_sk(mock_conn, "DRV000999")
        self.assertEqual(sk, 15)
        self.assertEqual(self.loader.driver_cache["DRV000999"], 15)
        
        # Verify insert skeleton and DQ warning log
        self.assertTrue(mock_cur.execute.called)
        mock_log.assert_called_once()
        args, kwargs = mock_log.call_args
        rule_code = kwargs.get("rule_code") or args[4]
        severity = kwargs.get("severity") or args[5]
        self.assertEqual(rule_code, "DQ_MISSING_MASTER")
        self.assertEqual(severity, "WARN")

    @patch("src.warehouse.nds_loader.NDSLoader.connect_warehouse")
    @patch("src.warehouse.nds_loader.NDSLoader.write_quarantine")
    @patch("src.warehouse.nds_loader.NDSLoader.log_dq_issue")
    def test_load_drivers_dq_violations(self, mock_log: MagicMock, mock_quarantine: MagicMock, mock_connect: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        # Test cases for drivers:
        # Row 1: Valid driver -> should be loaded
        # Row 2: Invalid Driver ID format (DRV12) -> should be quarantined (DQ_FORMAT_DRV)
        # Row 3: Null Driver ID -> should be quarantined (DQ_NULL_PK)
        # Row 4: Invalid Enum Status -> should be quarantined (DQ_INVALID_ENUM)
        mock_cur.fetchall.return_value = [
            # batch_id, release_id, src_sys, src_ent, src_loc, rec_id, ext_at, hash, drv_id, vend, code, name, hire, status, lic_status, expiry, exp, borough, updated
            (str(self.batch_id), self.release_id, "HR_MYSQL", "drivers", "", "DRV000001", None, "hash1",
             "DRV000001", 1, "C1", "Driver One", date(2020, 1, 1), "ACTIVE", "ACTIVE", date(2025, 1, 1), 5, "Manhattan", datetime.now()),
            (str(self.batch_id), self.release_id, "HR_MYSQL", "drivers", "", "DRV12", None, "hash2",
             "DRV12", 1, "C2", "Driver Two", date(2020, 1, 1), "ACTIVE", "ACTIVE", date(2025, 1, 1), 5, "Manhattan", datetime.now()),
            (str(self.batch_id), self.release_id, "HR_MYSQL", "drivers", "", "", None, "hash3",
             None, 1, "C3", "Driver Three", date(2020, 1, 1), "ACTIVE", "ACTIVE", date(2025, 1, 1), 5, "Manhattan", datetime.now()),
            (str(self.batch_id), self.release_id, "HR_MYSQL", "drivers", "", "DRV000004", None, "hash4",
             "DRV000004", 1, "C4", "Driver Four", date(2020, 1, 1), "UNKNOWN_STATUS", "ACTIVE", date(2025, 1, 1), 5, "Manhattan", datetime.now()),
        ]
        
        # Mock vendor SK lookup
        self.loader.vendor_cache[1] = 10
        # Mock executing insert
        mock_cur.fetchone.return_value = (100,)

        read_count, loaded, quarantined = self.loader.load_drivers()

        self.assertEqual(read_count, 4)
        self.assertEqual(loaded, 1)
        self.assertEqual(quarantined, 3)

        # Check quarantine calls
        self.assertEqual(mock_quarantine.call_count, 3)
        quarantine_rules = [call[0][2] for call in mock_quarantine.call_args_list]
        self.assertIn("DQ_NULL_PK", quarantine_rules)
        self.assertIn("DQ_FORMAT_DRV", quarantine_rules)
        self.assertIn("DQ_INVALID_ENUM", quarantine_rules)

        # Check log_dq_issue calls
        self.assertEqual(mock_log.call_count, 3)

    @patch("src.warehouse.nds_loader.NDSLoader.connect_warehouse")
    @patch("src.warehouse.nds_loader.NDSLoader.write_quarantine")
    @patch("src.warehouse.nds_loader.NDSLoader.log_dq_issue")
    @patch("src.warehouse.nds_loader.execute_values")
    def test_load_shifts_dq_violations(self, mock_execute_values: MagicMock, mock_log: MagicMock, mock_quarantine: MagicMock, mock_connect: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        # Test cases for shifts:
        # Row 1: Valid shift
        # Row 2: shift_end < shift_start -> DQ_DATE_ORDER (ERROR)
        mock_cur.fetchall.side_effect = [
            [
                # batch_id, release_id, src_sys, src_ent, src_loc, rec_id, ext_at, hash, shift_id, drv_id, veh_id, vend, start, end, start_z, end_z, count, occ, idle, status
                (str(self.batch_id), self.release_id, "DISPATCH_POSTGRES", "shifts", "", "SHF01", None, "hash1",
                 "SHF01", "DRV000001", "VEH000001", 1, datetime(2020, 1, 1, 8, 0), datetime(2020, 1, 1, 16, 0), 1, 2, 10, 300, 180, "COMPLETED"),
                (str(self.batch_id), self.release_id, "DISPATCH_POSTGRES", "shifts", "", "SHF02", None, "hash2",
                 "SHF02", "DRV000001", "VEH000001", 1, datetime(2020, 1, 1, 16, 0), datetime(2020, 1, 1, 8, 0), 1, 2, 10, 300, 180, "COMPLETED"),
            ],
            [] # Second fetchmany returns empty
        ]

        # Mock lookups
        self.loader.driver_cache["DRV000001"] = 100
        self.loader.vehicle_cache["VEH000001"] = 200
        self.loader.vendor_cache[1] = 10
        self.loader.location_cache[1] = 15
        self.loader.location_cache[2] = 16
        mock_cur.fetchone.return_value = (1000,)

        read_count, loaded, quarantined = self.loader.load_shifts()

        self.assertEqual(read_count, 2)
        self.assertEqual(loaded, 1)
        self.assertEqual(quarantined, 1)

        # Verify date order error quarantine
        mock_quarantine.assert_called_once()
        self.assertEqual(mock_quarantine.call_args[0][2], "DQ_DATE_ORDER")

    @patch("src.warehouse.nds_loader.NDSLoader.connect_warehouse")
    @patch("src.warehouse.nds_loader.NDSLoader.log_dq_issue")
    @patch("src.warehouse.nds_loader.execute_values")
    def test_load_trips_negative_warn(self, mock_execute_values: MagicMock, mock_log: MagicMock, mock_connect: MagicMock) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        # Test cases for trips:
        # Row 1: fare_amount = -5.0 -> DQ_NEGATIVE_VAL (WARN) but load to NDS
        mock_cur.fetchall.side_effect = [
            [
                # batch_id, release_id, src_sys, src_ent, src_loc, file, row, ext, load, check, wat, hash, vend, pick, drop, forward, rate, pu, do, pass, dist, fare, extra, tax, tip, tolls, fee, imp, total, pay, type, cong, rec_id
                (str(self.batch_id), self.release_id, "TLC_FILE", "tlc_green_tripdata", "TK01", "file.csv", 2, None, None, "check", None, "hash1",
                 1, datetime(2020, 1, 1, 10, 0), datetime(2020, 1, 1, 10, 15), "N", 1, 1, 2, 1, 2.5, -5.0, 0.0, 0.5, 0.0, 0.0, 0.0, 0.3, -4.2, 1, 1, 0.0, "TK01"),
            ],
            []
        ]

        self.loader.vendor_cache[1] = 10
        self.loader.location_cache[1] = 15
        self.loader.location_cache[2] = 16
        mock_cur.fetchone.return_value = (5000,)

        read_count, loaded, quarantined = self.loader.load_trips()

        self.assertEqual(read_count, 1)
        self.assertEqual(loaded, 1) # loaded because it's a WARN
        self.assertEqual(quarantined, 0)

        # Verify WARN issue logged
        mock_log.assert_called_once()
        args, kwargs = mock_log.call_args
        rule_code = kwargs.get("rule_code") or args[4]
        severity = kwargs.get("severity") or args[5]
        self.assertEqual(rule_code, "DQ_NEGATIVE_VAL")
        self.assertEqual(severity, "WARN")


if __name__ == "__main__":
    unittest.main()
