# -*- coding: utf-8 -*-
"""DDS Loader module.

Loads data from NDS schema tables into DDS schema (Star Schema) with:
- Static dimensions: dim_date, dim_time, dim_vendor, dim_location
- SCD Type 2 dimensions: dim_driver, dim_vehicle
- Junk dimension: dim_junk_trip
- Fact tables: fact_driver_trip, fact_driver_shift
- DQ Gate 2 business anomaly checks
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID, uuid4

import psycopg2
from psycopg2.extras import execute_values


PAYMENT_TYPE_MAP: dict[int, str] = {
    1: "Credit Card",
    2: "Cash",
    3: "No Charge",
    4: "Dispute",
    5: "Unknown",
}

RATECODE_MAP: dict[int, str] = {
    1: "Standard Rate",
    2: "JFK",
    3: "Newark",
    4: "Nassau/Westchester",
    5: "Negotiated Fare",
    6: "Group Ride",
}

TRIP_TYPE_MAP: dict[int, str] = {
    1: "Street-Hail",
    2: "Dispatch",
}


def deterministic_row_hash(*values: Any) -> str:
    """Compute deterministic SHA-256 hash from ordered values."""
    payload = "|".join("" if v is None else str(v) for v in values)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class DDSLoader:
    """Orchestrates NDS-to-DDS load processes with SCD2 and DQ Gate 2."""

    def __init__(self, release_id: str, batch_id: UUID | None = None) -> None:
        self.release_id = release_id
        self.batch_id = batch_id or uuid4()
        self.pg_conn = None
        self.audit_conn = None

        self.vendor_cache: dict[int, int] = {}
        self.location_cache: dict[int, int] = {}
        self.driver_key_cache: dict[tuple[str, datetime], int] = {}
        self.vehicle_key_cache: dict[tuple[str, datetime], int] = {}
        self.date_key_cache: dict[date, int] = {}
        self.time_key_cache: dict[int, int] = {}
        self.junk_trip_cache: dict[tuple, int] = {}

        self.stats: list[tuple[str, int, int, str]] = []

    def connect_warehouse(self) -> Any:
        if self.pg_conn is None or self.pg_conn.closed:
            self.pg_conn = psycopg2.connect(
                host=os.getenv("POSTGRES_WAREHOUSE_HOST", "127.0.0.1"),
                port=int(os.getenv("POSTGRES_WAREHOUSE_PORT", "5434")),
                database=os.getenv("POSTGRES_WAREHOUSE_DATABASE", "green_taxi_warehouse"),
                user=os.getenv("POSTGRES_WAREHOUSE_USER", "green_taxi_warehouse_app"),
                password=os.getenv("POSTGRES_WAREHOUSE_PASSWORD", "change_me_warehouse"),
            )
        return self.pg_conn

    def connect_audit(self) -> Any:
        if self.audit_conn is None or self.audit_conn.closed:
            self.audit_conn = psycopg2.connect(
                host=os.getenv("POSTGRES_WAREHOUSE_HOST", "127.0.0.1"),
                port=int(os.getenv("POSTGRES_WAREHOUSE_PORT", "5434")),
                database=os.getenv("POSTGRES_WAREHOUSE_DATABASE", "green_taxi_warehouse"),
                user=os.getenv("POSTGRES_WAREHOUSE_USER", "green_taxi_warehouse_app"),
                password=os.getenv("POSTGRES_WAREHOUSE_PASSWORD", "change_me_warehouse"),
            )
        return self.audit_conn

    def close_all(self) -> None:
        for conn_name in ("pg_conn", "audit_conn"):
            conn = getattr(self, conn_name, None)
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
                setattr(self, conn_name, None)

    def start_batch_log(self, input_params: dict | None = None) -> None:
        conn = self.connect_audit()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit.metadata_etl_batch (
                    batch_id, release_id, pipeline_name, batch_status,
                    batch_started_at, source_system, business_timezone,
                    audit_timezone, input_parameters
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(self.batch_id),
                    self.release_id,
                    "warehouse_dds",
                    "STARTED",
                    datetime.now(timezone.utc),
                    None,
                    os.getenv("BUSINESS_TIMEZONE", "America/New_York"),
                    "UTC",
                    json.dumps(input_params or {}),
                ),
            )
        conn.commit()

    def complete_batch_log(
        self,
        status: str,
        expected_rows: int = 0,
        loaded_rows: int = 0,
        error_msg: str | None = None,
    ) -> None:
        conn = self.connect_audit()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE audit.metadata_etl_batch
                SET batch_status = %s,
                    batch_completed_at = %s,
                    row_count_expected = %s,
                    row_count_loaded = %s,
                    error_message = %s,
                    updated_at = %s
                WHERE batch_id = %s
                """,
                (
                    status,
                    datetime.now(timezone.utc),
                    expected_rows,
                    loaded_rows,
                    error_msg,
                    datetime.now(timezone.utc),
                    str(self.batch_id),
                ),
            )
        conn.commit()

    def log_dq_issue(
        self,
        conn: Any,
        source_system: str,
        source_entity: str,
        source_record_id: str | None,
        rule_code: str,
        severity: str,
        message: str,
        payload: dict,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO dq.dq_issue (
                    batch_id, release_id, source_system_code, source_entity,
                    source_record_id, rule_code, severity, issue_message, issue_payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(self.batch_id),
                    self.release_id,
                    source_system,
                    source_entity,
                    source_record_id,
                    rule_code,
                    severity,
                    message,
                    json.dumps(payload, default=str),
                ),
            )

    def _get_vendor_key(self, conn: Any, vendor_nk: int) -> int:
        if vendor_nk in self.vendor_cache:
            return self.vendor_cache[vendor_nk]
        with conn.cursor() as cur:
            cur.execute(
                "SELECT vendor_key FROM dds.dim_vendor WHERE vendor_id = %s",
                (vendor_nk,),
            )
            row = cur.fetchone()
            if row:
                self.vendor_cache[vendor_nk] = row[0]
                return row[0]
        raise ValueError(f"dim_vendor not found for vendor_id={vendor_nk}")

    def _get_location_key(self, conn: Any, location_nk: int) -> int:
        if location_nk in self.location_cache:
            return self.location_cache[location_nk]
        with conn.cursor() as cur:
            cur.execute(
                "SELECT location_key FROM dds.dim_location WHERE location_id = %s",
                (location_nk,),
            )
            row = cur.fetchone()
            if row:
                self.location_cache[location_nk] = row[0]
                return row[0]
        raise ValueError(f"dim_location not found for location_id={location_nk}")

    def _get_date_key(self, conn: Any, dt: date | datetime) -> int:
        if isinstance(dt, datetime):
            dt = dt.date()
        if dt in self.date_key_cache:
            return self.date_key_cache[dt]
        dk = int(dt.strftime("%Y%m%d"))
        self.date_key_cache[dt] = dk
        return dk

    def _get_time_key(self, dt: datetime) -> int:
        tk = dt.hour * 100 + dt.minute
        return tk

    def _lookup_driver_key(
        self, conn: Any, driver_nk: str, event_time: datetime
    ) -> int:
        cache_key = (driver_nk, event_time)
        if cache_key in self.driver_key_cache:
            return self.driver_key_cache[cache_key]
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT driver_key FROM dds.dim_driver
                WHERE driver_id = %s
                  AND start_date <= %s
                  AND (end_date IS NULL OR %s < end_date)
                LIMIT 1
                """,
                (driver_nk, event_time, event_time),
            )
            row = cur.fetchone()
            if row:
                self.driver_key_cache[cache_key] = row[0]
                return row[0]
        raise ValueError(
            f"dim_driver lookup failed for driver_id={driver_nk} at {event_time}"
        )

    def _lookup_vehicle_key(
        self, conn: Any, vehicle_nk: str, event_time: datetime
    ) -> int:
        cache_key = (vehicle_nk, event_time)
        if cache_key in self.vehicle_key_cache:
            return self.vehicle_key_cache[cache_key]
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT vehicle_key FROM dds.dim_vehicle
                WHERE vehicle_id = %s
                  AND start_date <= %s
                  AND (end_date IS NULL OR %s < end_date)
                LIMIT 1
                """,
                (vehicle_nk, event_time, event_time),
            )
            row = cur.fetchone()
            if row:
                self.vehicle_key_cache[cache_key] = row[0]
                return row[0]
        raise ValueError(
            f"dim_vehicle lookup failed for vehicle_id={vehicle_nk} at {event_time}"
        )

    def _get_junk_trip_key(
        self,
        conn: Any,
        payment_type: int | None,
        ratecode_id: int | None,
        trip_type: int | None,
        assignment_method: str,
        is_anomaly: bool,
    ) -> int:
        payment_desc = PAYMENT_TYPE_MAP.get(payment_type or 0, "Unknown")
        ratecode_desc = RATECODE_MAP.get(ratecode_id or 0, "Unknown")
        trip_desc = TRIP_TYPE_MAP.get(trip_type or 0, "Unknown")
        method = assignment_method or "Unknown"

        cache_key = (payment_desc, ratecode_desc, trip_desc, method, is_anomaly)
        if cache_key in self.junk_trip_cache:
            return self.junk_trip_cache[cache_key]

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO dds.dim_junk_trip (
                    payment_type_desc, ratecode_desc, trip_type_desc,
                    assignment_method, is_anomaly
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (
                    payment_type_desc, ratecode_desc, trip_type_desc,
                    assignment_method, is_anomaly
                ) DO UPDATE SET payment_type_desc = EXCLUDED.payment_type_desc
                RETURNING junk_trip_key
                """,
                (payment_desc, ratecode_desc, trip_desc, method, is_anomaly),
            )
            key = cur.fetchone()[0]
            self.junk_trip_cache[cache_key] = key
            return key

    def _compute_scd2_hash_driver(
        self,
        home_borough: str,
        employment_status: str,
    ) -> str:
        return deterministic_row_hash(home_borough, employment_status)

    def _compute_scd2_hash_vehicle(self, vehicle_status: str) -> str:
        return deterministic_row_hash(vehicle_status)

    def load_dim_date(self) -> tuple[int, int]:
        conn = self.connect_warehouse()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT MIN(min_ts), MAX(max_ts)
                FROM (
                    SELECT MIN(pickup_datetime) AS min_ts,
                           MAX(dropoff_datetime) AS max_ts
                    FROM nds.nds_trip
                    UNION ALL
                    SELECT MIN(shift_start) AS min_ts,
                           MAX(shift_end) AS max_ts
                    FROM nds.nds_shift
                ) bounds
                """
            )
            row = cur.fetchone()
            if not row or not row[0]:
                return 0, 0
            min_date = row[0].date() if isinstance(row[0], datetime) else row[0]
            max_date = row[1].date() if isinstance(row[1], datetime) else row[1]

        rows_to_insert = []
        current = min_date
        while current <= max_date:
            dk = int(current.strftime("%Y%m%d"))
            dow = current.isoweekday()
            rows_to_insert.append((
                dk,
                current,
                current.day,
                current.month,
                current.strftime("%B"),
                (current.month - 1) // 3 + 1,
                current.year,
                dow,
                current.strftime("%A"),
                dow >= 6,
                False,
                current.isocalendar()[1],
            ))
            current += timedelta(days=1)

        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO dds.dim_date (
                    date_key, date, day, month, month_name, quarter, year,
                    day_of_week, day_name, is_weekend, is_holiday, week_of_year
                ) VALUES %s
                ON CONFLICT (date_key) DO NOTHING
                """,
                rows_to_insert,
                page_size=1000,
            )
        conn.commit()
        return len(rows_to_insert), 0

    def load_dim_time(self) -> tuple[int, int]:
        conn = self.connect_warehouse()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM dds.dim_time")
            existing = cur.fetchone()[0]
            if existing >= 1440:
                return existing, 0

        rows_to_insert = []
        for minute_of_day in range(1440):
            h = minute_of_day // 60
            m = minute_of_day % 60
            tk = h * 100 + m
            tod = datetime(2000, 1, 1, h, m).time()
            if 6 <= h < 10:
                bucket = "Morning"
            elif 10 <= h < 16:
                bucket = "Afternoon"
            elif 16 <= h < 21:
                bucket = "Evening"
            else:
                bucket = "Night"
            is_peak = h in (7, 8, 9, 17, 18, 19)
            rows_to_insert.append((tk, tod, h, m, bucket, is_peak))

        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO dds.dim_time (
                    time_key, time_of_day, hour, minute, time_bucket, is_peak_hour
                ) VALUES %s
                ON CONFLICT (time_key) DO NOTHING
                """,
                rows_to_insert,
                page_size=1440,
            )
        conn.commit()
        return len(rows_to_insert), 0

    def load_dim_vendor(self) -> tuple[int, int]:
        conn = self.connect_warehouse()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT vendor_nk, vendor_name
                FROM nds.nds_vendor
                """
            )
            nds_rows = cur.fetchall()

        rows_to_insert = []
        for vendor_nk, vendor_name in nds_rows:
            rows_to_insert.append((vendor_nk, vendor_name, str(self.batch_id)))
            self.vendor_cache[vendor_nk] = vendor_nk

        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO dds.dim_vendor (vendor_id, vendor_name, batch_id)
                VALUES %s
                ON CONFLICT (vendor_id) DO UPDATE
                SET vendor_name = EXCLUDED.vendor_name,
                    batch_id = EXCLUDED.batch_id
                """,
                rows_to_insert,
                page_size=100,
            )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT vendor_id, vendor_key FROM dds.dim_vendor")
            for vid, vk in cur.fetchall():
                self.vendor_cache[vid] = vk

        return len(rows_to_insert), 0

    def load_dim_location(self) -> tuple[int, int]:
        conn = self.connect_warehouse()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT location_nk, borough, zone, service_zone
                FROM nds.nds_location
                """
            )
            nds_rows = cur.fetchall()

        rows_to_insert = []
        for loc_nk, borough, zone, svc in nds_rows:
            rows_to_insert.append((loc_nk, borough, zone, svc))
            self.location_cache[loc_nk] = loc_nk

        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO dds.dim_location (location_id, borough, zone, service_zone)
                VALUES %s
                ON CONFLICT (location_id) DO UPDATE
                SET borough = EXCLUDED.borough,
                    zone = EXCLUDED.zone,
                    service_zone = EXCLUDED.service_zone
                """,
                rows_to_insert,
                page_size=300,
            )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT location_id, location_key FROM dds.dim_location")
            for lid, lk in cur.fetchall():
                self.location_cache[lid] = lk

        return len(rows_to_insert), 0

    def load_dim_driver(self) -> tuple[int, int, int]:
        conn = self.connect_warehouse()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.driver_nk, d.driver_code, d.display_name,
                       d.home_borough, d.employment_status, d.license_status,
                       d.license_expiry_date, d.experience_years,
                       LEAST(
                           d.hire_date::timestamp,
                           d.created_at::timestamp,
                           COALESCE(
                               (SELECT MIN(s.shift_start)
                                FROM nds.nds_shift s
                                WHERE s.driver_sk = d.driver_sk),
                               d.created_at::timestamp
                           )
                       )
                FROM nds.nds_driver d
                ORDER BY d.driver_nk
                """
            )
            nds_rows = cur.fetchall()

        new_versions = 0
        no_op = 0
        now_ts = datetime.now()

        for (
            driver_nk, driver_code, display_name, home_borough,
            employment_status, license_status, license_expiry_date,
            experience_years, created_at,
        ) in nds_rows:
            scd_hash = self._compute_scd2_hash_driver(home_borough, employment_status)

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT driver_key, source_row_hash
                    FROM dds.dim_driver
                    WHERE driver_id = %s AND is_current = true
                    """,
                    (driver_nk,),
                )
                current = cur.fetchone()

            if current is None:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO dds.dim_driver (
                            driver_id, driver_code, display_name, home_borough,
                            employment_status, license_status, license_expiry_date,
                            experience_years, start_date, end_date, is_current,
                            source_row_hash, batch_id
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,true,%s,%s)
                        RETURNING driver_key
                        """,
                        (
                            driver_nk, driver_code, display_name, home_borough,
                            employment_status, license_status, license_expiry_date,
                            experience_years, created_at or now_ts, scd_hash,
                            str(self.batch_id),
                        ),
                    )
                    self.driver_key_cache[(driver_nk, created_at or now_ts)] = cur.fetchone()[0]
                new_versions += 1
            else:
                existing_key, existing_hash = current
                if existing_hash != scd_hash:
                    close_ts = now_ts
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE dds.dim_driver
                            SET end_date = %s, is_current = false
                            WHERE driver_key = %s
                            """,
                            (close_ts, existing_key),
                        )
                        cur.execute(
                            """
                            INSERT INTO dds.dim_driver (
                                driver_id, driver_code, display_name, home_borough,
                                employment_status, license_status, license_expiry_date,
                                experience_years, start_date, end_date, is_current,
                                source_row_hash, batch_id
                            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,true,%s,%s)
                            RETURNING driver_key
                            """,
                            (
                                driver_nk, driver_code, display_name, home_borough,
                                employment_status, license_status, license_expiry_date,
                                experience_years, close_ts, scd_hash,
                                str(self.batch_id),
                            ),
                        )
                        self.driver_key_cache[(driver_nk, close_ts)] = cur.fetchone()[0]
                    new_versions += 1
                else:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE dds.dim_driver
                            SET driver_code = %s,
                                display_name = %s,
                                license_status = %s,
                                license_expiry_date = %s,
                                experience_years = %s,
                                start_date = LEAST(start_date, %s)
                            WHERE driver_key = %s
                            """,
                            (
                                driver_code, display_name, license_status,
                                license_expiry_date, experience_years,
                                created_at or now_ts, existing_key,
                            ),
                        )
                    no_op += 1

        conn.commit()
        return len(nds_rows), new_versions, no_op

    def load_dim_vehicle(self) -> tuple[int, int, int]:
        conn = self.connect_warehouse()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT v.vehicle_nk, v.plate_token, v.model_year,
                       v.vehicle_type, v.vehicle_status, v.last_inspection_date,
                       LEAST(
                           v.service_start_date::timestamp,
                           v.created_at::timestamp,
                           COALESCE(
                               (SELECT MIN(s.shift_start)
                                FROM nds.nds_shift s
                                WHERE s.vehicle_sk = v.vehicle_sk),
                               v.created_at::timestamp
                           )
                       )
                FROM nds.nds_vehicle v
                ORDER BY v.vehicle_nk
                """
            )
            nds_rows = cur.fetchall()

        new_versions = 0
        no_op = 0
        now_ts = datetime.now()

        for (
            vehicle_nk, plate_token, model_year, vehicle_type,
            vehicle_status, last_inspection_date, created_at,
        ) in nds_rows:
            scd_hash = self._compute_scd2_hash_vehicle(vehicle_status)

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT vehicle_key, source_row_hash
                    FROM dds.dim_vehicle
                    WHERE vehicle_id = %s AND is_current = true
                    """,
                    (vehicle_nk,),
                )
                current = cur.fetchone()

            if current is None:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO dds.dim_vehicle (
                            vehicle_id, plate_token, model_year, vehicle_type,
                            vehicle_status, last_inspection_date, start_date,
                            end_date, is_current, source_row_hash, batch_id
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,NULL,true,%s,%s)
                        RETURNING vehicle_key
                        """,
                        (
                            vehicle_nk, plate_token, model_year, vehicle_type,
                            vehicle_status, last_inspection_date,
                            created_at or now_ts, scd_hash, str(self.batch_id),
                        ),
                    )
                    self.vehicle_key_cache[(vehicle_nk, created_at or now_ts)] = cur.fetchone()[0]
                new_versions += 1
            else:
                existing_key, existing_hash = current
                if existing_hash != scd_hash:
                    close_ts = now_ts
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE dds.dim_vehicle
                            SET end_date = %s, is_current = false
                            WHERE vehicle_key = %s
                            """,
                            (close_ts, existing_key),
                        )
                        cur.execute(
                            """
                            INSERT INTO dds.dim_vehicle (
                                vehicle_id, plate_token, model_year, vehicle_type,
                                vehicle_status, last_inspection_date, start_date,
                                end_date, is_current, source_row_hash, batch_id
                            ) VALUES (%s,%s,%s,%s,%s,%s,%s,NULL,true,%s,%s)
                            RETURNING vehicle_key
                            """,
                            (
                                vehicle_nk, plate_token, model_year, vehicle_type,
                                vehicle_status, last_inspection_date,
                                close_ts, scd_hash, str(self.batch_id),
                            ),
                        )
                        self.vehicle_key_cache[(vehicle_nk, close_ts)] = cur.fetchone()[0]
                    new_versions += 1
                else:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE dds.dim_vehicle
                            SET plate_token = %s,
                                model_year = %s,
                                vehicle_type = %s,
                                last_inspection_date = %s,
                                start_date = LEAST(start_date, %s)
                            WHERE vehicle_key = %s
                            """,
                            (
                                plate_token, model_year, vehicle_type,
                                last_inspection_date, created_at or now_ts,
                                existing_key,
                            ),
                        )
                    no_op += 1

        conn.commit()
        return len(nds_rows), new_versions, no_op

    def _dq_check_driver_shift_overlap(self, conn: Any) -> int:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH overlapping AS (
                    SELECT a.shift_nk AS shift_a, b.shift_nk AS shift_b,
                           a.driver_sk, a.shift_start, a.shift_end
                    FROM nds.nds_shift a
                    JOIN nds.nds_shift b
                        ON a.driver_sk = b.driver_sk
                        AND a.shift_nk < b.shift_nk
                        AND a.shift_start < b.shift_end
                        AND b.shift_start < a.shift_end
                )
                SELECT shift_a, shift_b, driver_sk, shift_start, shift_end
                FROM overlapping
                """
            )
            overlaps = cur.fetchall()

        for shift_a, shift_b, driver_sk, shift_start, shift_end in overlaps:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT driver_nk FROM nds.nds_driver WHERE driver_sk = %s",
                    (driver_sk,),
                )
                row = cur.fetchone()
                driver_nk = row[0] if row else str(driver_sk)

            self.log_dq_issue(
                conn,
                source_system="DISPATCH_POSTGRES",
                source_entity="shifts",
                source_record_id=shift_a,
                rule_code="ANOM_DRV_OVERLAP",
                severity="WARN",
                message=f"Driver {driver_nk} has overlapping shifts: {shift_a} and {shift_b}",
                payload={
                    "driver_id": driver_nk,
                    "shift_a": shift_a,
                    "shift_b": shift_b,
                    "shift_a_start": str(shift_start),
                    "shift_a_end": str(shift_end),
                },
            )
        return len(overlaps)

    def _dq_check_vehicle_shift_overlap(self, conn: Any) -> int:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH overlapping AS (
                    SELECT a.shift_nk AS shift_a, b.shift_nk AS shift_b,
                           a.vehicle_sk, a.shift_start, a.shift_end
                    FROM nds.nds_shift a
                    JOIN nds.nds_shift b
                        ON a.vehicle_sk = b.vehicle_sk
                        AND a.shift_nk < b.shift_nk
                        AND a.shift_start < b.shift_end
                        AND b.shift_start < a.shift_end
                )
                SELECT shift_a, shift_b, vehicle_sk, shift_start, shift_end
                FROM overlapping
                """
            )
            overlaps = cur.fetchall()

        for shift_a, shift_b, vehicle_sk, shift_start, shift_end in overlaps:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT vehicle_nk FROM nds.nds_vehicle WHERE vehicle_sk = %s",
                    (vehicle_sk,),
                )
                row = cur.fetchone()
                vehicle_nk = row[0] if row else str(vehicle_sk)

            self.log_dq_issue(
                conn,
                source_system="DISPATCH_POSTGRES",
                source_entity="shifts",
                source_record_id=shift_a,
                rule_code="ANOM_VEH_OVERLAP",
                severity="WARN",
                message=f"Vehicle {vehicle_nk} has overlapping shifts: {shift_a} and {shift_b}",
                payload={
                    "vehicle_id": vehicle_nk,
                    "shift_a": shift_a,
                    "shift_b": shift_b,
                    "shift_a_start": str(shift_start),
                    "shift_a_end": str(shift_end),
                },
            )
        return len(overlaps)

    def _dq_check_trip_outside_shift(self, conn: Any) -> int:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.trip_nk, s.shift_nk, t.pickup_datetime, t.dropoff_datetime,
                       s.shift_start, s.shift_end
                FROM nds.nds_trip t
                JOIN nds.nds_trip_assignment ta ON t.trip_sk = ta.trip_sk
                JOIN nds.nds_shift s ON ta.shift_sk = s.shift_sk
                WHERE t.pickup_datetime < s.shift_start
                   OR t.dropoff_datetime > s.shift_end
                """
            )
            violations = cur.fetchall()

        for (
            trip_nk, shift_nk, pickup_dt, dropoff_dt, shift_start, shift_end
        ) in violations:
            self.log_dq_issue(
                conn,
                source_system="TLC_FILE",
                source_entity="trips",
                source_record_id=trip_nk,
                rule_code="ANOM_TRIP_OUT_SHF",
                severity="WARN",
                message=f"Trip {trip_nk} falls outside shift {shift_nk}",
                payload={
                    "trip_id": trip_nk,
                    "shift_id": shift_nk,
                    "pickup": str(pickup_dt),
                    "dropoff": str(dropoff_dt),
                    "shift_start": str(shift_start),
                    "shift_end": str(shift_end),
                },
            )
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE nds.nds_trip
                    SET is_anomaly = true
                    WHERE trip_nk = %s AND is_anomaly = false
                    """,
                    (trip_nk,),
                )

        return len(violations)

    def _dq_check_negative_assignment_delay(self, conn: Any) -> int:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.trip_nk, ta.assignment_timestamp, t.pickup_datetime
                FROM nds.nds_trip t
                JOIN nds.nds_trip_assignment ta ON t.trip_sk = ta.trip_sk
                WHERE ta.assignment_timestamp > t.pickup_datetime
                """
            )
            violations = cur.fetchall()

        for trip_nk, assignment_ts, pickup_dt in violations:
            self.log_dq_issue(
                conn,
                source_system="DISPATCH_POSTGRES",
                source_entity="trip_assignments",
                source_record_id=trip_nk,
                rule_code="ANOM_DEL_NEGATIVE",
                severity="WARN",
                message=f"Trip {trip_nk} has negative assignment delay",
                payload={
                    "trip_id": trip_nk,
                    "assignment_timestamp": str(assignment_ts),
                    "pickup_datetime": str(pickup_dt),
                },
            )
        return len(violations)

    def run_dq_gate2(self) -> dict[str, int]:
        conn = self.connect_warehouse()
        results = {}
        results["driver_shift_overlap"] = self._dq_check_driver_shift_overlap(conn)
        results["vehicle_shift_overlap"] = self._dq_check_vehicle_shift_overlap(conn)
        results["trip_outside_shift"] = self._dq_check_trip_outside_shift(conn)
        results["negative_assignment_delay"] = self._dq_check_negative_assignment_delay(conn)
        conn.commit()
        return results

    def load_fact_driver_trip(self) -> tuple[int, int]:
        conn = self.connect_warehouse()
        last_trip_nk: str | None = None
        batch_size = 5000
        loaded = 0

        while True:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT t.trip_nk, t.pickup_datetime, t.dropoff_datetime,
                           t.passenger_count, t.trip_distance,
                           t.fare_amount, t.extra, t.mta_tax, t.tip_amount,
                           t.tolls_amount, t.improvement_surcharge, t.total_amount,
                           dv.vendor_key,
                           dpl.location_key, ddl.location_key,
                           t.ratecode_id, t.payment_type, t.trip_type,
                           t.source_file, t.source_row_number, t.is_anomaly,
                           ta.assignment_timestamp, ta.assignment_method,
                           dd.driver_key, dveh.vehicle_key,
                           s.shift_nk
                    FROM nds.nds_trip t
                    JOIN nds.nds_trip_assignment ta ON t.trip_sk = ta.trip_sk
                    JOIN nds.nds_shift s ON ta.shift_sk = s.shift_sk
                    JOIN nds.nds_driver nd ON ta.driver_sk = nd.driver_sk
                    JOIN dds.dim_driver dd
                      ON dd.driver_id = nd.driver_nk
                     AND dd.start_date <= t.pickup_datetime
                     AND (dd.end_date IS NULL OR t.pickup_datetime < dd.end_date)
                    JOIN nds.nds_vehicle nv ON ta.vehicle_sk = nv.vehicle_sk
                    JOIN dds.dim_vehicle dveh
                      ON dveh.vehicle_id = nv.vehicle_nk
                     AND dveh.start_date <= t.pickup_datetime
                     AND (dveh.end_date IS NULL OR t.pickup_datetime < dveh.end_date)
                    JOIN nds.nds_vendor nvend ON t.vendor_sk = nvend.vendor_sk
                    JOIN dds.dim_vendor dv ON dv.vendor_id = nvend.vendor_nk
                    JOIN nds.nds_location npl ON t.pickup_location_sk = npl.location_sk
                    JOIN dds.dim_location dpl ON dpl.location_id = npl.location_nk
                    JOIN nds.nds_location ndl ON t.dropoff_location_sk = ndl.location_sk
                    JOIN dds.dim_location ddl ON ddl.location_id = ndl.location_nk
                    WHERE (%s IS NULL OR t.trip_nk > %s)
                    ORDER BY t.trip_nk
                    LIMIT %s
                    """,
                    (last_trip_nk, last_trip_nk, batch_size),
                )
                rows = cur.fetchall()

            if not rows:
                break

            last_trip_nk = rows[-1][0]
            trip_rows = []

            for r in rows:
                (
                    trip_nk, pickup_dt, dropoff_dt,
                    passenger_count, trip_distance,
                    fare_amount, extra, mta_tax, tip_amount,
                    tolls_amount, improvement_surcharge, total_amount,
                    vendor_key,
                    pickup_location_key, dropoff_location_key,
                    ratecode_id, payment_type, trip_type,
                    source_file, source_row_number, is_anomaly,
                    assignment_ts, assignment_method,
                    driver_key, vehicle_key,
                    shift_nk,
                ) = r

                pickup_date_key = self._get_date_key(conn, pickup_dt)
                pickup_time_key = self._get_time_key(pickup_dt)
                dropoff_date_key = self._get_date_key(conn, dropoff_dt)
                dropoff_time_key = self._get_time_key(dropoff_dt)

                junk_trip_key = self._get_junk_trip_key(
                    conn, payment_type, ratecode_id, trip_type,
                    assignment_method, is_anomaly,
                )

                duration = None
                if pickup_dt and dropoff_dt:
                    delta = dropoff_dt - pickup_dt
                    duration = Decimal(str(delta.total_seconds() / 60)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )

                delay = None
                if assignment_ts and pickup_dt:
                    delay_delta = pickup_dt - assignment_ts
                    delay_val = Decimal(str(delay_delta.total_seconds() / 60)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    if delay_val < 0:
                        delay = None
                    else:
                        delay = delay_val

                trip_rows.append((
                    trip_nk,
                    shift_nk or "",
                    pickup_date_key,
                    pickup_time_key,
                    dropoff_date_key,
                    dropoff_time_key,
                    driver_key,
                    vehicle_key,
                    vendor_key,
                    pickup_location_key,
                    dropoff_location_key,
                    junk_trip_key,
                    passenger_count,
                    trip_distance,
                    duration,
                    Decimal(str(fare_amount or 0)),
                    Decimal(str(extra or 0)),
                    Decimal(str(mta_tax or 0)),
                    Decimal(str(tip_amount or 0)),
                    Decimal(str(tolls_amount or 0)),
                    Decimal(str(improvement_surcharge or 0)),
                    Decimal(str(total_amount or 0)),
                    delay,
                    source_file or "",
                    source_row_number or 2,
                    str(self.batch_id),
                ))

            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """
                    INSERT INTO dds.fact_driver_trip (
                        trip_id, shift_id,
                        pickup_date_key, pickup_time_key,
                        dropoff_date_key, dropoff_time_key,
                        driver_key, vehicle_key, vendor_key,
                        pickup_location_key, dropoff_location_key,
                        junk_trip_key,
                        passenger_count, trip_distance, trip_duration_minutes,
                        fare_amount, extra, mta_tax, tip_amount,
                        tolls_amount, improvement_surcharge, total_amount,
                        assignment_delay_minutes,
                        source_file, source_row_number, batch_id
                    ) VALUES %s
                    ON CONFLICT (trip_id) DO UPDATE SET
                        shift_id = EXCLUDED.shift_id,
                        pickup_date_key = EXCLUDED.pickup_date_key,
                        pickup_time_key = EXCLUDED.pickup_time_key,
                        dropoff_date_key = EXCLUDED.dropoff_date_key,
                        dropoff_time_key = EXCLUDED.dropoff_time_key,
                        driver_key = EXCLUDED.driver_key,
                        vehicle_key = EXCLUDED.vehicle_key,
                        vendor_key = EXCLUDED.vendor_key,
                        pickup_location_key = EXCLUDED.pickup_location_key,
                        dropoff_location_key = EXCLUDED.dropoff_location_key,
                        junk_trip_key = EXCLUDED.junk_trip_key,
                        passenger_count = EXCLUDED.passenger_count,
                        trip_distance = EXCLUDED.trip_distance,
                        trip_duration_minutes = EXCLUDED.trip_duration_minutes,
                        fare_amount = EXCLUDED.fare_amount,
                        extra = EXCLUDED.extra,
                        mta_tax = EXCLUDED.mta_tax,
                        tip_amount = EXCLUDED.tip_amount,
                        tolls_amount = EXCLUDED.tolls_amount,
                        improvement_surcharge = EXCLUDED.improvement_surcharge,
                        total_amount = EXCLUDED.total_amount,
                        assignment_delay_minutes = EXCLUDED.assignment_delay_minutes,
                        source_file = EXCLUDED.source_file,
                        source_row_number = EXCLUDED.source_row_number,
                        batch_id = EXCLUDED.batch_id
                    """,
                    trip_rows,
                    page_size=1000,
                )
            conn.commit()
            loaded += len(trip_rows)

        return loaded, 0

    def _resolve_driver_nk(self, conn: Any, driver_sk: int) -> str:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT driver_nk FROM nds.nds_driver WHERE driver_sk = %s",
                (driver_sk,),
            )
            row = cur.fetchone()
            return row[0] if row else "UNKNOWN"

    def _resolve_vehicle_nk(self, conn: Any, vehicle_sk: int) -> str:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT vehicle_nk FROM nds.nds_vehicle WHERE vehicle_sk = %s",
                (vehicle_sk,),
            )
            row = cur.fetchone()
            return row[0] if row else "UNKNOWN"

    def _resolve_vendor_nk(self, conn: Any, vendor_sk: int) -> int:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT vendor_nk FROM nds.nds_vendor WHERE vendor_sk = %s",
                (vendor_sk,),
            )
            row = cur.fetchone()
            return row[0] if row else 0

    def _resolve_location_nk(self, conn: Any, location_sk: int) -> int:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT location_nk FROM nds.nds_location WHERE location_sk = %s",
                (location_sk,),
            )
            row = cur.fetchone()
            return row[0] if row else 264

    def load_fact_driver_shift(self) -> tuple[int, int]:
        conn = self.connect_warehouse()
        last_shift_nk: str | None = None
        batch_size = 5000
        loaded = 0

        while True:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT s.shift_nk, s.shift_start, s.shift_end,
                           s.shift_status, dd.driver_key, dveh.vehicle_key,
                           dv.vendor_key, COUNT(t.trip_sk),
                           COALESCE(SUM(
                               EXTRACT(EPOCH FROM (t.dropoff_datetime - t.pickup_datetime)) / 60
                           ), 0),
                           COALESCE(SUM(t.total_amount), 0),
                           COALESCE(SUM(t.tip_amount), 0),
                           COALESCE(BOOL_OR(
                               t.pickup_datetime < s.shift_start
                               OR t.dropoff_datetime > s.shift_end
                           ), false)
                    FROM nds.nds_shift s
                    JOIN nds.nds_driver d ON s.driver_sk = d.driver_sk
                    JOIN nds.nds_vehicle v ON s.vehicle_sk = v.vehicle_sk
                    JOIN nds.nds_vendor nv ON s.vendor_sk = nv.vendor_sk
                    JOIN dds.dim_driver dd
                      ON dd.driver_id = d.driver_nk
                     AND dd.start_date <= s.shift_start
                     AND (dd.end_date IS NULL OR s.shift_start < dd.end_date)
                    JOIN dds.dim_vehicle dveh
                      ON dveh.vehicle_id = v.vehicle_nk
                     AND dveh.start_date <= s.shift_start
                     AND (dveh.end_date IS NULL OR s.shift_start < dveh.end_date)
                    JOIN dds.dim_vendor dv ON dv.vendor_id = nv.vendor_nk
                    LEFT JOIN nds.nds_trip_assignment ta ON ta.shift_sk = s.shift_sk
                    LEFT JOIN nds.nds_trip t ON t.trip_sk = ta.trip_sk
                    WHERE (%s IS NULL OR s.shift_nk > %s)
                      AND s.shift_status = 'COMPLETED'
                    GROUP BY s.shift_nk, s.shift_start, s.shift_end,
                             s.shift_status, dd.driver_key,
                             dveh.vehicle_key, dv.vendor_key
                    ORDER BY s.shift_nk
                    LIMIT %s
                    """,
                    (last_shift_nk, last_shift_nk, batch_size),
                )
                rows = cur.fetchall()

            if not rows:
                break

            last_shift_nk = rows[-1][0]
            shift_rows = []

            for r in rows:
                (
                    shift_nk, shift_start, shift_end,
                    shift_status, driver_key, vehicle_key, vendor_key,
                    trip_count, occupied_raw, revenue_raw, tips_raw,
                    is_anomaly,
                ) = r

                shift_start_date_key = self._get_date_key(conn, shift_start)
                shift_start_time_key = self._get_time_key(shift_start)

                duration_minutes = Decimal("0.00")
                if shift_start and shift_end:
                    delta = shift_end - shift_start
                    duration_minutes = Decimal(str(delta.total_seconds() / 60)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )

                occupied_minutes = Decimal(str(occupied_raw)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                total_revenue = Decimal(str(revenue_raw)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                total_tips = Decimal(str(tips_raw)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

                idle_minutes = duration_minutes - occupied_minutes
                if idle_minutes < 0:
                    idle_minutes = Decimal("0.00")

                utilization_rate = Decimal("0.0000")
                if duration_minutes > 0:
                    utilization_rate = (occupied_minutes / duration_minutes).quantize(
                        Decimal("0.0001"), rounding=ROUND_HALF_UP
                    )

                shift_rows.append((
                    shift_nk,
                    shift_start_date_key,
                    shift_start_time_key,
                    driver_key,
                    vehicle_key,
                    vendor_key,
                    shift_status or "COMPLETED",
                    shift_start,
                    shift_end,
                    is_anomaly,
                    duration_minutes,
                    trip_count,
                    occupied_minutes,
                    idle_minutes,
                    utilization_rate,
                    total_revenue,
                    total_tips,
                    str(self.batch_id),
                ))

            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """
                    INSERT INTO dds.fact_driver_shift (
                        shift_id, shift_start_date_key, shift_start_time_key,
                        driver_key, vehicle_key, vendor_key,
                        shift_status, shift_start, shift_end,
                        is_anomaly, shift_duration_minutes,
                        trip_count, occupied_minutes, idle_minutes,
                        utilization_rate, total_revenue, total_tips, batch_id
                    ) VALUES %s
                    ON CONFLICT (shift_id) DO UPDATE SET
                        shift_start_date_key = EXCLUDED.shift_start_date_key,
                        shift_start_time_key = EXCLUDED.shift_start_time_key,
                        driver_key = EXCLUDED.driver_key,
                        vehicle_key = EXCLUDED.vehicle_key,
                        vendor_key = EXCLUDED.vendor_key,
                        shift_status = EXCLUDED.shift_status,
                        shift_start = EXCLUDED.shift_start,
                        shift_end = EXCLUDED.shift_end,
                        is_anomaly = EXCLUDED.is_anomaly,
                        shift_duration_minutes = EXCLUDED.shift_duration_minutes,
                        trip_count = EXCLUDED.trip_count,
                        occupied_minutes = EXCLUDED.occupied_minutes,
                        idle_minutes = EXCLUDED.idle_minutes,
                        utilization_rate = EXCLUDED.utilization_rate,
                        total_revenue = EXCLUDED.total_revenue,
                        total_tips = EXCLUDED.total_tips,
                        batch_id = EXCLUDED.batch_id
                    """,
                    shift_rows,
                    page_size=1000,
                )
            conn.commit()
            loaded += len(shift_rows)

        return loaded, 0
