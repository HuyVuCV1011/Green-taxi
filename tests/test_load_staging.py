# -*- coding: utf-8 -*-
"""Unit tests for staging loader functionality."""

from __future__ import annotations

import hashlib
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

from src.ingestion.staging_loader import (
    calculate_file_checksum,
    make_row_hash,
    to_int,
    to_decimal,
    to_str,
    to_datetime_str,
    convert_mongo_date_to_date,
    convert_mongo_date_to_timestamp_ny
)


class TestStagingLoaderUtils(unittest.TestCase):

    def test_to_int(self) -> None:
        self.assertEqual(to_int("123"), 123)
        self.assertEqual(to_int("123.45"), 123)
        self.assertEqual(to_int(""), None)
        self.assertEqual(to_int("   "), None)
        self.assertEqual(to_int(None), None)
        self.assertEqual(to_int(5), 5)

    def test_to_decimal(self) -> None:
        self.assertEqual(to_decimal("12.34"), Decimal("12.34"))
        self.assertEqual(to_decimal(""), None)
        self.assertEqual(to_decimal("   "), None)
        self.assertEqual(to_decimal(None), None)

    def test_to_str(self) -> None:
        self.assertEqual(to_str("abc"), "abc")
        self.assertEqual(to_str("  abc  "), "abc")
        self.assertEqual(to_str(""), None)
        self.assertEqual(to_str(None), None)

    def test_to_datetime_str(self) -> None:
        self.assertEqual(to_datetime_str("2020-01-01T05:00:00"), "2020-01-01 05:00:00")
        self.assertEqual(to_datetime_str("2020-01-01"), "2020-01-01 00:00:00")
        self.assertEqual(to_datetime_str(""), None)
        self.assertEqual(to_datetime_str(None), None)

    def test_make_row_hash_deterministic(self) -> None:
        payload_1 = {
            "driver_id": "DRV_001",
            "vendor_id": 1,
            "hire_date": date(2020, 1, 15),
            "experience_years": 5,
            "source_updated_at": datetime(2020, 1, 15, 10, 30, 0),
            "occupied_minutes": Decimal("12.50")
        }
        
        payload_2 = {
            "driver_id": "DRV_001",
            "vendor_id": 1,
            "hire_date": date(2020, 1, 15),
            "experience_years": 5,
            "source_updated_at": datetime(2020, 1, 15, 10, 30, 0),
            "occupied_minutes": Decimal("12.5") # Test decimal normalization
        }

        hash_1 = make_row_hash(payload_1)
        hash_2 = make_row_hash(payload_2)
        
        self.assertEqual(hash_1, hash_2)
        self.assertEqual(len(hash_1), 64) # SHA-256 hash length is 64 hex characters

    def test_calculate_file_checksum(self) -> None:
        with NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            try:
                tmp.write(b"Hello green taxi!")
                tmp.flush()
                tmp.close()
                
                checksum = calculate_file_checksum(tmp_path)
                expected = hashlib.sha256(b"Hello green taxi!").hexdigest()
                self.assertEqual(checksum, expected)
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()

    def test_mongo_date_conversion(self) -> None:
        # 2020-01-15 05:00:00 UTC (naive or aware)
        dt_utc = datetime(2020, 1, 15, 5, 0, 0, tzinfo=timezone.utc)
        
        date_str = convert_mongo_date_to_date(dt_utc)
        # 2020-01-15 05:00:00 UTC is 2020-01-15 00:00:00 EST
        self.assertEqual(date_str, "2020-01-15")
        
        ts_ny = convert_mongo_date_to_timestamp_ny(dt_utc)
        self.assertEqual(ts_ny, datetime(2020, 1, 15, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
