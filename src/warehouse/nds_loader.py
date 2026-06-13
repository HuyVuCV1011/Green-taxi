# -*- coding: utf-8 -*-
"""NDS Loader module.

Loads data from staging tables into NDS schema tables, applying DQ Gate 1 checks,
quarantining invalid records, logging DQ issues, and handling late-arriving master records
with inferred skeleton rows.
"""

from __future__ import annotations

import os
import re
import sys
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from typing import Any, Sequence

import psycopg2
from psycopg2.extras import execute_values

class NDSLoader:
    """Orchestrates staging-to-NDS load processes with DQ checks."""

    def __init__(self, release_id: str, batch_id: UUID | None = None) -> None:
        self.release_id = release_id
        self.batch_id = batch_id or uuid4()
        self.pg_conn = None
        self.audit_conn = None
        
        # In-memory caches for surrogate keys to optimize lookups
        self.vendor_cache: dict[int, int] = {}
        self.location_cache: dict[int, int] = {}
        self.driver_cache: dict[str, int] = {}
        self.vehicle_cache: dict[str, int] = {}
        self.shift_cache: dict[str, int] = {}
        self.trip_cache: dict[str, int] = {}

        # Stats tracking for reconciliation
        self.stats: list[tuple[str, str, int, int, int, str]] = []  # (source_system, entity, read, loaded, quarantined, status)

    def connect_warehouse(self) -> Any:
        """Connect to PostgreSQL Warehouse database for NDS (transactional)."""
        if self.pg_conn is None:
            self.pg_conn = psycopg2.connect(
                host=os.getenv("POSTGRES_WAREHOUSE_HOST", "127.0.0.1"),
                port=int(os.getenv("POSTGRES_WAREHOUSE_PORT", "5434")),
                database=os.getenv("POSTGRES_WAREHOUSE_DATABASE", "green_taxi_warehouse"),
                user=os.getenv("POSTGRES_WAREHOUSE_USER", "green_taxi_warehouse_app"),
                password=os.getenv("POSTGRES_WAREHOUSE_PASSWORD", "change_me_warehouse")
            )
        return self.pg_conn

    def connect_audit(self) -> Any:
        """Connect to PostgreSQL Warehouse database for Audit logs (independent)."""
        if self.audit_conn is None:
            self.audit_conn = psycopg2.connect(
                host=os.getenv("POSTGRES_WAREHOUSE_HOST", "127.0.0.1"),
                port=int(os.getenv("POSTGRES_WAREHOUSE_PORT", "5434")),
                database=os.getenv("POSTGRES_WAREHOUSE_DATABASE", "green_taxi_warehouse"),
                user=os.getenv("POSTGRES_WAREHOUSE_USER", "green_taxi_warehouse_app"),
                password=os.getenv("POSTGRES_WAREHOUSE_PASSWORD", "change_me_warehouse")
            )
        return self.audit_conn

    def close_all(self) -> None:
        """Safely close all connections."""
        for conn_name in ("pg_conn", "audit_conn"):
            conn = getattr(self, conn_name)
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
                setattr(self, conn_name, None)

    def start_batch_log(self, source_system: str | None = None, input_params: dict | None = None) -> None:
        """Log the start of the ETL batch in audit.metadata_etl_batch."""
        conn = self.connect_audit()
        query = """
            INSERT INTO audit.metadata_etl_batch (
                batch_id, release_id, pipeline_name, batch_status,
                batch_started_at, source_system, business_timezone,
                audit_timezone, input_parameters
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    str(self.batch_id),
                    self.release_id,
                    "warehouse_nds",
                    "STARTED",
                    datetime.now(timezone.utc),
                    source_system,
                    os.getenv("BUSINESS_TIMEZONE", "America/New_York"),
                    "UTC",
                    json.dumps(input_params or {})
                )
            )
        conn.commit()

    def complete_batch_log(self, status: str, expected_rows: int = 0, loaded_rows: int = 0, error_msg: str | None = None) -> None:
        """Update batch log with execution status and record counts."""
        conn = self.connect_audit()
        query = """
            UPDATE audit.metadata_etl_batch
            SET batch_status = %s,
                batch_completed_at = %s,
                row_count_expected = %s,
                row_count_loaded = %s,
                error_message = %s,
                updated_at = %s
            WHERE batch_id = %s
        """
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    status,
                    datetime.now(timezone.utc),
                    expected_rows,
                    loaded_rows,
                    error_msg,
                    datetime.now(timezone.utc),
                    str(self.batch_id)
                )
            )
        conn.commit()

    def init_nds_schema(self) -> None:
        """Create NDS schema, tables, and DQ Quarantine tables if they do not exist."""
        conn = self.connect_warehouse()
        with conn.cursor() as cur:
            # 1. Create nds schema
            cur.execute("CREATE SCHEMA IF NOT EXISTS nds;")
            
            # 2. Ref Source System
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nds.ref_source_system (
                    source_system_code VARCHAR(50) PRIMARY KEY,
                    source_system_name VARCHAR(100) NOT NULL,
                    source_type VARCHAR(30) NOT NULL CHECK (source_type IN ('DATABASE', 'DOCUMENT', 'FILE')),
                    is_active BOOLEAN NOT NULL DEFAULT true
                );
            """)
            
            cur.execute("""
                INSERT INTO nds.ref_source_system (source_system_code, source_system_name, source_type)
                VALUES
                    ('HR_MYSQL', 'Driver HR MySQL', 'DATABASE'),
                    ('FLEET_MONGODB', 'Fleet MongoDB', 'DOCUMENT'),
                    ('DISPATCH_POSTGRES', 'Dispatch PostgreSQL', 'DATABASE'),
                    ('TLC_FILE', 'NYC TLC Green Taxi Files', 'FILE'),
                    ('LOOKUP_FILE', 'Vendor and Taxi Zone Lookup Files', 'FILE')
                ON CONFLICT (source_system_code) DO UPDATE
                SET source_system_name = EXCLUDED.source_system_name,
                    source_type = EXCLUDED.source_type,
                    is_active = true;
            """)

            # 3. NDS Vendor
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nds.nds_vendor (
                    vendor_sk INT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    vendor_nk INT UNIQUE NOT NULL,
                    vendor_name VARCHAR(100) NOT NULL,
                    source_system_code VARCHAR(50) NOT NULL REFERENCES nds.ref_source_system (source_system_code),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)

            # 4. NDS Location
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nds.nds_location (
                    location_sk INT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    location_nk INT UNIQUE NOT NULL,
                    borough VARCHAR(100) NOT NULL,
                    zone VARCHAR(100) NOT NULL,
                    service_zone VARCHAR(50) NULL,
                    source_system_code VARCHAR(50) NOT NULL REFERENCES nds.ref_source_system (source_system_code),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)

            # 5. NDS Driver
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nds.nds_driver (
                    driver_sk INT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    driver_nk VARCHAR(50) UNIQUE NOT NULL,
                    vendor_sk INT NOT NULL REFERENCES nds.nds_vendor (vendor_sk),
                    driver_code VARCHAR(50) NOT NULL,
                    display_name VARCHAR(100) NOT NULL,
                    hire_date DATE NOT NULL,
                    employment_status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
                    license_status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
                    license_expiry_date DATE NOT NULL,
                    experience_years INT NOT NULL DEFAULT 0 CHECK (experience_years >= 0),
                    home_borough VARCHAR(100) NOT NULL,
                    is_inferred BOOLEAN NOT NULL DEFAULT false,
                    source_system_code VARCHAR(50) NOT NULL REFERENCES nds.ref_source_system (source_system_code),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)

            # 6. NDS Driver History
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nds.nds_driver_history (
                    driver_history_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    driver_sk INT NOT NULL REFERENCES nds.nds_driver (driver_sk),
                    event_id VARCHAR(50) NOT NULL UNIQUE,
                    effective_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    delivered_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    attribute_name VARCHAR(100) NOT NULL,
                    old_value TEXT NULL,
                    new_value TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                CREATE INDEX IF NOT EXISTS ix_nds_driver_history_driver ON nds.nds_driver_history (driver_sk);
            """)

            # 7. NDS Vehicle
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nds.nds_vehicle (
                    vehicle_sk INT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    vehicle_nk VARCHAR(50) UNIQUE NOT NULL,
                    vendor_sk INT NOT NULL REFERENCES nds.nds_vehicle (vehicle_sk),
                    plate_token VARCHAR(100) UNIQUE NOT NULL,
                    model_year INT NOT NULL,
                    vehicle_type VARCHAR(50) NOT NULL,
                    service_start_date DATE NOT NULL,
                    vehicle_status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
                    last_inspection_date DATE NOT NULL,
                    is_inferred BOOLEAN NOT NULL DEFAULT false,
                    source_system_code VARCHAR(50) NOT NULL REFERENCES nds.ref_source_system (source_system_code),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)

            # 8. NDS Shift
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nds.nds_shift (
                    shift_sk BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    shift_nk VARCHAR(50) UNIQUE NOT NULL,
                    driver_sk INT NOT NULL REFERENCES nds.nds_driver (driver_sk),
                    vehicle_sk INT NOT NULL REFERENCES nds.nds_vehicle (vehicle_sk),
                    vendor_sk INT NOT NULL REFERENCES nds.nds_vendor (vendor_sk),
                    shift_start TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    shift_end TIMESTAMP WITHOUT TIME ZONE NOT NULL CHECK (shift_end >= shift_start),
                    assigned_start_zone INT NOT NULL REFERENCES nds.nds_location (location_sk),
                    actual_end_zone INT NOT NULL REFERENCES nds.nds_location (location_sk),
                    trip_count_source INT NOT NULL DEFAULT 0 CHECK (trip_count_source >= 0),
                    occupied_minutes_source DECIMAL(12,2) NOT NULL DEFAULT 0.0 CHECK (occupied_minutes_source >= 0.0),
                    idle_minutes_source DECIMAL(12,2) NOT NULL DEFAULT 0.0 CHECK (idle_minutes_source >= 0.0),
                    shift_status VARCHAR(50) NOT NULL DEFAULT 'COMPLETED',
                    source_system_code VARCHAR(50) NOT NULL REFERENCES nds.ref_source_system (source_system_code),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                CREATE INDEX IF NOT EXISTS ix_nds_shift_driver_time ON nds.nds_shift (driver_sk, shift_start);
            """)

            # 9. NDS Trip
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nds.nds_trip (
                    trip_sk BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    trip_nk TEXT UNIQUE NOT NULL,
                    vendor_sk INT NOT NULL REFERENCES nds.nds_vendor (vendor_sk),
                    pickup_datetime TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    dropoff_datetime TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    passenger_count INT NULL,
                    trip_distance DECIMAL(9,4) NULL,
                    pickup_location_sk INT NOT NULL REFERENCES nds.nds_location (location_sk),
                    dropoff_location_sk INT NOT NULL REFERENCES nds.nds_location (location_sk),
                    ratecode_id INT NULL,
                    store_and_fwd_flag CHAR(1) NULL,
                    payment_type INT NULL,
                    fare_amount DECIMAL(9,2) NOT NULL DEFAULT 0.00,
                    extra DECIMAL(9,2) NOT NULL DEFAULT 0.00,
                    mta_tax DECIMAL(9,2) NOT NULL DEFAULT 0.00,
                    tip_amount DECIMAL(9,2) NOT NULL DEFAULT 0.00,
                    tolls_amount DECIMAL(9,2) NOT NULL DEFAULT 0.00,
                    improvement_surcharge DECIMAL(9,2) NOT NULL DEFAULT 0.00,
                    total_amount DECIMAL(9,2) NOT NULL DEFAULT 0.00,
                    trip_type INT NULL,
                    source_file VARCHAR(255) NOT NULL,
                    source_row_number INT NOT NULL,
                    is_anomaly BOOLEAN NOT NULL DEFAULT false,
                    source_system_code VARCHAR(50) NOT NULL REFERENCES nds.ref_source_system (source_system_code),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                CREATE INDEX IF NOT EXISTS ix_nds_trip_pickup_time ON nds.nds_trip (pickup_datetime);
            """)

            # 10. NDS Trip Assignment
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nds.nds_trip_assignment (
                    assignment_sk BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    trip_sk BIGINT NOT NULL UNIQUE REFERENCES nds.nds_trip (trip_sk),
                    driver_sk INT NOT NULL REFERENCES nds.nds_driver (driver_sk),
                    vehicle_sk INT NOT NULL REFERENCES nds.nds_vehicle (vehicle_sk),
                    shift_sk BIGINT NOT NULL REFERENCES nds.nds_shift (shift_sk),
                    assignment_timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    assignment_method VARCHAR(50) NOT NULL,
                    source_system_code VARCHAR(50) NOT NULL REFERENCES nds.ref_source_system (source_system_code),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)

            # 11. Quarantine tables in dq schema
            cur.execute("""
                CREATE TABLE IF NOT EXISTS dq.quarantine_stg_hr_drivers (
                    quarantine_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    error_rule_code TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    batch_id UUID, release_id TEXT, source_system TEXT, source_entity TEXT, source_locator TEXT, source_record_id TEXT, source_extract_at TIMESTAMPTZ, load_timestamp TIMESTAMPTZ, source_checksum TEXT, extraction_watermark TEXT, row_hash TEXT, driver_id TEXT, vendor_id INTEGER, driver_code TEXT, display_name TEXT, hire_date DATE, employment_status TEXT, license_status TEXT, license_expiry_date DATE, experience_years INTEGER, home_borough TEXT, source_updated_at TIMESTAMP WITHOUT TIME ZONE
                );
                
                CREATE TABLE IF NOT EXISTS dq.quarantine_stg_hr_driver_changes (
                    quarantine_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    error_rule_code TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    batch_id UUID, release_id TEXT, source_system TEXT, source_entity TEXT, source_locator TEXT, source_record_id TEXT, source_extract_at TIMESTAMPTZ, load_timestamp TIMESTAMPTZ, source_checksum TEXT, extraction_watermark TEXT, row_hash TEXT, event_id TEXT, driver_id TEXT, event_type TEXT, effective_at TIMESTAMP WITHOUT TIME ZONE, delivered_at TIMESTAMP WITHOUT TIME ZONE, changes JSONB, is_late_arriving BOOLEAN
                );
                
                CREATE TABLE IF NOT EXISTS dq.quarantine_stg_fleet_vehicles (
                    quarantine_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    error_rule_code TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    batch_id UUID, release_id TEXT, source_system TEXT, source_entity TEXT, source_locator TEXT, source_record_id TEXT, source_extract_at TIMESTAMPTZ, load_timestamp TIMESTAMPTZ, source_checksum TEXT, extraction_watermark TEXT, row_hash TEXT, mongo_document_id TEXT, vehicle_id TEXT, vendor_id INTEGER, plate_token TEXT, model_year INTEGER, vehicle_type TEXT, service_start_date DATE, vehicle_status TEXT, last_inspection_date DATE, source_updated_at TIMESTAMP WITHOUT TIME ZONE
                );
                
                CREATE TABLE IF NOT EXISTS dq.quarantine_stg_dispatch_shifts (
                    quarantine_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    error_rule_code TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    batch_id UUID, release_id TEXT, source_system TEXT, source_entity TEXT, source_locator TEXT, source_record_id TEXT, source_extract_at TIMESTAMPTZ, load_timestamp TIMESTAMPTZ, source_checksum TEXT, extraction_watermark TEXT, row_hash TEXT, shift_id TEXT, driver_id TEXT, vehicle_id TEXT, vendor_id INTEGER, shift_start TIMESTAMP WITHOUT TIME ZONE, shift_end TIMESTAMP WITHOUT TIME ZONE, assigned_start_zone INTEGER, actual_end_zone INTEGER, trip_count INTEGER, occupied_minutes NUMERIC(12, 2), idle_minutes NUMERIC(12, 2), shift_status TEXT
                );
                
                CREATE TABLE IF NOT EXISTS dq.quarantine_stg_dispatch_trip_assignments (
                    quarantine_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    error_rule_code TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    batch_id UUID, release_id TEXT, source_system TEXT, source_entity TEXT, source_locator TEXT, source_record_id TEXT, source_extract_at TIMESTAMPTZ, load_timestamp TIMESTAMPTZ, source_checksum TEXT, extraction_watermark TEXT, row_hash TEXT, trip_key TEXT, source_file TEXT, source_row_number INTEGER, driver_id TEXT, vehicle_id TEXT, shift_id TEXT, assignment_timestamp TIMESTAMP WITHOUT TIME ZONE, assignment_method TEXT
                );
                
                CREATE TABLE IF NOT EXISTS dq.quarantine_stg_tlc_green_trips (
                    quarantine_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    error_rule_code TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    batch_id UUID, release_id TEXT, source_system TEXT, source_entity TEXT, source_locator TEXT, source_file TEXT, source_row_number INT, source_extract_at TIMESTAMPTZ, load_timestamp TIMESTAMPTZ, source_checksum TEXT, extraction_watermark TEXT, row_hash TEXT, vendor_id INTEGER, lpep_pickup_datetime TIMESTAMP WITHOUT TIME ZONE, lpep_dropoff_datetime TIMESTAMP WITHOUT TIME ZONE, store_and_fwd_flag TEXT, ratecode_id INTEGER, pu_location_id INTEGER, do_location_id INTEGER, passenger_count TEXT, trip_distance TEXT, fare_amount TEXT, total_amount TEXT, payment_type INTEGER, trip_type INTEGER, congestion_surcharge TEXT
                );
            """)

            # Pre-insert default vendor 0 (Legacy Pool)
            cur.execute("""
                INSERT INTO nds.nds_vendor (vendor_nk, vendor_name, source_system_code)
                VALUES (0, 'Legacy Pool', 'LOOKUP_FILE')
                ON CONFLICT (vendor_nk) DO NOTHING;
            """)
            
        conn.commit()

    def prepopulate_caches(self, conn: Any) -> None:
        """Pre-populate in-memory lookup caches to avoid single-row SELECTs."""
        with conn.cursor() as cur:
            # Vendor Cache
            try:
                cur.execute("SELECT vendor_nk, vendor_sk FROM nds.nds_vendor")
                rows = cur.fetchall()
                if rows and len(rows[0]) == 2:
                    self.vendor_cache = dict(rows)
            except Exception:
                pass
            
            # Location Cache
            try:
                cur.execute("SELECT location_nk, location_sk FROM nds.nds_location")
                rows = cur.fetchall()
                if rows and len(rows[0]) == 2:
                    self.location_cache = dict(rows)
            except Exception:
                pass
            
            # Driver Cache
            try:
                cur.execute("SELECT driver_nk, driver_sk FROM nds.nds_driver")
                rows = cur.fetchall()
                if rows and len(rows[0]) == 2:
                    self.driver_cache = dict(rows)
            except Exception:
                pass
            
            # Vehicle Cache
            try:
                cur.execute("SELECT vehicle_nk, vehicle_sk FROM nds.nds_vehicle")
                rows = cur.fetchall()
                if rows and len(rows[0]) == 2:
                    self.vehicle_cache = dict(rows)
            except Exception:
                pass
            
            # Shift Cache
            try:
                cur.execute("SELECT shift_nk, shift_sk FROM nds.nds_shift")
                rows = cur.fetchall()
                if rows and len(rows[0]) == 2:
                    self.shift_cache = dict(rows)
            except Exception:
                pass
            
            # Trip Cache
            try:
                cur.execute("SELECT trip_nk, trip_sk FROM nds.nds_trip")
                rows = cur.fetchall()
                if rows and len(rows[0]) == 2:
                    self.trip_cache = dict(rows)
            except Exception:
                pass

    def log_dq_issue(self, conn: Any, source_system: str, source_entity: str, source_record_id: str | None, rule_code: str, severity: str, message: str, payload: dict) -> None:
        """Insert DQ issue log into dq.dq_issue table."""
        query = """
            INSERT INTO dq.dq_issue (
                batch_id, release_id, source_system_code, source_entity,
                source_record_id, rule_code, severity, issue_message, issue_payload
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    str(self.batch_id),
                    self.release_id,
                    source_system,
                    source_entity,
                    source_record_id,
                    rule_code,
                    severity,
                    message,
                    json.dumps(payload, default=str)
                )
            )

    def write_quarantine(self, conn: Any, table_name: str, error_rule_code: str, columns: list[str], row_data: tuple) -> None:
        """Insert raw staging row data into a quarantine table in dq schema."""
        col_list = ["error_rule_code", "batch_id"] + columns
        placeholders = ["%s", "%s"] + ["%s"] * len(columns)
        
        query = f"""
            INSERT INTO dq.quarantine_{table_name} ({', '.join(col_list)})
            VALUES ({', '.join(placeholders)})
        """
        
        with conn.cursor() as cur:
            cur.execute(query, (error_rule_code, str(self.batch_id)) + row_data)

    def get_vendor_sk(self, conn: Any, vendor_nk: int | None) -> int:
        """Lookup and cache vendor surrogate key."""
        if vendor_nk is None:
            vendor_nk = 0
        if vendor_nk in self.vendor_cache:
            return self.vendor_cache[vendor_nk]
        
        with conn.cursor() as cur:
            cur.execute("SELECT vendor_sk FROM nds.nds_vendor WHERE vendor_nk = %s", (vendor_nk,))
            row = cur.fetchone()
            if row:
                self.vendor_cache[vendor_nk] = row[0]
                return row[0]
            else:
                # If not found, fall back to default vendor 0
                if vendor_nk != 0:
                    return self.get_vendor_sk(conn, 0)
                raise ValueError("Default vendor 0 not found in nds.nds_vendor!")

    def get_or_create_location_sk(self, conn: Any, location_nk: int | None, source_system: str = "LOOKUP_FILE") -> int:
        """Lookup or create skeleton location and return location_sk."""
        if location_nk is None:
            location_nk = 264  # Default to Unknown location (NV/Unknown)
        if location_nk in self.location_cache:
            return self.location_cache[location_nk]

        with conn.cursor() as cur:
            cur.execute("SELECT location_sk FROM nds.nds_location WHERE location_nk = %s", (location_nk,))
            row = cur.fetchone()
            if row:
                self.location_cache[location_nk] = row[0]
                return row[0]
            else:
                # Insert skeleton location
                cur.execute("""
                    INSERT INTO nds.nds_location (location_nk, borough, zone, service_zone, source_system_code)
                    VALUES (%s, 'Unknown', 'Unknown', 'Unknown', %s)
                    ON CONFLICT (location_nk) DO UPDATE SET updated_at = now()
                    RETURNING location_sk;
                """, (location_nk, source_system))
                loc_sk = cur.fetchone()[0]
                self.location_cache[location_nk] = loc_sk
                return loc_sk

    def get_or_create_driver_sk(self, conn: Any, driver_id: str, source_system: str = "HR_MYSQL") -> int:
        """Lookup or create skeleton driver and return driver_sk. Logs missing master warning."""
        if driver_id in self.driver_cache:
            return self.driver_cache[driver_id]

        with conn.cursor() as cur:
            cur.execute("SELECT driver_sk, is_inferred FROM nds.nds_driver WHERE driver_nk = %s", (driver_id,))
            row = cur.fetchone()
            if row:
                self.driver_cache[driver_id] = row[0]
                return row[0]
            else:
                # Create inferred driver
                vendor_sk = self.get_vendor_sk(conn, 0) # default to legacy pool
                cur.execute("""
                    INSERT INTO nds.nds_driver (
                        driver_nk, vendor_sk, driver_code, display_name, hire_date,
                        employment_status, license_status, license_expiry_date,
                        experience_years, home_borough, is_inferred, source_system_code
                    )
                    VALUES (%s, %s, 'Unknown', 'Unknown', '1970-01-01', 'ACTIVE', 'ACTIVE', '9999-12-31', 0, 'Unknown', true, %s)
                    ON CONFLICT (driver_nk) DO UPDATE SET is_inferred = true
                    RETURNING driver_sk;
                """, (driver_id, vendor_sk, source_system))
                dr_sk = cur.fetchone()[0]
                self.driver_cache[driver_id] = dr_sk
                
                # Log DQ_MISSING_MASTER
                self.log_dq_issue(
                    conn,
                    source_system=source_system,
                    source_entity="drivers",
                    source_record_id=driver_id,
                    rule_code="DQ_MISSING_MASTER",
                    severity="WARN",
                    message=f"Driver Master record missing for ID '{driver_id}'. Created skeleton member.",
                    payload={"driver_id": driver_id}
                )
                return dr_sk

    def get_or_create_vehicle_sk(self, conn: Any, vehicle_id: str, source_system: str = "FLEET_MONGODB") -> int:
        """Lookup or create skeleton vehicle and return vehicle_sk. Logs missing master warning."""
        if vehicle_id in self.vehicle_cache:
            return self.vehicle_cache[vehicle_id]

        with conn.cursor() as cur:
            cur.execute("SELECT vehicle_sk FROM nds.nds_vehicle WHERE vehicle_nk = %s", (vehicle_id,))
            row = cur.fetchone()
            if row:
                self.vehicle_cache[vehicle_id] = row[0]
                return row[0]
            else:
                # Create inferred vehicle
                vendor_sk = self.get_vendor_sk(conn, 0)
                cur.execute("""
                    INSERT INTO nds.nds_vehicle (
                        vehicle_nk, vendor_sk, plate_token, model_year, vehicle_type,
                        service_start_date, vehicle_status, last_inspection_date, is_inferred, source_system_code
                    )
                    VALUES (%s, %s, 'Unknown', 1970, 'SEDAN', '1970-01-01', 'ACTIVE', '1970-01-01', true, %s)
                    ON CONFLICT (vehicle_nk) DO UPDATE SET is_inferred = true
                    RETURNING vehicle_sk;
                """, (vehicle_id, vendor_sk, source_system))
                vh_sk = cur.fetchone()[0]
                self.vehicle_cache[vehicle_id] = vh_sk
                
                # Log DQ_MISSING_MASTER
                self.log_dq_issue(
                    conn,
                    source_system=source_system,
                    source_entity="vehicles",
                    source_record_id=vehicle_id,
                    rule_code="DQ_MISSING_MASTER",
                    severity="WARN",
                    message=f"Vehicle Master record missing for ID '{vehicle_id}'. Created skeleton member.",
                    payload={"vehicle_id": vehicle_id}
                )
                return vh_sk

    def get_or_create_shift_sk(self, conn: Any, shift_id: str, driver_sk: int, vehicle_sk: int, vendor_sk: int, ts: datetime, source_system: str = "DISPATCH_POSTGRES") -> int:
        """Lookup or create skeleton shift and return shift_sk."""
        if shift_id in self.shift_cache:
            return self.shift_cache[shift_id]
            
        with conn.cursor() as cur:
            cur.execute("SELECT shift_sk FROM nds.nds_shift WHERE shift_nk = %s", (shift_id,))
            row = cur.fetchone()
            if row:
                self.shift_cache[shift_id] = row[0]
                return row[0]
            else:
                # Create inferred shift
                loc_sk = self.get_or_create_location_sk(conn, 264)
                cur.execute("""
                    INSERT INTO nds.nds_shift (
                        shift_nk, driver_sk, vehicle_sk, vendor_sk, shift_start, shift_end,
                        assigned_start_zone, actual_end_zone, source_system_code
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (shift_nk) DO UPDATE SET updated_at = now()
                    RETURNING shift_sk;
                """, (shift_id, driver_sk, vehicle_sk, vendor_sk, ts, ts, loc_sk, loc_sk, source_system))
                sh_sk = cur.fetchone()[0]
                self.shift_cache[shift_id] = sh_sk
                
                # Log DQ_MISSING_MASTER
                self.log_dq_issue(
                    conn,
                    source_system=source_system,
                    source_entity="shifts",
                    source_record_id=shift_id,
                    rule_code="DQ_MISSING_MASTER",
                    severity="WARN",
                    message=f"Shift record missing for ID '{shift_id}'. Created skeleton member.",
                    payload={"shift_id": shift_id}
                )
                return sh_sk

    def get_or_create_trip_sk(self, conn: Any, trip_key: str, assignment_timestamp: datetime) -> int:
        """Lookup or create skeleton trip for assignment."""
        if trip_key in self.trip_cache:
            return self.trip_cache[trip_key]
            
        with conn.cursor() as cur:
            cur.execute("SELECT trip_sk FROM nds.nds_trip WHERE trip_nk = %s", (trip_key,))
            row = cur.fetchone()
            if row:
                self.trip_cache[trip_key] = row[0]
                return row[0]
            else:
                # Create inferred trip
                vendor_sk = self.get_vendor_sk(conn, 0)
                loc_sk = self.get_or_create_location_sk(conn, 264)
                cur.execute("""
                    INSERT INTO nds.nds_trip (
                        trip_nk, vendor_sk, pickup_datetime, dropoff_datetime,
                        pickup_location_sk, dropoff_location_sk, source_file, source_row_number, source_system_code
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, 'inferred', 0, 'TLC_FILE')
                    ON CONFLICT (trip_nk) DO UPDATE SET updated_at = now()
                    RETURNING trip_sk;
                """, (trip_key, vendor_sk, assignment_timestamp, assignment_timestamp, loc_sk, loc_sk))
                tr_sk = cur.fetchone()[0]
                self.trip_cache[trip_key] = tr_sk
                
                # Log DQ_MISSING_MASTER
                self.log_dq_issue(
                    conn,
                    source_system="TLC_FILE",
                    source_entity="trips",
                    source_record_id=trip_key,
                    rule_code="DQ_MISSING_MASTER",
                    severity="WARN",
                    message=f"Trip record missing for Assignment ID '{trip_key}'. Created skeleton member.",
                    payload={"trip_key": trip_key}
                )
                return tr_sk

    def load_vendor(self) -> tuple[int, int, int]:
        """Load lookup vendors."""
        dwh = self.connect_warehouse()
        source_system = "LOOKUP_FILE"
        entity = "vendor"
        
        self.prepopulate_caches(dwh)
        
        with dwh.cursor() as cur:
            cur.execute("""
                SELECT batch_id, release_id, source_system, source_entity, source_locator,
                       source_record_id, source_file, source_row_number, source_extract_at,
                       source_checksum, row_hash, vendor_id, vendor_name
                FROM staging.stg_lookup_vendor
                WHERE release_id = %s;
            """, (self.release_id,))
            rows = cur.fetchall()
            
        read_count = len(rows)
        loaded = 0
        quarantined = 0
        
        columns = [
            "batch_id", "release_id", "source_system", "source_entity", "source_locator",
            "source_record_id", "source_file", "source_row_number", "source_extract_at",
            "source_checksum", "row_hash", "vendor_id", "vendor_name"
        ]
        
        for row in rows:
            vendor_id = row[11]
            vendor_name = row[12]
            
            # DQ_NULL_PK
            if vendor_id is None:
                quarantined += 1
                self.write_quarantine(dwh, "stg_lookup_vendor", "DQ_NULL_PK", columns, row)
                self.log_dq_issue(
                    dwh, source_system, entity, None, "DQ_NULL_PK", "ERROR",
                    "Vendor ID is null", {"row": row}
                )
                continue
                
            # Upsert NDS
            with dwh.cursor() as cur:
                cur.execute("""
                    INSERT INTO nds.nds_vendor (vendor_nk, vendor_name, source_system_code)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (vendor_nk) DO UPDATE
                    SET vendor_name = EXCLUDED.vendor_name,
                        source_system_code = EXCLUDED.source_system_code,
                        updated_at = now()
                    RETURNING vendor_sk;
                """, (vendor_id, vendor_name, source_system))
                vendor_sk = cur.fetchone()[0]
                self.vendor_cache[vendor_id] = vendor_sk
                loaded += 1
                
        dwh.commit()
        status = "SUCCEEDED" if quarantined == 0 else "FAILED"
        self.stats.append((source_system, entity, read_count, loaded, quarantined, status))
        return read_count, loaded, quarantined

    def load_location(self) -> tuple[int, int, int]:
        """Load lookup taxi zones."""
        dwh = self.connect_warehouse()
        source_system = "LOOKUP_FILE"
        entity = "taxi_zone"
        
        self.prepopulate_caches(dwh)
        
        with dwh.cursor() as cur:
            cur.execute("""
                SELECT batch_id, release_id, source_system, source_entity, source_locator,
                       source_record_id, source_file, source_row_number, source_extract_at,
                       source_checksum, row_hash, location_id, borough, zone, service_zone
                FROM staging.stg_lookup_taxi_zone
                WHERE release_id = %s;
            """, (self.release_id,))
            rows = cur.fetchall()
            
        read_count = len(rows)
        loaded = 0
        quarantined = 0
        
        columns = [
            "batch_id", "release_id", "source_system", "source_entity", "source_locator",
            "source_record_id", "source_file", "source_row_number", "source_extract_at",
            "source_checksum", "row_hash", "location_id", "borough", "zone", "service_zone"
        ]
        
        for row in rows:
            location_id = row[11]
            borough = row[12]
            zone = row[13]
            service_zone = row[14]
            
            # DQ_NULL_PK
            if location_id is None:
                quarantined += 1
                self.write_quarantine(dwh, "stg_lookup_taxi_zone", "DQ_NULL_PK", columns, row)
                self.log_dq_issue(
                    dwh, source_system, entity, None, "DQ_NULL_PK", "ERROR",
                    "Location ID is null", {"row": row}
                )
                continue
                
            # Upsert NDS
            with dwh.cursor() as cur:
                cur.execute("""
                    INSERT INTO nds.nds_location (location_nk, borough, zone, service_zone, source_system_code)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (location_nk) DO UPDATE
                    SET borough = EXCLUDED.borough,
                        zone = EXCLUDED.zone,
                        service_zone = EXCLUDED.service_zone,
                        source_system_code = EXCLUDED.source_system_code,
                        updated_at = now()
                    RETURNING location_sk;
                """, (location_id, borough or 'Unknown', zone or 'Unknown', service_zone, source_system))
                location_sk = cur.fetchone()[0]
                self.location_cache[location_id] = location_sk
                loaded += 1
                
        dwh.commit()
        status = "SUCCEEDED" if quarantined == 0 else "FAILED"
        self.stats.append((source_system, entity, read_count, loaded, quarantined, status))
        return read_count, loaded, quarantined

    def load_drivers(self) -> tuple[int, int, int]:
        """Load master drivers."""
        dwh = self.connect_warehouse()
        source_system = "HR_MYSQL"
        entity = "drivers"
        
        self.prepopulate_caches(dwh)
        
        with dwh.cursor() as cur:
            cur.execute("""
                SELECT batch_id, release_id, source_system, source_entity, source_locator,
                       source_record_id, source_extract_at, row_hash,
                       driver_id, vendor_id, driver_code, display_name, hire_date,
                       employment_status, license_status, license_expiry_date,
                       experience_years, home_borough, source_updated_at
                FROM staging.stg_hr_drivers
                WHERE release_id = %s;
            """, (self.release_id,))
            rows = cur.fetchall()
            
        read_count = len(rows)
        loaded = 0
        quarantined = 0
        
        columns = [
            "batch_id", "release_id", "source_system", "source_entity", "source_locator",
            "source_record_id", "source_extract_at", "row_hash",
            "driver_id", "vendor_id", "driver_code", "display_name", "hire_date",
            "employment_status", "license_status", "license_expiry_date",
            "experience_years", "home_borough", "source_updated_at"
        ]
        
        for row in rows:
            driver_id = row[8]
            vendor_id = row[9]
            driver_code = row[10]
            display_name = row[11]
            hire_date = row[12]
            employment_status = row[13]
            license_status = row[14]
            license_expiry_date = row[15]
            experience_years = row[16]
            home_borough = row[17]
            
            # 1. DQ_NULL_PK
            if not driver_id or str(driver_id).strip() == "":
                quarantined += 1
                self.write_quarantine(dwh, "stg_hr_drivers", "DQ_NULL_PK", columns, row)
                self.log_dq_issue(
                    dwh, source_system, entity, None, "DQ_NULL_PK", "ERROR",
                    "Driver ID is null or empty", {"row": row}
                )
                continue
                
            driver_id_clean = str(driver_id).strip()
            
            # 2. DQ_FORMAT_DRV
            if not re.match(r"^DRV[0-9]{6}$", driver_id_clean):
                quarantined += 1
                self.write_quarantine(dwh, "stg_hr_drivers", "DQ_FORMAT_DRV", columns, row)
                self.log_dq_issue(
                    dwh, source_system, entity, driver_id_clean, "DQ_FORMAT_DRV", "ERROR",
                    f"Driver ID '{driver_id_clean}' violates regex ^DRV[0-9]{{6}}$", {"driver_id": driver_id_clean}
                )
                continue
                
            # 3. DQ_INVALID_ENUM
            employment_status_clean = str(employment_status).strip().upper() if employment_status else ""
            if employment_status_clean not in {"ACTIVE", "LEAVE", "INACTIVE"}:
                quarantined += 1
                self.write_quarantine(dwh, "stg_hr_drivers", "DQ_INVALID_ENUM", columns, row)
                self.log_dq_issue(
                    dwh, source_system, entity, driver_id_clean, "DQ_INVALID_ENUM", "ERROR",
                    f"Driver '{driver_id_clean}' has invalid employment status '{employment_status}'",
                    {"driver_id": driver_id_clean, "employment_status": employment_status}
                )
                continue
                
            # Upsert
            vendor_sk = self.get_vendor_sk(dwh, vendor_id)
            with dwh.cursor() as cur:
                cur.execute("""
                    INSERT INTO nds.nds_driver (
                        driver_nk, vendor_sk, driver_code, display_name, hire_date,
                        employment_status, license_status, license_expiry_date,
                        experience_years, home_borough, is_inferred, source_system_code
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, false, %s)
                    ON CONFLICT (driver_nk) DO UPDATE
                    SET vendor_sk = EXCLUDED.vendor_sk,
                        driver_code = EXCLUDED.driver_code,
                        display_name = EXCLUDED.display_name,
                        hire_date = EXCLUDED.hire_date,
                        employment_status = EXCLUDED.employment_status,
                        license_status = EXCLUDED.license_status,
                        license_expiry_date = EXCLUDED.license_expiry_date,
                        experience_years = EXCLUDED.experience_years,
                        home_borough = EXCLUDED.home_borough,
                        is_inferred = EXCLUDED.is_inferred,
                        updated_at = now()
                    RETURNING driver_sk;
                """, (driver_id_clean, vendor_sk, driver_code, display_name, hire_date,
                      employment_status_clean, license_status, license_expiry_date,
                      experience_years, home_borough, source_system))
                dr_sk = cur.fetchone()[0]
                self.driver_cache[driver_id_clean] = dr_sk
                loaded += 1
                
        dwh.commit()
        status = "SUCCEEDED" if quarantined == 0 else "FAILED"
        self.stats.append((source_system, entity, read_count, loaded, quarantined, status))
        return read_count, loaded, quarantined

    def load_driver_changes(self) -> tuple[int, int, int]:
        """Load driver change events and update driver master attributes."""
        dwh = self.connect_warehouse()
        source_system = "HR_MYSQL"
        entity = "driver_changes"
        
        self.prepopulate_caches(dwh)
        
        # Sort by delivered_at and event_id for processing
        with dwh.cursor() as cur:
            cur.execute("""
                SELECT batch_id, release_id, source_system, source_entity, source_locator,
                       source_record_id, source_extract_at, row_hash,
                       event_id, driver_id, event_type, effective_at, delivered_at,
                       changes, is_late_arriving
                FROM staging.stg_hr_driver_changes
                WHERE release_id = %s
                ORDER BY delivered_at ASC, event_id ASC;
            """, (self.release_id,))
            rows = cur.fetchall()
            
        read_count = len(rows)
        loaded = 0
        quarantined = 0
        
        columns = [
            "batch_id", "release_id", "source_system", "source_entity", "source_locator",
            "source_record_id", "source_extract_at", "row_hash",
            "event_id", "driver_id", "event_type", "effective_at", "delivered_at",
            "changes", "is_late_arriving"
        ]
        
        for row in rows:
            event_id = row[8]
            driver_id = row[9]
            event_type = row[10]
            effective_at = row[11]
            delivered_at = row[12]
            changes = row[13]
            
            # 1. DQ_NULL_PK
            if not event_id or str(event_id).strip() == "" or not driver_id or str(driver_id).strip() == "":
                quarantined += 1
                self.write_quarantine(dwh, "stg_hr_driver_changes", "DQ_NULL_PK", columns, row)
                self.log_dq_issue(
                    dwh, source_system, entity, None, "DQ_NULL_PK", "ERROR",
                    "Event ID or Driver ID is null/empty", {"row": row}
                )
                continue
                
            event_id_clean = str(event_id).strip()
            driver_id_clean = str(driver_id).strip()
            
            # 2. DQ_FORMAT_DRV
            if not re.match(r"^DRV[0-9]{6}$", driver_id_clean):
                quarantined += 1
                self.write_quarantine(dwh, "stg_hr_driver_changes", "DQ_FORMAT_DRV", columns, row)
                self.log_dq_issue(
                    dwh, source_system, entity, driver_id_clean, "DQ_FORMAT_DRV", "ERROR",
                    f"Driver ID '{driver_id_clean}' in changes violates regex ^DRV[0-9]{{6}}$", {"driver_id": driver_id_clean}
                )
                continue
                
            # Process changes JSON
            changes_dict = {}
            if isinstance(changes, str):
                try:
                    changes_dict = json.loads(changes)
                except ValueError:
                    pass
            elif isinstance(changes, dict):
                changes_dict = changes
                
            # Get or create inferred driver
            driver_sk = self.get_or_create_driver_sk(dwh, driver_id_clean)
            
            # Insert into nds_driver_history
            attribute_name = "home_borough"  # default for release v1
            new_value = changes_dict.get("home_borough", "Unknown")
            
            # Get old value if driver exists
            old_value = None
            with dwh.cursor() as cur:
                cur.execute("SELECT home_borough FROM nds.nds_driver WHERE driver_sk = %s", (driver_sk,))
                old_row = cur.fetchone()
                if old_row:
                    old_value = old_row[0]
                    
            with dwh.cursor() as cur:
                cur.execute("""
                    INSERT INTO nds.nds_driver_history (
                        driver_sk, event_id, effective_at, delivered_at, attribute_name, old_value, new_value, source_system_code
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (event_id) DO NOTHING;
                """, (driver_sk, event_id_clean, effective_at, delivered_at, attribute_name, old_value, new_value, source_system))
                
            # Update current attribute on master driver
            with dwh.cursor() as cur:
                cur.execute("""
                    UPDATE nds.nds_driver
                    SET home_borough = %s,
                        updated_at = now()
                    WHERE driver_sk = %s;
                """, (new_value, driver_sk))
                
            loaded += 1
            
        dwh.commit()
        status = "SUCCEEDED" if quarantined == 0 else "FAILED"
        self.stats.append((source_system, entity, read_count, loaded, quarantined, status))
        return read_count, loaded, quarantined

    def load_vehicles(self) -> tuple[int, int, int]:
        """Load master vehicles."""
        dwh = self.connect_warehouse()
        source_system = "FLEET_MONGODB"
        entity = "vehicles"
        
        self.prepopulate_caches(dwh)
        
        with dwh.cursor() as cur:
            cur.execute("""
                SELECT batch_id, release_id, source_system, source_entity, source_locator,
                       source_record_id, source_extract_at, row_hash,
                       mongo_document_id, vehicle_id, vendor_id, plate_token,
                       model_year, vehicle_type, service_start_date, vehicle_status,
                       last_inspection_date, source_updated_at
                FROM staging.stg_fleet_vehicles
                WHERE release_id = %s;
            """, (self.release_id,))
            rows = cur.fetchall()
            
        read_count = len(rows)
        loaded = 0
        quarantined = 0
        
        columns = [
            "batch_id", "release_id", "source_system", "source_entity", "source_locator",
            "source_record_id", "source_extract_at", "row_hash",
            "mongo_document_id", "vehicle_id", "vendor_id", "plate_token",
            "model_year", "vehicle_type", "service_start_date", "vehicle_status",
            "last_inspection_date", "source_updated_at"
        ]
        
        for row in rows:
            vehicle_id = row[9]
            vendor_id = row[10]
            plate_token = row[11]
            model_year = row[12]
            vehicle_type = row[13]
            service_start_date = row[14]
            vehicle_status = row[15]
            last_inspection_date = row[16]
            
            # 1. DQ_NULL_PK
            if not vehicle_id or str(vehicle_id).strip() == "":
                quarantined += 1
                self.write_quarantine(dwh, "stg_fleet_vehicles", "DQ_NULL_PK", columns, row)
                self.log_dq_issue(
                    dwh, source_system, entity, None, "DQ_NULL_PK", "ERROR",
                    "Vehicle ID is null or empty", {"row": row}
                )
                continue
                
            vehicle_id_clean = str(vehicle_id).strip()
            
            # 2. DQ_FORMAT_VEH
            if not re.match(r"^VEH[0-9]{6}$", vehicle_id_clean):
                quarantined += 1
                self.write_quarantine(dwh, "stg_fleet_vehicles", "DQ_FORMAT_VEH", columns, row)
                self.log_dq_issue(
                    dwh, source_system, entity, vehicle_id_clean, "DQ_FORMAT_VEH", "ERROR",
                    f"Vehicle ID '{vehicle_id_clean}' violates regex ^VEH[0-9]{{6}}$", {"vehicle_id": vehicle_id_clean}
                )
                continue
                
            # 3. DQ_INVALID_ENUM
            vehicle_status_clean = str(vehicle_status).strip().upper() if vehicle_status else ""
            if vehicle_status_clean not in {"ACTIVE", "MAINTENANCE", "RETIRED"}:
                quarantined += 1
                self.write_quarantine(dwh, "stg_fleet_vehicles", "DQ_INVALID_ENUM", columns, row)
                self.log_dq_issue(
                    dwh, source_system, entity, vehicle_id_clean, "DQ_INVALID_ENUM", "ERROR",
                    f"Vehicle '{vehicle_id_clean}' has invalid status '{vehicle_status}'",
                    {"vehicle_id": vehicle_id_clean, "vehicle_status": vehicle_status}
                )
                continue
                
            # Upsert
            vendor_sk = self.get_vendor_sk(dwh, vendor_id)
            with dwh.cursor() as cur:
                cur.execute("""
                    INSERT INTO nds.nds_vehicle (
                        vehicle_nk, vendor_sk, plate_token, model_year, vehicle_type,
                        service_start_date, vehicle_status, last_inspection_date, is_inferred, source_system_code
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, false, %s)
                    ON CONFLICT (vehicle_nk) DO UPDATE
                    SET vendor_sk = EXCLUDED.vendor_sk,
                        plate_token = EXCLUDED.plate_token,
                        model_year = EXCLUDED.model_year,
                        vehicle_type = EXCLUDED.vehicle_type,
                        service_start_date = EXCLUDED.service_start_date,
                        vehicle_status = EXCLUDED.vehicle_status,
                        last_inspection_date = EXCLUDED.last_inspection_date,
                        is_inferred = EXCLUDED.is_inferred,
                        updated_at = now()
                    RETURNING vehicle_sk;
                """, (vehicle_id_clean, vendor_sk, plate_token, model_year, vehicle_type,
                      service_start_date, vehicle_status_clean, last_inspection_date, source_system))
                vh_sk = cur.fetchone()[0]
                self.vehicle_cache[vehicle_id_clean] = vh_sk
                loaded += 1
                
        dwh.commit()
        status = "SUCCEEDED" if quarantined == 0 else "FAILED"
        self.stats.append((source_system, entity, read_count, loaded, quarantined, status))
        return read_count, loaded, quarantined

    def load_shifts(self) -> tuple[int, int, int]:
        """Load completed driver shifts."""
        dwh = self.connect_warehouse()
        source_system = "DISPATCH_POSTGRES"
        entity = "shifts"
        
        # SQL-level bulk inferred member creation
        with dwh.cursor() as cur:
            # 1. Inferred drivers for shifts
            cur.execute("""
                INSERT INTO nds.nds_driver (
                    driver_nk, vendor_sk, driver_code, display_name, hire_date,
                    employment_status, license_status, license_expiry_date,
                    experience_years, home_borough, is_inferred, source_system_code
                )
                SELECT DISTINCT s.driver_id, 
                       (SELECT vendor_sk FROM nds.nds_vendor WHERE vendor_nk = 0),
                       'Unknown', 'Unknown', '1970-01-01'::DATE, 'ACTIVE', 'ACTIVE', '9999-12-31'::DATE, 0, 'Unknown', true, 'HR_MYSQL'
                FROM staging.stg_dispatch_shifts s
                LEFT JOIN nds.nds_driver d ON d.driver_nk = s.driver_id
                WHERE s.release_id = %s AND d.driver_nk IS NULL AND s.driver_id IS NOT NULL AND s.driver_id <> '' AND s.driver_id ~ '^DRV[0-9]{6}$'
                ON CONFLICT (driver_nk) DO NOTHING;
            """, (self.release_id,))
            
            # Log DQ_MISSING_MASTER warnings for shifts
            cur.execute("""
                INSERT INTO dq.dq_issue (
                    batch_id, release_id, source_system_code, source_entity,
                    source_record_id, rule_code, severity, issue_message, issue_payload
                )
                SELECT DISTINCT %s::UUID, %s, 'HR_MYSQL', 'drivers',
                       s.driver_id, 'DQ_MISSING_MASTER', 'WARN',
                       'Driver Master record missing for ID ''' || s.driver_id || '''. Created skeleton member.',
                       jsonb_build_object('driver_id', s.driver_id)
                FROM staging.stg_dispatch_shifts s
                JOIN nds.nds_driver d ON d.driver_nk = s.driver_id
                WHERE s.release_id = %s AND d.is_inferred = true AND NOT EXISTS (
                    SELECT 1 FROM dq.dq_issue i WHERE i.batch_id = %s AND i.source_record_id = s.driver_id AND i.rule_code = 'DQ_MISSING_MASTER'
                );
            """, (str(self.batch_id), self.release_id, self.release_id, str(self.batch_id)))
            
            # 2. Inferred vehicles for shifts
            cur.execute("""
                INSERT INTO nds.nds_vehicle (
                    vehicle_nk, vendor_sk, plate_token, model_year, vehicle_type,
                    service_start_date, vehicle_status, last_inspection_date, is_inferred, source_system_code
                )
                SELECT DISTINCT s.vehicle_id,
                       (SELECT vendor_sk FROM nds.nds_vendor WHERE vendor_nk = 0),
                       'Unknown', 1970, 'SEDAN', '1970-01-01'::DATE, 'ACTIVE', '1970-01-01'::DATE, true, 'FLEET_MONGODB'
                FROM staging.stg_dispatch_shifts s
                LEFT JOIN nds.nds_vehicle v ON v.vehicle_nk = s.vehicle_id
                WHERE s.release_id = %s AND v.vehicle_nk IS NULL AND s.vehicle_id IS NOT NULL AND s.vehicle_id <> '' AND s.vehicle_id ~ '^VEH[0-9]{6}$'
                ON CONFLICT (vehicle_nk) DO NOTHING;
            """, (self.release_id,))
            
            # Log DQ_MISSING_MASTER warnings for shifts
            cur.execute("""
                INSERT INTO dq.dq_issue (
                    batch_id, release_id, source_system_code, source_entity,
                    source_record_id, rule_code, severity, issue_message, issue_payload
                )
                SELECT DISTINCT %s::UUID, %s, 'FLEET_MONGODB', 'vehicles',
                       s.vehicle_id, 'DQ_MISSING_MASTER', 'WARN',
                       'Vehicle Master record missing for ID ''' || s.vehicle_id || '''. Created skeleton member.',
                       jsonb_build_object('vehicle_id', s.vehicle_id)
                FROM staging.stg_dispatch_shifts s
                JOIN nds.nds_vehicle v ON v.vehicle_nk = s.vehicle_id
                WHERE s.release_id = %s AND v.is_inferred = true AND NOT EXISTS (
                    SELECT 1 FROM dq.dq_issue i WHERE i.batch_id = %s AND i.source_record_id = s.vehicle_id AND i.rule_code = 'DQ_MISSING_MASTER'
                );
            """, (str(self.batch_id), self.release_id, self.release_id, str(self.batch_id)))
            
        dwh.commit()
        
        self.prepopulate_caches(dwh)
        
        offset = 0
        batch_size = 5000
        
        read_count = 0
        loaded = 0
        quarantined = 0
        
        columns = [
            "batch_id", "release_id", "source_system", "source_entity", "source_locator",
            "source_record_id", "source_extract_at", "row_hash",
            "shift_id", "driver_id", "vehicle_id", "vendor_id", "shift_start", "shift_end",
            "assigned_start_zone", "actual_end_zone", "trip_count", "occupied_minutes",
            "idle_minutes", "shift_status"
        ]
        
        last_shift_id = None
        while True:
            with dwh.cursor() as cur:
                if last_shift_id is None:
                    cur.execute("""
                        SELECT batch_id, release_id, source_system, source_entity, source_locator,
                               source_record_id, source_extract_at, row_hash,
                               shift_id, driver_id, vehicle_id, vendor_id, shift_start, shift_end,
                               assigned_start_zone, actual_end_zone, trip_count, occupied_minutes,
                               idle_minutes, shift_status
                        FROM staging.stg_dispatch_shifts
                        WHERE release_id = %s
                        ORDER BY shift_id
                        LIMIT %s;
                    """, (self.release_id, batch_size))
                else:
                    cur.execute("""
                        SELECT batch_id, release_id, source_system, source_entity, source_locator,
                               source_record_id, source_extract_at, row_hash,
                               shift_id, driver_id, vehicle_id, vendor_id, shift_start, shift_end,
                               assigned_start_zone, actual_end_zone, trip_count, occupied_minutes,
                               idle_minutes, shift_status
                        FROM staging.stg_dispatch_shifts
                        WHERE release_id = %s AND shift_id > %s
                        ORDER BY shift_id
                        LIMIT %s;
                    """, (self.release_id, last_shift_id, batch_size))
                rows = cur.fetchall()
                
            if not rows:
                break
                
            read_count += len(rows)
            last_shift_id = rows[-1][8]
            
            chunk = []
            for row in rows:
                shift_id = row[8]
                driver_id = row[9]
                vehicle_id = row[10]
                vendor_id = row[11]
                shift_start = row[12]
                shift_end = row[13]
                assigned_start_zone = row[14]
                actual_end_zone = row[15]
                trip_count = row[16]
                occupied_minutes = row[17]
                idle_minutes = row[18]
                shift_status = row[19]
                
                # 1. DQ_NULL_PK
                if not shift_id or str(shift_id).strip() == "" or not driver_id or str(driver_id).strip() == "" or not vehicle_id or str(vehicle_id).strip() == "":
                    quarantined += 1
                    self.write_quarantine(dwh, "stg_dispatch_shifts", "DQ_NULL_PK", columns, row)
                    self.log_dq_issue(
                        dwh, source_system, entity, shift_id, "DQ_NULL_PK", "ERROR",
                        "Shift ID, Driver ID, or Vehicle ID is null/empty", {"row": row}
                    )
                    continue
                    
                shift_id_clean = str(shift_id).strip()
                driver_id_clean = str(driver_id).strip()
                vehicle_id_clean = str(vehicle_id).strip()
                
                # 2. DQ_FORMAT_DRV
                if not re.match(r"^DRV[0-9]{6}$", driver_id_clean):
                    quarantined += 1
                    self.write_quarantine(dwh, "stg_dispatch_shifts", "DQ_FORMAT_DRV", columns, row)
                    self.log_dq_issue(
                        dwh, source_system, entity, shift_id_clean, "DQ_FORMAT_DRV", "ERROR",
                        f"Driver ID '{driver_id_clean}' in shift '{shift_id_clean}' violates regex ^DRV[0-9]{{6}}$", {"driver_id": driver_id_clean}
                    )
                    continue
                    
                # 3. DQ_FORMAT_VEH
                if not re.match(r"^VEH[0-9]{6}$", vehicle_id_clean):
                    quarantined += 1
                    self.write_quarantine(dwh, "stg_dispatch_shifts", "DQ_FORMAT_VEH", columns, row)
                    self.log_dq_issue(
                        dwh, source_system, entity, shift_id_clean, "DQ_FORMAT_VEH", "ERROR",
                        f"Vehicle ID '{vehicle_id_clean}' in shift '{shift_id_clean}' violates regex ^VEH[0-9]{{6}}$", {"vehicle_id": vehicle_id_clean}
                    )
                    continue
                    
                # 4. DQ_DATE_ORDER
                if shift_start is None or shift_end is None or shift_end < shift_start:
                    quarantined += 1
                    self.write_quarantine(dwh, "stg_dispatch_shifts", "DQ_DATE_ORDER", columns, row)
                    self.log_dq_issue(
                        dwh, source_system, entity, shift_id_clean, "DQ_DATE_ORDER", "ERROR",
                        f"Shift '{shift_id_clean}' has invalid dates. Start: {shift_start}, End: {shift_end}",
                        {"shift_id": shift_id_clean, "shift_start": shift_start, "shift_end": shift_end}
                    )
                    continue
                    
                # Lookup cached master keys
                driver_sk = self.get_or_create_driver_sk(dwh, driver_id_clean)
                vehicle_sk = self.get_or_create_vehicle_sk(dwh, vehicle_id_clean)
                vendor_sk = self.get_vendor_sk(dwh, vendor_id)
                
                # Check taxi zones
                start_zone_sk = self.get_or_create_location_sk(dwh, assigned_start_zone)
                end_zone_sk = self.get_or_create_location_sk(dwh, actual_end_zone)
                
                chunk.append((
                    shift_id_clean, driver_sk, vehicle_sk, vendor_sk, shift_start, shift_end,
                    start_zone_sk, end_zone_sk, trip_count, occupied_minutes, idle_minutes,
                    shift_status or 'COMPLETED', source_system
                ))
            
            # Bulk upsert NDS
            if chunk:
                query = """
                    INSERT INTO nds.nds_shift (
                        shift_nk, driver_sk, vehicle_sk, vendor_sk, shift_start, shift_end,
                        assigned_start_zone, actual_end_zone, trip_count_source,
                        occupied_minutes_source, idle_minutes_source, shift_status, source_system_code
                    )
                    VALUES %s
                    ON CONFLICT (shift_nk) DO UPDATE
                    SET driver_sk = EXCLUDED.driver_sk,
                        vehicle_sk = EXCLUDED.vehicle_sk,
                        vendor_sk = EXCLUDED.vendor_sk,
                        shift_start = EXCLUDED.shift_start,
                        shift_end = EXCLUDED.shift_end,
                        assigned_start_zone = EXCLUDED.assigned_start_zone,
                        actual_end_zone = EXCLUDED.actual_end_zone,
                        trip_count_source = EXCLUDED.trip_count_source,
                        occupied_minutes_source = EXCLUDED.occupied_minutes_source,
                        idle_minutes_source = EXCLUDED.idle_minutes_source,
                        shift_status = EXCLUDED.shift_status,
                        source_system_code = EXCLUDED.source_system_code,
                        updated_at = now();
                """
                with dwh.cursor() as cur:
                    execute_values(cur, query, chunk)
                loaded += len(chunk)
                
            dwh.commit()
            
        status = "SUCCEEDED" if quarantined == 0 else "FAILED"
        self.stats.append((source_system, entity, read_count, loaded, quarantined, status))
        return read_count, loaded, quarantined

    def load_trips(self, limit_rows: int | None = None) -> tuple[int, int, int]:
        """Load TLC Green Trips."""
        dwh = self.connect_warehouse()
        source_system = "TLC_FILE"
        entity = "tlc_green_tripdata"
        
        self.prepopulate_caches(dwh)
        
        offset = 0
        batch_size = 5000
        
        read_count = 0
        loaded = 0
        quarantined = 0
        
        columns = [
            "batch_id", "release_id", "source_system", "source_entity", "source_locator",
            "source_file", "source_row_number", "source_extract_at", "load_timestamp",
            "source_checksum", "extraction_watermark", "row_hash",
            "vendor_id", "lpep_pickup_datetime", "lpep_dropoff_datetime", "store_and_fwd_flag",
            "ratecode_id", "pu_location_id", "do_location_id", "passenger_count", "trip_distance",
            "fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount", "ehail_fee",
            "improvement_surcharge", "total_amount", "payment_type", "trip_type", "congestion_surcharge"
        ]
        
        while True:
            current_batch_size = batch_size
            if limit_rows is not None:
                if read_count >= limit_rows:
                    break
                if read_count + batch_size > limit_rows:
                    current_batch_size = limit_rows - read_count
                    
            with dwh.cursor() as cur:
                cur.execute("""
                    SELECT batch_id, release_id, source_system, source_entity, source_locator,
                           source_file, source_row_number, source_extract_at, load_timestamp,
                           source_checksum, extraction_watermark, row_hash,
                           vendor_id, lpep_pickup_datetime, lpep_dropoff_datetime, store_and_fwd_flag,
                           ratecode_id, pu_location_id, do_location_id, passenger_count, trip_distance,
                           fare_amount, extra, mta_tax, tip_amount, tolls_amount, ehail_fee,
                           improvement_surcharge, total_amount, payment_type, trip_type, congestion_surcharge,
                           staging_row_id
                    FROM staging.stg_tlc_green_trips
                    WHERE release_id = %s
                    ORDER BY staging_row_id
                    LIMIT %s OFFSET %s;
                """, (self.release_id, current_batch_size, offset))
                rows = cur.fetchall()
                
            if not rows:
                break
                
            read_count += len(rows)
            offset += len(rows)
            
            chunk = []
            for row in rows:
                vendor_id = row[12]
                pickup_datetime = row[13]
                dropoff_datetime = row[14]
                store_and_fwd_flag = row[15]
                ratecode_id = row[16]
                pu_location_id = row[17]
                do_location_id = row[18]
                passenger_count = row[19]
                trip_distance = row[20]
                fare_amount = row[21]
                extra = row[22]
                mta_tax = row[23]
                tip_amount = row[24]
                tolls_amount = row[25]
                improvement_surcharge = row[27]
                total_amount = row[28]
                payment_type = row[29]
                trip_type = row[30]
                source_file = row[5]
                source_row_number = row[6]
                trip_nk = row[4]
                
                # 1. DQ_NULL_PK
                if not trip_nk or str(trip_nk).strip() == "":
                    quarantined += 1
                    self.write_quarantine(dwh, "stg_tlc_green_trips", "DQ_NULL_PK", columns, row[:-1])
                    self.log_dq_issue(
                        dwh, source_system, entity, None, "DQ_NULL_PK", "ERROR",
                        "Trip Key (source_record_id) is null or empty", {"row": row}
                    )
                    continue
                    
                trip_nk_clean = str(trip_nk).strip()
                
                # 2. DQ_NEGATIVE_VAL (WARN)
                is_negative = False
                negative_fields = []
                for field_name, val in [("fare_amount", fare_amount), ("total_amount", total_amount), ("trip_distance", trip_distance)]:
                    if val is not None and val < 0:
                        is_negative = True
                        negative_fields.append(f"{field_name}={val}")
                        
                if is_negative:
                    self.log_dq_issue(
                        dwh, source_system, entity, trip_nk_clean, "DQ_NEGATIVE_VAL", "WARN",
                        f"Trip '{trip_nk_clean}' has negative financial/distance values: {', '.join(negative_fields)}",
                        {"trip_key": trip_nk_clean, "fare_amount": fare_amount, "total_amount": total_amount, "trip_distance": trip_distance}
                    )
                
                pu_sk = self.get_or_create_location_sk(dwh, pu_location_id, source_system)
                do_sk = self.get_or_create_location_sk(dwh, do_location_id, source_system)
                vendor_sk = self.get_vendor_sk(dwh, vendor_id)
                
                chunk.append((
                    trip_nk_clean, vendor_sk, pickup_datetime, dropoff_datetime, passenger_count,
                    trip_distance, pu_sk, do_sk, ratecode_id,
                    store_and_fwd_flag, payment_type, fare_amount or 0.00, extra or 0.00, mta_tax or 0.00,
                    tip_amount or 0.00, tolls_amount or 0.00, improvement_surcharge or 0.00, total_amount or 0.00,
                    trip_type, source_file, source_row_number, source_system
                ))
                
            # Bulk upsert NDS
            if chunk:
                query = """
                    INSERT INTO nds.nds_trip (
                        trip_nk, vendor_sk, pickup_datetime, dropoff_datetime, passenger_count,
                        trip_distance, pickup_location_sk, dropoff_location_sk, ratecode_id,
                        store_and_fwd_flag, payment_type, fare_amount, extra, mta_tax,
                        tip_amount, tolls_amount, improvement_surcharge, total_amount,
                        trip_type, source_file, source_row_number, is_anomaly, source_system_code
                    )
                    VALUES %s
                    ON CONFLICT (trip_nk) DO UPDATE
                    SET vendor_sk = EXCLUDED.vendor_sk,
                        pickup_datetime = EXCLUDED.pickup_datetime,
                        dropoff_datetime = EXCLUDED.dropoff_datetime,
                        passenger_count = EXCLUDED.passenger_count,
                        trip_distance = EXCLUDED.trip_distance,
                        pickup_location_sk = EXCLUDED.pickup_location_sk,
                        dropoff_location_sk = EXCLUDED.dropoff_location_sk,
                        ratecode_id = EXCLUDED.ratecode_id,
                        store_and_fwd_flag = EXCLUDED.store_and_fwd_flag,
                        payment_type = EXCLUDED.payment_type,
                        fare_amount = EXCLUDED.fare_amount,
                        extra = EXCLUDED.extra,
                        mta_tax = EXCLUDED.mta_tax,
                        tip_amount = EXCLUDED.tip_amount,
                        tolls_amount = EXCLUDED.tolls_amount,
                        improvement_surcharge = EXCLUDED.improvement_surcharge,
                        total_amount = EXCLUDED.total_amount,
                        trip_type = EXCLUDED.trip_type,
                        source_file = EXCLUDED.source_file,
                        source_row_number = EXCLUDED.source_row_number,
                        is_anomaly = EXCLUDED.is_anomaly,
                        source_system_code = EXCLUDED.source_system_code,
                        updated_at = now();
                """
                with dwh.cursor() as cur:
                    execute_values(cur, query, chunk)
                loaded += len(chunk)
                
            dwh.commit()
            
        status = "SUCCEEDED" if quarantined == 0 else "FAILED"
        self.stats.append((source_system, entity, read_count, loaded, quarantined, status))
        return read_count, loaded, quarantined

    def load_trip_assignments(self) -> tuple[int, int, int]:
        """Load dispatch trip assignments."""
        dwh = self.connect_warehouse()
        source_system = "DISPATCH_POSTGRES"
        entity = "trip_assignments"
        
        # SQL-level bulk inferred member creation
        with dwh.cursor() as cur:
            # 1. Inferred drivers for assignments
            cur.execute("""
                INSERT INTO nds.nds_driver (
                    driver_nk, vendor_sk, driver_code, display_name, hire_date,
                    employment_status, license_status, license_expiry_date,
                    experience_years, home_borough, is_inferred, source_system_code
                )
                SELECT DISTINCT ta.driver_id, 
                       (SELECT vendor_sk FROM nds.nds_vendor WHERE vendor_nk = 0),
                       'Unknown', 'Unknown', '1970-01-01'::DATE, 'ACTIVE', 'ACTIVE', '9999-12-31'::DATE, 0, 'Unknown', true, 'HR_MYSQL'
                FROM staging.stg_dispatch_trip_assignments ta
                LEFT JOIN nds.nds_driver d ON d.driver_nk = ta.driver_id
                WHERE ta.release_id = %s AND d.driver_nk IS NULL AND ta.driver_id IS NOT NULL AND ta.driver_id <> '' AND ta.driver_id ~ '^DRV[0-9]{6}$'
                ON CONFLICT (driver_nk) DO NOTHING;
            """, (self.release_id,))
            
            # Log DQ_MISSING_MASTER warnings for drivers in assignments
            cur.execute("""
                INSERT INTO dq.dq_issue (
                    batch_id, release_id, source_system_code, source_entity,
                    source_record_id, rule_code, severity, issue_message, issue_payload
                )
                SELECT DISTINCT %s::UUID, %s, 'HR_MYSQL', 'drivers',
                       ta.driver_id, 'DQ_MISSING_MASTER', 'WARN',
                       'Driver Master record missing for ID ''' || ta.driver_id || '''. Created skeleton member.',
                       jsonb_build_object('driver_id', ta.driver_id)
                FROM staging.stg_dispatch_trip_assignments ta
                JOIN nds.nds_driver d ON d.driver_nk = ta.driver_id
                WHERE ta.release_id = %s AND d.is_inferred = true AND NOT EXISTS (
                    SELECT 1 FROM dq.dq_issue i WHERE i.batch_id = %s AND i.source_record_id = ta.driver_id AND i.rule_code = 'DQ_MISSING_MASTER'
                );
            """, (str(self.batch_id), self.release_id, self.release_id, str(self.batch_id)))
            
            # 2. Inferred vehicles for assignments
            cur.execute("""
                INSERT INTO nds.nds_vehicle (
                    vehicle_nk, vendor_sk, plate_token, model_year, vehicle_type,
                    service_start_date, vehicle_status, last_inspection_date, is_inferred, source_system_code
                )
                SELECT DISTINCT ta.vehicle_id,
                       (SELECT vendor_sk FROM nds.nds_vendor WHERE vendor_nk = 0),
                       'Unknown', 1970, 'SEDAN', '1970-01-01'::DATE, 'ACTIVE', '1970-01-01'::DATE, true, 'FLEET_MONGODB'
                FROM staging.stg_dispatch_trip_assignments ta
                LEFT JOIN nds.nds_vehicle v ON v.vehicle_nk = ta.vehicle_id
                WHERE ta.release_id = %s AND v.vehicle_nk IS NULL AND ta.vehicle_id IS NOT NULL AND ta.vehicle_id <> '' AND ta.vehicle_id ~ '^VEH[0-9]{6}$'
                ON CONFLICT (vehicle_nk) DO NOTHING;
            """, (self.release_id,))
            
            # Log DQ_MISSING_MASTER warnings for vehicles in assignments
            cur.execute("""
                INSERT INTO dq.dq_issue (
                    batch_id, release_id, source_system_code, source_entity,
                    source_record_id, rule_code, severity, issue_message, issue_payload
                )
                SELECT DISTINCT %s::UUID, %s, 'FLEET_MONGODB', 'vehicles',
                       ta.vehicle_id, 'DQ_MISSING_MASTER', 'WARN',
                       'Vehicle Master record missing for ID ''' || ta.vehicle_id || '''. Created skeleton member.',
                       jsonb_build_object('vehicle_id', ta.vehicle_id)
                FROM staging.stg_dispatch_trip_assignments ta
                JOIN nds.nds_vehicle v ON v.vehicle_nk = ta.vehicle_id
                WHERE ta.release_id = %s AND v.is_inferred = true AND NOT EXISTS (
                    SELECT 1 FROM dq.dq_issue i WHERE i.batch_id = %s AND i.source_record_id = ta.vehicle_id AND i.rule_code = 'DQ_MISSING_MASTER'
                );
            """, (str(self.batch_id), self.release_id, self.release_id, str(self.batch_id)))
            
            # 3. Inferred trips for assignments (Essential for performance as TLC trips might not be loaded yet)
            cur.execute("""
                INSERT INTO nds.nds_trip (
                    trip_nk, vendor_sk, pickup_datetime, dropoff_datetime, 
                    pickup_location_sk, dropoff_location_sk, source_file, source_row_number, source_system_code
                )
                SELECT DISTINCT ta.trip_key, 
                       (SELECT vendor_sk FROM nds.nds_vendor WHERE vendor_nk = 0),
                       ta.assignment_timestamp, 
                       ta.assignment_timestamp,
                       (SELECT location_sk FROM nds.nds_location WHERE location_nk = 264),
                       (SELECT location_sk FROM nds.nds_location WHERE location_nk = 264),
                       'inferred', 2, 'TLC_FILE'
                FROM staging.stg_dispatch_trip_assignments ta
                LEFT JOIN nds.nds_trip t ON t.trip_nk = ta.trip_key
                WHERE ta.release_id = %s AND t.trip_nk IS NULL AND ta.trip_key IS NOT NULL AND ta.trip_key <> ''
                ON CONFLICT (trip_nk) DO NOTHING;
            """, (self.release_id,))
            
            # Log DQ_MISSING_MASTER warnings for trips in assignments
            cur.execute("""
                INSERT INTO dq.dq_issue (
                    batch_id, release_id, source_system_code, source_entity,
                    source_record_id, rule_code, severity, issue_message, issue_payload
                )
                SELECT DISTINCT %s::UUID, %s, 'TLC_FILE', 'trips',
                       ta.trip_key, 'DQ_MISSING_MASTER', 'WARN',
                       'Trip Master record missing for Assignment ID ''' || ta.trip_key || '''. Created skeleton member.',
                       jsonb_build_object('trip_key', ta.trip_key)
                FROM staging.stg_dispatch_trip_assignments ta
                JOIN nds.nds_trip t ON t.trip_nk = ta.trip_key
                WHERE ta.release_id = %s AND t.source_file = 'inferred' AND NOT EXISTS (
                    SELECT 1 FROM dq.dq_issue i WHERE i.batch_id = %s AND i.source_record_id = ta.trip_key AND i.rule_code = 'DQ_MISSING_MASTER'
                );
            """, (str(self.batch_id), self.release_id, self.release_id, str(self.batch_id)))
            
            # 4. Inferred shifts for assignments
            cur.execute("""
                INSERT INTO nds.nds_shift (
                    shift_nk, driver_sk, vehicle_sk, vendor_sk, shift_start, shift_end,
                    assigned_start_zone, actual_end_zone, source_system_code
                )
                SELECT DISTINCT ta.shift_id,
                       d.driver_sk,
                       v.vehicle_sk,
                       (SELECT vendor_sk FROM nds.nds_vendor WHERE vendor_nk = 0),
                       ta.assignment_timestamp,
                       ta.assignment_timestamp,
                       (SELECT location_sk FROM nds.nds_location WHERE location_nk = 264),
                       (SELECT location_sk FROM nds.nds_location WHERE location_nk = 264),
                       'DISPATCH_POSTGRES'
                FROM staging.stg_dispatch_trip_assignments ta
                JOIN nds.nds_driver d ON d.driver_nk = ta.driver_id
                JOIN nds.nds_vehicle v ON v.vehicle_nk = ta.vehicle_id
                LEFT JOIN nds.nds_shift s ON s.shift_nk = ta.shift_id
                WHERE ta.release_id = %s AND s.shift_nk IS NULL AND ta.shift_id IS NOT NULL AND ta.shift_id <> ''
                ON CONFLICT (shift_nk) DO NOTHING;
            """, (self.release_id,))
            
            # Log DQ_MISSING_MASTER warnings for shifts in assignments
            cur.execute("""
                INSERT INTO dq.dq_issue (
                    batch_id, release_id, source_system_code, source_entity,
                    source_record_id, rule_code, severity, issue_message, issue_payload
                )
                SELECT DISTINCT %s::UUID, %s, 'DISPATCH_POSTGRES', 'shifts',
                       ta.shift_id, 'DQ_MISSING_MASTER', 'WARN',
                       'Shift record missing for ID ''' || ta.shift_id || '''. Created skeleton member.',
                       jsonb_build_object('shift_id', ta.shift_id)
                FROM staging.stg_dispatch_trip_assignments ta
                JOIN nds.nds_shift s ON s.shift_nk = ta.shift_id
                WHERE ta.release_id = %s AND s.trip_count_source = 0 AND s.occupied_minutes_source = 0 AND NOT EXISTS (
                    SELECT 1 FROM dq.dq_issue i WHERE i.batch_id = %s AND i.source_record_id = ta.shift_id AND i.rule_code = 'DQ_MISSING_MASTER'
                );
            """, (str(self.batch_id), self.release_id, self.release_id, str(self.batch_id)))
            
        dwh.commit()
        
        self.prepopulate_caches(dwh)
        
        offset = 0
        batch_size = 5000
        
        read_count = 0
        loaded = 0
        quarantined = 0
        
        columns = [
            "batch_id", "release_id", "source_system", "source_entity", "source_locator",
            "source_record_id", "source_extract_at", "row_hash",
            "trip_key", "source_file", "source_row_number", "driver_id", "vehicle_id",
            "shift_id", "assignment_timestamp", "assignment_method"
        ]
        
        last_trip_key = None
        while True:
            with dwh.cursor() as cur:
                if last_trip_key is None:
                    cur.execute("""
                        SELECT batch_id, release_id, source_system, source_entity, source_locator,
                               source_record_id, source_extract_at, row_hash,
                               trip_key, source_file, source_row_number, driver_id, vehicle_id,
                               shift_id, assignment_timestamp, assignment_method
                        FROM staging.stg_dispatch_trip_assignments
                        WHERE release_id = %s
                        ORDER BY trip_key
                        LIMIT %s;
                    """, (self.release_id, batch_size))
                else:
                    cur.execute("""
                        SELECT batch_id, release_id, source_system, source_entity, source_locator,
                               source_record_id, source_extract_at, row_hash,
                               trip_key, source_file, source_row_number, driver_id, vehicle_id,
                               shift_id, assignment_timestamp, assignment_method
                        FROM staging.stg_dispatch_trip_assignments
                        WHERE release_id = %s AND trip_key > %s
                        ORDER BY trip_key
                        LIMIT %s;
                    """, (self.release_id, last_trip_key, batch_size))
                rows = cur.fetchall()
                
            if not rows:
                break
                
            read_count += len(rows)
            last_trip_key = rows[-1][8]
            
            chunk = []
            for row in rows:
                trip_key = row[8]
                source_file = row[9]
                source_row_number = row[10]
                driver_id = row[11]
                vehicle_id = row[12]
                shift_id = row[13]
                assignment_timestamp = row[14]
                assignment_method = row[15]
                
                # 1. DQ_NULL_PK
                if not trip_key or str(trip_key).strip() == "" or not driver_id or str(driver_id).strip() == "" or not vehicle_id or str(vehicle_id).strip() == "" or not shift_id or str(shift_id).strip() == "":
                    quarantined += 1
                    self.write_quarantine(dwh, "stg_dispatch_trip_assignments", "DQ_NULL_PK", columns, row)
                    self.log_dq_issue(
                        dwh, source_system, entity, trip_key, "DQ_NULL_PK", "ERROR",
                        "Trip Key, Driver ID, Vehicle ID, or Shift ID is null/empty", {"row": row}
                    )
                    continue
                    
                trip_key_clean = str(trip_key).strip()
                driver_id_clean = str(driver_id).strip()
                vehicle_id_clean = str(vehicle_id).strip()
                shift_id_clean = str(shift_id).strip()
                
                # 2. DQ_FORMAT_DRV
                if not re.match(r"^DRV[0-9]{6}$", driver_id_clean):
                    quarantined += 1
                    self.write_quarantine(dwh, "stg_dispatch_trip_assignments", "DQ_FORMAT_DRV", columns, row)
                    self.log_dq_issue(
                        dwh, source_system, entity, trip_key_clean, "DQ_FORMAT_DRV", "ERROR",
                        f"Driver ID '{driver_id_clean}' in assignment violates regex ^DRV[0-9]{{6}}$", {"driver_id": driver_id_clean}
                    )
                    continue
                    
                # 3. DQ_FORMAT_VEH
                if not re.match(r"^VEH[0-9]{6}$", vehicle_id_clean):
                    quarantined += 1
                    self.write_quarantine(dwh, "stg_dispatch_trip_assignments", "DQ_FORMAT_VEH", columns, row)
                    self.log_dq_issue(
                        dwh, source_system, entity, trip_key_clean, "DQ_FORMAT_VEH", "ERROR",
                        f"Vehicle ID '{vehicle_id_clean}' in assignment violates regex ^VEH[0-9]{{6}}$", {"vehicle_id": vehicle_id_clean}
                    )
                    continue
                    
                # Lookups (should all be cache hit now)
                driver_sk = self.get_or_create_driver_sk(dwh, driver_id_clean)
                vehicle_sk = self.get_or_create_vehicle_sk(dwh, vehicle_id_clean)
                vendor_sk = self.get_vendor_sk(dwh, 0)
                
                shift_sk = self.get_or_create_shift_sk(dwh, shift_id_clean, driver_sk, vehicle_sk, vendor_sk, assignment_timestamp)
                trip_sk = self.get_or_create_trip_sk(dwh, trip_key_clean, assignment_timestamp)
                
                chunk.append((trip_sk, driver_sk, vehicle_sk, shift_sk, assignment_timestamp, assignment_method, source_system))
                
            # Bulk upsert NDS
            if chunk:
                query = """
                    INSERT INTO nds.nds_trip_assignment (
                        trip_sk, driver_sk, vehicle_sk, shift_sk, assignment_timestamp, assignment_method, source_system_code
                    )
                    VALUES %s
                    ON CONFLICT (trip_sk) DO UPDATE
                    SET driver_sk = EXCLUDED.driver_sk,
                        vehicle_sk = EXCLUDED.vehicle_sk,
                        shift_sk = EXCLUDED.shift_sk,
                        assignment_timestamp = EXCLUDED.assignment_timestamp,
                        assignment_method = EXCLUDED.assignment_method,
                        source_system_code = EXCLUDED.source_system_code,
                        updated_at = now();
                """
                with dwh.cursor() as cur:
                    execute_values(cur, query, chunk)
                loaded += len(chunk)
                
            dwh.commit()
            
        status = "SUCCEEDED" if quarantined == 0 else "FAILED"
        self.stats.append((source_system, entity, read_count, loaded, quarantined, status))
        return read_count, loaded, quarantined
