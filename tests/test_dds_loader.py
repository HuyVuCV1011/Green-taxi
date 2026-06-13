# -*- coding: utf-8 -*-
"""Unit tests for DDS Loader functionality."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, date, timedelta
from decimal import Decimal
from uuid import uuid4

from src.warehouse.dds_loader import (
    DDSLoader,
    deterministic_row_hash,
    PAYMENT_TYPE_MAP,
    RATECODE_MAP,
    TRIP_TYPE_MAP,
)


def _make_cursor_mock() -> tuple[MagicMock, MagicMock]:
    """Create a mock connection with a proper context-manager cursor."""
    mock_conn = MagicMock()
    cur_mock = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = cur_mock
    mock_conn.cursor.return_value.__exit__.return_value = False
    return mock_conn, cur_mock


class TestDeterministicRowHash(unittest.TestCase):

    def test_same_values_same_hash(self) -> None:
        h1 = deterministic_row_hash("A", "B", "C")
        h2 = deterministic_row_hash("A", "B", "C")
        self.assertEqual(h1, h2)

    def test_different_values_different_hash(self) -> None:
        h1 = deterministic_row_hash("A", "B")
        h2 = deterministic_row_hash("A", "C")
        self.assertNotEqual(h1, h2)

    def test_none_produces_hash(self) -> None:
        h = deterministic_row_hash(None, "A")
        self.assertEqual(len(h), 64)

    def test_empty_input(self) -> None:
        h = deterministic_row_hash()
        self.assertEqual(len(h), 64)

    def test_scd2_driver_hash(self) -> None:
        h1 = deterministic_row_hash("Manhattan", "ACTIVE")
        h2 = deterministic_row_hash("Brooklyn", "ACTIVE")
        self.assertNotEqual(h1, h2)

    def test_scd2_vehicle_hash(self) -> None:
        h1 = deterministic_row_hash("ACTIVE")
        h2 = deterministic_row_hash("MAINTENANCE")
        self.assertNotEqual(h1, h2)


class TestDDSLoaderInit(unittest.TestCase):

    def test_init_defaults(self) -> None:
        loader = DDSLoader("test-release")
        self.assertEqual(loader.release_id, "test-release")
        self.assertIsNotNone(loader.batch_id)

    def test_init_custom_batch_id(self) -> None:
        bid = uuid4()
        loader = DDSLoader("test-release", bid)
        self.assertEqual(loader.batch_id, bid)


class TestSCD2DriverHashNoChange(unittest.TestCase):
    """Hash unchanged -> no-op, no new SCD2 version."""

    @patch.object(DDSLoader, "connect_warehouse")
    def test_no_new_version_when_hash_unchanged(self, mock_connect: MagicMock) -> None:
        mock_conn, cur_mock = _make_cursor_mock()
        mock_connect.return_value = mock_conn

        existing_hash = deterministic_row_hash("Manhattan", "ACTIVE")

        nds_rows = [
            ("DRV000001", "D001", "John", "Manhattan", "ACTIVE",
             "ACTIVE", date(2025, 12, 31), 5, datetime(2024, 1, 1)),
        ]

        cur_mock.fetchall.return_value = nds_rows
        cur_mock.fetchone.return_value = (99, existing_hash)

        loader = DDSLoader("test-release", uuid4())
        loaded, new_v, noop = loader.load_dim_driver()

        self.assertEqual(loaded, 1)
        self.assertEqual(new_v, 0)
        self.assertEqual(noop, 1)


class TestSCD2DriverHashChanged(unittest.TestCase):
    """Hash changed -> exactly one new version, close old row."""

    @patch.object(DDSLoader, "connect_warehouse")
    def test_new_version_when_hash_changed(self, mock_connect: MagicMock) -> None:
        mock_conn, cur_mock = _make_cursor_mock()
        mock_connect.return_value = mock_conn

        old_hash = deterministic_row_hash("Manhattan", "ACTIVE")

        nds_rows = [
            ("DRV000001", "D001", "John", "Brooklyn", "ACTIVE",
             "ACTIVE", date(2025, 12, 31), 5, datetime(2024, 1, 1)),
        ]

        cur_mock.fetchall.return_value = nds_rows

        fetchone_calls = [0]
        def side_effect():
            fetchone_calls[0] += 1
            if fetchone_calls[0] == 1:
                return (99, old_hash)
            elif fetchone_calls[0] == 2:
                return (100,)
            return None
        cur_mock.fetchone.side_effect = side_effect

        loader = DDSLoader("test-release", uuid4())
        loaded, new_v, noop = loader.load_dim_driver()

        self.assertEqual(loaded, 1)
        self.assertEqual(new_v, 1)
        self.assertEqual(noop, 0)

        sql_calls = [str(c) for c in cur_mock.execute.call_args_list]
        update_calls = [c for c in sql_calls if "UPDATE dds.dim_driver" in c]
        self.assertTrue(len(update_calls) > 0, "Expected UPDATE to close old version")


class TestSCD2VehicleHashChanged(unittest.TestCase):
    """Vehicle hash changed -> exactly one new version."""

    @patch.object(DDSLoader, "connect_warehouse")
    def test_new_vehicle_version(self, mock_connect: MagicMock) -> None:
        mock_conn, cur_mock = _make_cursor_mock()
        mock_connect.return_value = mock_conn

        old_hash = deterministic_row_hash("ACTIVE")

        nds_rows = [
            ("VEH000001", "ABC123", 2023, "SEDAN", "MAINTENANCE",
             date(2025, 6, 1), datetime(2024, 1, 1)),
        ]

        cur_mock.fetchall.return_value = nds_rows

        fetchone_calls = [0]
        def side_effect():
            fetchone_calls[0] += 1
            if fetchone_calls[0] == 1:
                return (50, old_hash)
            elif fetchone_calls[0] == 2:
                return (51,)
            return None
        cur_mock.fetchone.side_effect = side_effect

        loader = DDSLoader("test-release", uuid4())
        loaded, new_v, noop = loader.load_dim_vehicle()

        self.assertEqual(loaded, 1)
        self.assertEqual(new_v, 1)
        self.assertEqual(noop, 0)


class TestEffectiveTimeLookup(unittest.TestCase):
    """SCD2 lookup returns correct version by business timestamp."""

    @patch.object(DDSLoader, "connect_warehouse")
    def test_lookup_returns_current_version(self, mock_connect: MagicMock) -> None:
        mock_conn, cur_mock = _make_cursor_mock()
        mock_connect.return_value = mock_conn

        cur_mock.fetchone.return_value = (42,)

        loader = DDSLoader("test-release", uuid4())
        event_time = datetime(2025, 6, 15, 10, 0, 0)
        key = loader._lookup_driver_key(mock_conn, "DRV000001", event_time)

        self.assertEqual(key, 42)
        sql = cur_mock.execute.call_args[0][0]
        self.assertIn("start_date", sql)
        self.assertIn("end_date", sql)

    @patch.object(DDSLoader, "connect_warehouse")
    def test_lookup_vehicle_returns_key(self, mock_connect: MagicMock) -> None:
        mock_conn, cur_mock = _make_cursor_mock()
        mock_connect.return_value = mock_conn

        cur_mock.fetchone.return_value = (77,)

        loader = DDSLoader("test-release", uuid4())
        event_time = datetime(2025, 6, 15, 10, 0, 0)
        key = loader._lookup_vehicle_key(mock_conn, "VEH000001", event_time)

        self.assertEqual(key, 77)


class TestFactCalculations(unittest.TestCase):
    """Check duration, delay, utilization, idle calculations."""

    def test_trip_duration_minutes(self) -> None:
        pickup = datetime(2025, 6, 15, 10, 0, 0)
        dropoff = datetime(2025, 6, 15, 10, 30, 0)
        delta = dropoff - pickup
        duration = Decimal(str(delta.total_seconds() / 60)).quantize(Decimal("0.01"))
        self.assertEqual(duration, Decimal("30.00"))

    def test_assignment_delay_positive(self) -> None:
        assignment_ts = datetime(2025, 6, 15, 9, 45, 0)
        pickup_dt = datetime(2025, 6, 15, 10, 0, 0)
        delay = pickup_dt - assignment_ts
        delay_min = Decimal(str(delay.total_seconds() / 60)).quantize(Decimal("0.01"))
        self.assertEqual(delay_min, Decimal("15.00"))

    def test_assignment_delay_negative_set_null(self) -> None:
        assignment_ts = datetime(2025, 6, 15, 10, 15, 0)
        pickup_dt = datetime(2025, 6, 15, 10, 0, 0)
        delay = pickup_dt - assignment_ts
        delay_min = Decimal(str(delay.total_seconds() / 60)).quantize(Decimal("0.01"))
        self.assertTrue(delay_min < 0)

    def test_division_by_zero_utilization(self) -> None:
        occupied = Decimal("0.00")
        duration = Decimal("0.00")
        utilization = Decimal("0.0000")
        if duration > 0:
            utilization = (occupied / duration).quantize(Decimal("0.0001"))
        self.assertEqual(utilization, Decimal("0.0000"))

    def test_idle_minutes_not_negative(self) -> None:
        duration = Decimal("30.00")
        occupied = Decimal("35.00")
        idle = duration - occupied
        if idle < 0:
            idle = Decimal("0.00")
        self.assertEqual(idle, Decimal("0.00"))

    def test_utilization_calculation(self) -> None:
        occupied = Decimal("20.00")
        duration = Decimal("60.00")
        utilization = (occupied / duration).quantize(Decimal("0.0001"))
        self.assertEqual(utilization, Decimal("0.3333"))


class TestRerunNoDuplicate(unittest.TestCase):
    """Rerun same event/hash does not create duplicate."""

    @patch.object(DDSLoader, "connect_warehouse")
    def test_driver_rerun_same_hash_no_new_version(self, mock_connect: MagicMock) -> None:
        mock_conn, cur_mock = _make_cursor_mock()
        mock_connect.return_value = mock_conn

        scd_hash = deterministic_row_hash("Manhattan", "ACTIVE")

        nds_rows = [
            ("DRV000001", "D001", "John", "Manhattan", "ACTIVE",
             "ACTIVE", date(2025, 12, 31), 5, datetime(2024, 1, 1)),
        ]

        cur_mock.fetchall.return_value = nds_rows
        cur_mock.fetchone.return_value = (99, scd_hash)

        loader = DDSLoader("test-release", uuid4())
        loaded, new_v, noop = loader.load_dim_driver()

        self.assertEqual(new_v, 0)
        self.assertEqual(noop, 1)

    @patch.object(DDSLoader, "connect_warehouse")
    def test_vehicle_rerun_same_hash_no_new_version(self, mock_connect: MagicMock) -> None:
        mock_conn, cur_mock = _make_cursor_mock()
        mock_connect.return_value = mock_conn

        scd_hash = deterministic_row_hash("ACTIVE")

        nds_rows = [
            ("VEH000001", "ABC123", 2023, "SEDAN", "ACTIVE",
             date(2025, 6, 1), datetime(2024, 1, 1)),
        ]

        cur_mock.fetchall.return_value = nds_rows
        cur_mock.fetchone.return_value = (50, scd_hash)

        loader = DDSLoader("test-release", uuid4())
        loaded, new_v, noop = loader.load_dim_vehicle()

        self.assertEqual(new_v, 0)
        self.assertEqual(noop, 1)


class TestNoDimShiftQuery(unittest.TestCase):
    """No query to dim_shift in DDS loader source."""

    def test_no_dim_shift_in_source(self) -> None:
        import inspect
        from src.warehouse import dds_loader as mod

        source = inspect.getsource(mod)
        self.assertNotIn("dim_shift", source)


class TestJunkDimensionMaps(unittest.TestCase):

    def test_payment_type_map_keys(self) -> None:
        self.assertIn(1, PAYMENT_TYPE_MAP)
        self.assertIn(2, PAYMENT_TYPE_MAP)
        self.assertIn(5, PAYMENT_TYPE_MAP)

    def test_payment_type_map_values(self) -> None:
        self.assertEqual(PAYMENT_TYPE_MAP[1], "Credit Card")
        self.assertEqual(PAYMENT_TYPE_MAP[2], "Cash")

    def test_ratecode_map_keys(self) -> None:
        self.assertIn(1, RATECODE_MAP)
        self.assertIn(2, RATECODE_MAP)

    def test_ratecode_map_values(self) -> None:
        self.assertEqual(RATECODE_MAP[1], "Standard Rate")
        self.assertEqual(RATECODE_MAP[2], "JFK")

    def test_trip_type_map(self) -> None:
        self.assertEqual(TRIP_TYPE_MAP[1], "Street-Hail")
        self.assertEqual(TRIP_TYPE_MAP[2], "Dispatch")


class TestDQGate2OverlapDetection(unittest.TestCase):
    """DQ Gate 2 overlap detection logs warnings correctly."""

    @patch.object(DDSLoader, "log_dq_issue")
    def test_driver_overlap_logged(self, mock_log: MagicMock) -> None:
        mock_conn, cur_mock = _make_cursor_mock()

        overlap_rows = [
            ("SHF001", "SHF002", 1, datetime(2025, 6, 15, 8, 0), datetime(2025, 6, 15, 16, 0)),
        ]
        driver_rows = [("DRV000001",)]

        cur_mock.fetchall.side_effect = [overlap_rows, driver_rows]

        loader = DDSLoader("test-release", uuid4())
        count = loader._dq_check_driver_shift_overlap(mock_conn)

        self.assertEqual(count, 1)
        mock_log.assert_called_once()
        log_kwargs = mock_log.call_args[1]
        self.assertEqual(log_kwargs["rule_code"], "ANOM_DRV_OVERLAP")
        self.assertEqual(log_kwargs["severity"], "WARN")

    @patch.object(DDSLoader, "log_dq_issue")
    def test_vehicle_overlap_logged(self, mock_log: MagicMock) -> None:
        mock_conn, cur_mock = _make_cursor_mock()

        overlap_rows = [
            ("SHF001", "SHF002", 1, datetime(2025, 6, 15, 8, 0), datetime(2025, 6, 15, 16, 0)),
        ]
        vehicle_rows = [("VEH000001",)]

        cur_mock.fetchall.side_effect = [overlap_rows, vehicle_rows]

        loader = DDSLoader("test-release", uuid4())
        count = loader._dq_check_vehicle_shift_overlap(mock_conn)

        self.assertEqual(count, 1)
        mock_log.assert_called_once()
        log_kwargs = mock_log.call_args[1]
        self.assertEqual(log_kwargs["rule_code"], "ANOM_VEH_OVERLAP")

    @patch.object(DDSLoader, "log_dq_issue")
    def test_trip_outside_shift_logged(self, mock_log: MagicMock) -> None:
        mock_conn, cur_mock = _make_cursor_mock()

        violations = [
            ("TRIP001", "SHF001", datetime(2025, 6, 15, 7, 0), datetime(2025, 6, 15, 12, 0),
             datetime(2025, 6, 15, 8, 0), datetime(2025, 6, 15, 16, 0)),
        ]
        cur_mock.fetchall.return_value = violations

        loader = DDSLoader("test-release", uuid4())
        count = loader._dq_check_trip_outside_shift(mock_conn)

        self.assertEqual(count, 1)
        mock_log.assert_called_once()
        log_kwargs = mock_log.call_args[1]
        self.assertEqual(log_kwargs["rule_code"], "ANOM_TRIP_OUT_SHF")

    @patch.object(DDSLoader, "log_dq_issue")
    def test_negative_assignment_delay_logged(self, mock_log: MagicMock) -> None:
        mock_conn, cur_mock = _make_cursor_mock()

        violations = [
            ("TRIP001", datetime(2025, 6, 15, 10, 15), datetime(2025, 6, 15, 10, 0)),
        ]
        cur_mock.fetchall.return_value = violations

        loader = DDSLoader("test-release", uuid4())
        count = loader._dq_check_negative_assignment_delay(mock_conn)

        self.assertEqual(count, 1)
        mock_log.assert_called_once()
        log_kwargs = mock_log.call_args[1]
        self.assertEqual(log_kwargs["rule_code"], "ANOM_DEL_NEGATIVE")


class TestBatchLogMethods(unittest.TestCase):

    @patch.object(DDSLoader, "connect_audit")
    def test_start_batch_log(self, mock_connect: MagicMock) -> None:
        mock_conn, cur_mock = _make_cursor_mock()
        mock_connect.return_value = mock_conn

        loader = DDSLoader("test-release", uuid4())
        loader.start_batch_log(input_params={"release_id": "test-release"})

        self.assertTrue(mock_conn.commit.called)

    @patch.object(DDSLoader, "connect_audit")
    def test_complete_batch_log(self, mock_connect: MagicMock) -> None:
        mock_conn, cur_mock = _make_cursor_mock()
        mock_connect.return_value = mock_conn

        loader = DDSLoader("test-release", uuid4())
        loader.complete_batch_log("SUCCEEDED", loaded_rows=100)

        self.assertTrue(mock_conn.commit.called)


class TestDateKeyAndTimeKey(unittest.TestCase):

    def test_date_key_format(self) -> None:
        loader = DDSLoader("test-release", uuid4())
        dt = datetime(2025, 6, 15, 10, 30)
        dk = loader._get_date_key(None, dt)
        self.assertEqual(dk, 20250615)

    def test_date_key_from_date(self) -> None:
        loader = DDSLoader("test-release", uuid4())
        d = date(2025, 12, 31)
        dk = loader._get_date_key(None, d)
        self.assertEqual(dk, 20251231)

    def test_time_key_format(self) -> None:
        loader = DDSLoader("test-release", uuid4())
        dt = datetime(2025, 6, 15, 14, 30)
        tk = loader._get_time_key(dt)
        self.assertEqual(tk, 1430)

    def test_time_key_midnight(self) -> None:
        loader = DDSLoader("test-release", uuid4())
        dt = datetime(2025, 1, 1, 0, 0)
        tk = loader._get_time_key(dt)
        self.assertEqual(tk, 0)

    def test_time_key_2359(self) -> None:
        loader = DDSLoader("test-release", uuid4())
        dt = datetime(2025, 1, 1, 23, 59)
        tk = loader._get_time_key(dt)
        self.assertEqual(tk, 2359)


class TestCloseAll(unittest.TestCase):

    def test_close_all(self) -> None:
        loader = DDSLoader("test-release", uuid4())
        loader.pg_conn = MagicMock()
        loader.audit_conn = MagicMock()

        loader.close_all()

        self.assertIsNone(loader.pg_conn)
        self.assertIsNone(loader.audit_conn)


if __name__ == "__main__":
    unittest.main()
