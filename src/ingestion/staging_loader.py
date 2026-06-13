# -*- coding: utf-8 -*-
"""Staging Loader module.

Extracts data from simulated sources (MySQL HR, MongoDB Fleet, PostgreSQL Dispatch)
and raw file sources (TLC trips & lookup CSVs), applies mappings, generates metadata
(batch_id, row_hash, source_checksum), loads into PostgreSQL Warehouse Staging,
updates audit logs, and performs row-count reconciliation.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pymysql
from pymongo import MongoClient
import psycopg2
from psycopg2.extras import execute_values


REPO_ROOT = Path(__file__).resolve().parents[2]


def calculate_file_checksum(path: Path) -> str:
    """Calculate SHA-256 checksum of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_row_hash(payload: dict[str, Any]) -> str:
    """Generate a deterministic SHA-256 row_hash from business columns."""
    normalized: dict[str, str] = {}
    for k, v in payload.items():
        if v is None:
            normalized[k] = ""
        elif isinstance(v, datetime):
            normalized[k] = v.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(v, date):
            normalized[k] = v.strftime("%Y-%m-%d")
        elif isinstance(v, Decimal):
            normalized[k] = str(v.normalize())
        elif isinstance(v, bool):
            normalized[k] = "true" if v else "false"
        elif isinstance(v, (dict, list)):
            normalized[k] = json.dumps(v, sort_keys=True)
        else:
            normalized[k] = str(v).strip()

    serialized = json.dumps(normalized, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_business_tz() -> ZoneInfo:
    """Load business timezone from env. Default: America/New_York."""
    return ZoneInfo(os.getenv("BUSINESS_TIMEZONE", "America/New_York"))


def convert_mongo_date_to_date(val: Any) -> str:
    """Convert MongoDB datetime (UTC) to business date string in America/New_York."""
    if not val:
        return ""
    if isinstance(val, (int, float)):
        val = datetime.fromtimestamp(val / 1000.0, tz=timezone.utc)
    if val.tzinfo is None:
        val = val.replace(tzinfo=timezone.utc)
    val_ny = val.astimezone(get_business_tz())
    return val_ny.date().isoformat()


def convert_mongo_date_to_timestamp_ny(val: Any) -> datetime:
    """Convert MongoDB datetime (UTC) to naive datetime in America/New_York for DWH."""
    if isinstance(val, (int, float)):
        val = datetime.fromtimestamp(val / 1000.0, tz=timezone.utc)
    if val.tzinfo is None:
        val = val.replace(tzinfo=timezone.utc)
    val_ny = val.astimezone(get_business_tz())
    return val_ny.replace(tzinfo=None)


def to_int(val: Any) -> int | None:
    if val is None or str(val).strip() == "":
        return None
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return None


def to_decimal(val: Any) -> Decimal | None:
    if val is None or str(val).strip() == "":
        return None
    try:
        return Decimal(str(val).strip())
    except (ValueError, TypeError):
        return None


def to_str(val: Any) -> str | None:
    if val is None or str(val).strip() == "":
        return None
    return str(val).strip()


def to_datetime_str(val: Any) -> str | None:
    if not val:
        return None
    val_str = str(val).strip().replace("T", " ")
    if len(val_str) == 10:
        val_str += " 00:00:00"
    return val_str


class StagingLoader:
    """Orchestrates source-to-staging load processes."""

    def __init__(self, release_id: str, batch_id: UUID | None = None) -> None:
        self.release_id = release_id
        self.batch_id = batch_id or uuid4()
        self.pg_conn = None
        self.audit_conn = None
        self.mysql_conn = None
        self.mongo_client = None
        self.dispatch_conn = None
        
        # Reconciliation stats: (source_system, source_entity, extracted_count, loaded_count, status)
        self.stats: list[tuple[str, str, int, int, str]] = []

    def connect_warehouse(self) -> Any:
        """Connect to PostgreSQL Warehouse database for Staging (transactional)."""
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
        """Connect to PostgreSQL Warehouse database for Audit logs (independent transaction)."""
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
        for conn_name in ("mysql_conn", "pg_conn", "audit_conn", "dispatch_conn"):
            conn = getattr(self, conn_name)
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
                setattr(self, conn_name, None)
        if self.mongo_client:
            try:
                self.mongo_client.close()
            except Exception:
                pass
            self.mongo_client = None

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
                    "warehouse_staging",
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

    def write_source_extract_log(
        self,
        source_system: str,
        source_entity: str,
        source_locator: str,
        extract_at: datetime,
        status: str,
        rows_extracted: int,
        rows_loaded: int,
        checksum: str | None = None,
        error_msg: str | None = None
    ) -> None:
        """Log the extraction step in audit.metadata_source_extract."""
        conn = self.connect_audit()
        query = """
            INSERT INTO audit.metadata_source_extract (
                batch_id, release_id, source_system, source_entity,
                source_locator, source_extract_at, extraction_mode,
                source_checksum, rows_extracted, rows_loaded,
                extract_status, error_message
            ) VALUES (
                %s, %s, %s, %s, %s, %s, 'FULL', %s, %s, %s, %s, %s
            )
            ON CONFLICT (batch_id, source_system, source_entity, source_locator, COALESCE(extraction_watermark, ''))
            DO UPDATE SET
                rows_extracted = EXCLUDED.rows_extracted,
                rows_loaded = EXCLUDED.rows_loaded,
                extract_status = EXCLUDED.extract_status,
                error_message = EXCLUDED.error_message
        """
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    str(self.batch_id),
                    self.release_id,
                    source_system,
                    source_entity,
                    source_locator,
                    extract_at,
                    checksum,
                    rows_extracted,
                    rows_loaded,
                    status,
                    error_msg
                )
            )
        conn.commit()

    def write_file_checksum_log(self, source_system: str, source_entity: str, source_file: str, checksum: str, size_bytes: int, row_count: int) -> None:
        """Log file checksum in audit.metadata_file_checksum."""
        conn = self.connect_audit()
        query = """
            INSERT INTO audit.metadata_file_checksum (
                release_id, source_system, source_entity, source_file,
                checksum_algorithm, source_checksum, file_size_bytes,
                row_count, batch_id
            ) VALUES (
                %s, %s, %s, %s, 'SHA256', %s, %s, %s, %s
            )
            ON CONFLICT (release_id, source_system, source_entity, source_file, checksum_algorithm)
            DO UPDATE SET
                source_checksum = EXCLUDED.source_checksum,
                file_size_bytes = EXCLUDED.file_size_bytes,
                row_count = EXCLUDED.row_count,
                batch_id = EXCLUDED.batch_id
        """
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    self.release_id,
                    source_system,
                    source_entity,
                    source_file,
                    checksum,
                    size_bytes,
                    row_count,
                    str(self.batch_id)
                )
            )
        conn.commit()

    def load_hr(self) -> tuple[int, int]:
        """Extract MySQL HR database to PostgreSQL Warehouse staging."""
        self.mysql_conn = pymysql.connect(
            host=os.getenv("MYSQL_HR_HOST", "127.0.0.1"),
            port=int(os.getenv("MYSQL_HR_PORT", "3307")),
            user=os.getenv("MYSQL_HR_USER", "green_taxi_hr_app"),
            password=os.getenv("MYSQL_HR_PASSWORD", "change_me_hr"),
            database=os.getenv("MYSQL_HR_DATABASE", "green_taxi_hr"),
            cursorclass=pymysql.cursors.DictCursor
        )
        
        dwh = self.connect_warehouse()
        source_locator = f"mysql://{self.mysql_conn.host}:{self.mysql_conn.port}/{self.mysql_conn.db}"
        extract_at = datetime.now(timezone.utc)
        
        extracted_total = 0
        loaded_total = 0

        # --- 1. Load Drivers ---
        entity = "drivers"
        try:
            # Idempotency delete
            with dwh.cursor() as cur:
                cur.execute("DELETE FROM staging.stg_hr_drivers WHERE release_id = %s", (self.release_id,))
            
            # Extract
            with self.mysql_conn.cursor() as mysql_cur:
                mysql_cur.execute("SELECT * FROM drivers")
                mysql_rows = mysql_cur.fetchall()
            
            extracted = len(mysql_rows)
            extracted_total += extracted
            
            records = []
            for row in mysql_rows:
                # Build business payload for hashing
                payload = {
                    "driver_id": row["driver_id"],
                    "vendor_id": row["vendor_id"],
                    "driver_code": row["driver_code"],
                    "display_name": row["display_name"],
                    "hire_date": row["hire_date"],
                    "employment_status": row["employment_status"],
                    "license_status": row["license_status"],
                    "license_expiry_date": row["license_expiry_date"],
                    "experience_years": row["experience_years"],
                    "home_borough": row["home_borough"],
                    "source_updated_at": row["source_updated_at"]
                }
                row_hash = make_row_hash(payload)
                
                records.append((
                    str(self.batch_id),
                    self.release_id,
                    "HR_MYSQL",
                    entity,
                    f"{source_locator}/drivers",
                    str(row["driver_id"]),
                    extract_at,
                    row_hash,
                    row["driver_id"],
                    row["vendor_id"],
                    row["driver_code"],
                    row["display_name"],
                    row["hire_date"],
                    row["employment_status"],
                    row["license_status"],
                    row["license_expiry_date"],
                    row["experience_years"],
                    row["home_borough"],
                    row["source_updated_at"]
                ))
            
            # Load
            if records:
                query = """
                    INSERT INTO staging.stg_hr_drivers (
                        batch_id, release_id, source_system, source_entity, source_locator,
                        source_record_id, source_extract_at, row_hash,
                        driver_id, vendor_id, driver_code, display_name, hire_date,
                        employment_status, license_status, license_expiry_date,
                        experience_years, home_borough, source_updated_at
                    ) VALUES %s
                """
                with dwh.cursor() as cur:
                    execute_values(cur, query, records)
            
            loaded = len(records)
            loaded_total += loaded
            status = "SUCCEEDED" if extracted == loaded else "FAILED"
            self.stats.append(("HR_MYSQL", entity, extracted, loaded, status))
            self.write_source_extract_log("HR_MYSQL", entity, f"{source_locator}/drivers", extract_at, status, extracted, loaded)

        except Exception as e:
            dwh.rollback()
            self.stats.append(("HR_MYSQL", entity, 0, 0, "FAILED"))
            self.write_source_extract_log("HR_MYSQL", entity, f"{source_locator}/drivers", extract_at, "FAILED", 0, 0, error_msg=str(e))
            raise e

        # --- 2. Load Driver Changes ---
        entity = "driver_changes"
        try:
            # Idempotency delete
            with dwh.cursor() as cur:
                cur.execute("DELETE FROM staging.stg_hr_driver_changes WHERE release_id = %s", (self.release_id,))
            
            # Extract
            with self.mysql_conn.cursor() as mysql_cur:
                mysql_cur.execute("SELECT * FROM driver_changes")
                mysql_rows = mysql_cur.fetchall()
            
            extracted = len(mysql_rows)
            extracted_total += extracted
            
            records = []
            for row in mysql_rows:
                # Changes is a JSON string in MySQL, we need to parse it to a dictionary
                changes_val = row["changes"]
                if isinstance(changes_val, str):
                    try:
                        changes_val = json.loads(changes_val)
                    except ValueError:
                        pass
                
                payload = {
                    "event_id": row["event_id"],
                    "driver_id": row["driver_id"],
                    "event_type": row["event_type"],
                    "effective_at": row["effective_at"],
                    "delivered_at": row["delivered_at"],
                    "changes": changes_val,
                    "is_late_arriving": bool(row["is_late_arriving"])
                }
                row_hash = make_row_hash(payload)
                
                records.append((
                    str(self.batch_id),
                    self.release_id,
                    "HR_MYSQL",
                    entity,
                    f"{source_locator}/driver_changes",
                    str(row["event_id"]),
                    extract_at,
                    row_hash,
                    row["event_id"],
                    row["driver_id"],
                    row["event_type"],
                    row["effective_at"],
                    row["delivered_at"],
                    json.dumps(changes_val),
                    bool(row["is_late_arriving"])
                ))
            
            # Load
            if records:
                query = """
                    INSERT INTO staging.stg_hr_driver_changes (
                        batch_id, release_id, source_system, source_entity, source_locator,
                        source_record_id, source_extract_at, row_hash,
                        event_id, driver_id, event_type, effective_at, delivered_at,
                        changes, is_late_arriving
                    ) VALUES %s
                """
                with dwh.cursor() as cur:
                    execute_values(cur, query, records)
            
            loaded = len(records)
            loaded_total += loaded
            status = "SUCCEEDED" if extracted == loaded else "FAILED"
            self.stats.append(("HR_MYSQL", entity, extracted, loaded, status))
            self.write_source_extract_log("HR_MYSQL", entity, f"{source_locator}/driver_changes", extract_at, status, extracted, loaded)

        except Exception as e:
            dwh.rollback()
            self.stats.append(("HR_MYSQL", entity, 0, 0, "FAILED"))
            self.write_source_extract_log("HR_MYSQL", entity, f"{source_locator}/driver_changes", extract_at, "FAILED", 0, 0, error_msg=str(e))
            raise e

        # Commit transaction for entire HR source
        dwh.commit()
        return extracted_total, loaded_total

    def load_fleet(self) -> tuple[int, int]:
        """Extract MongoDB Fleet collection to PostgreSQL Warehouse staging."""
        host = os.getenv("MONGODB_FLEET_HOST", "localhost")
        port = int(os.getenv("MONGODB_FLEET_PORT", "27018"))
        user = os.getenv("MONGODB_FLEET_ROOT_USER", "green_taxi_fleet_admin")
        password = os.getenv("MONGODB_FLEET_ROOT_PASSWORD", "change_me_fleet_root")
        connection_string = f"mongodb://{user}:{password}@{host}:{port}/?authSource=admin"
        
        self.mongo_client = MongoClient(connection_string)
        db_name = os.getenv("MONGODB_FLEET_DATABASE", "green_taxi_fleet")
        db = self.mongo_client[db_name]
        vehicles_col = db["vehicles"]
        
        dwh = self.connect_warehouse()
        source_locator = f"mongodb://{host}:{port}/{db_name}"
        extract_at = datetime.now(timezone.utc)
        
        extracted_total = 0
        loaded_total = 0
        entity = "vehicles"
        
        try:
            # Idempotency delete
            with dwh.cursor() as cur:
                cur.execute("DELETE FROM staging.stg_fleet_vehicles WHERE release_id = %s", (self.release_id,))
            
            # Extract count using count_documents
            extracted = vehicles_col.count_documents({})
            extracted_total += extracted
            
            records = []
            # Stream directly using cursor
            for doc in vehicles_col.find({}):
                service_start_date = convert_mongo_date_to_date(doc.get("service_start_date"))
                last_inspection_date = convert_mongo_date_to_date(doc.get("last_inspection_date"))
                source_updated_at = convert_mongo_date_to_timestamp_ny(doc.get("source_updated_at"))
                
                payload = {
                    "vehicle_id": doc["vehicle_id"],
                    "vendor_id": doc["vendor_id"],
                    "plate_token": doc["plate_token"],
                    "model_year": doc["model_year"],
                    "vehicle_type": doc["vehicle_type"],
                    "service_start_date": service_start_date,
                    "vehicle_status": doc["vehicle_status"],
                    "last_inspection_date": last_inspection_date,
                    "source_updated_at": source_updated_at
                }
                row_hash = make_row_hash(payload)
                
                records.append((
                    str(self.batch_id),
                    self.release_id,
                    "FLEET_MONGODB",
                    entity,
                    f"{source_locator}/vehicles",
                    str(doc["vehicle_id"]),
                    extract_at,
                    row_hash,
                    str(doc.get("_id")),
                    doc["vehicle_id"],
                    doc["vendor_id"],
                    doc["plate_token"],
                    doc["model_year"],
                    doc["vehicle_type"],
                    service_start_date,
                    doc["vehicle_status"],
                    last_inspection_date,
                    source_updated_at
                ))
            
            # Load
            if records:
                query = """
                    INSERT INTO staging.stg_fleet_vehicles (
                        batch_id, release_id, source_system, source_entity, source_locator,
                        source_record_id, source_extract_at, row_hash,
                        mongo_document_id, vehicle_id, vendor_id, plate_token,
                        model_year, vehicle_type, service_start_date, vehicle_status,
                        last_inspection_date, source_updated_at
                    ) VALUES %s
                """
                with dwh.cursor() as cur:
                    execute_values(cur, query, records)
                
            loaded = len(records)
            loaded_total += loaded
            status = "SUCCEEDED" if extracted == loaded else "FAILED"
            self.stats.append(("FLEET_MONGODB", entity, extracted, loaded, status))
            self.write_source_extract_log("FLEET_MONGODB", entity, f"{source_locator}/vehicles", extract_at, status, extracted, loaded)

            # Commit transaction for entire Fleet source
            dwh.commit()

        except Exception as e:
            dwh.rollback()
            self.stats.append(("FLEET_MONGODB", entity, 0, 0, "FAILED"))
            self.write_source_extract_log("FLEET_MONGODB", entity, f"{source_locator}/vehicles", extract_at, "FAILED", 0, 0, error_msg=str(e))
            raise e

        return extracted_total, loaded_total

    def load_dispatch(self) -> tuple[int, int]:
        """Extract PostgreSQL Dispatch database to PostgreSQL Warehouse staging."""
        self.dispatch_conn = psycopg2.connect(
            host=os.getenv("POSTGRES_DISPATCH_HOST", "127.0.0.1"),
            port=int(os.getenv("POSTGRES_DISPATCH_PORT", "5433")),
            database=os.getenv("POSTGRES_DISPATCH_DATABASE", "green_taxi_dispatch"),
            user=os.getenv("POSTGRES_DISPATCH_USER", "green_taxi_dispatch_app"),
            password=os.getenv("POSTGRES_DISPATCH_PASSWORD", "change_me_dispatch")
        )
        
        dwh = self.connect_warehouse()
        ds_ds = self.dispatch_conn.get_dsn_parameters()
        source_locator = f"postgresql://{ds_ds.get('host')}:{ds_ds.get('port')}/{ds_ds.get('dbname')}"
        extract_at = datetime.now(timezone.utc)
        
        extracted_total = 0
        loaded_total = 0

        # --- 1. Load Shifts ---
        entity = "shifts"
        try:
            # Idempotency delete
            with dwh.cursor() as cur:
                cur.execute("DELETE FROM staging.stg_dispatch_shifts WHERE release_id = %s", (self.release_id,))
            
            # Extract colnames using dummy query
            with self.dispatch_conn.cursor() as dummy_cur:
                dummy_cur.execute("SELECT * FROM public.shifts LIMIT 0")
                colnames = [desc[0] for desc in dummy_cur.description]
            
            extracted_entity = 0
            loaded_entity = 0
            
            # Stream shifts using server-side cursor
            with self.dispatch_conn.cursor(name="shifts_cursor") as ds_cur:
                ds_cur.execute("SELECT * FROM public.shifts")
                
                chunk = []
                while True:
                    rows = ds_cur.fetchmany(5000)
                    if not rows:
                        break
                    
                    extracted_entity += len(rows)
                    
                    for row_tuple in rows:
                        row = dict(zip(colnames, row_tuple))
                        payload = {
                            "shift_id": row["shift_id"],
                            "driver_id": row["driver_id"],
                            "vehicle_id": row["vehicle_id"],
                            "vendor_id": row["vendor_id"],
                            "shift_start": row["shift_start"],
                            "shift_end": row["shift_end"],
                            "assigned_start_zone": row["assigned_start_zone"],
                            "actual_end_zone": row["actual_end_zone"],
                            "trip_count": row["trip_count"],
                            "occupied_minutes": row["occupied_minutes"],
                            "idle_minutes": row["idle_minutes"],
                            "shift_status": row["shift_status"]
                        }
                        row_hash = make_row_hash(payload)
                        
                        chunk.append((
                            str(self.batch_id),
                            self.release_id,
                            "DISPATCH_POSTGRES",
                            entity,
                            f"{source_locator}/shifts",
                            str(row["shift_id"]),
                            extract_at,
                            row_hash,
                            row["shift_id"],
                            row["driver_id"],
                            row["vehicle_id"],
                            row["vendor_id"],
                            row["shift_start"],
                            row["shift_end"],
                            row["assigned_start_zone"],
                            row["actual_end_zone"],
                            row["trip_count"],
                            row["occupied_minutes"],
                            row["idle_minutes"],
                            row["shift_status"]
                        ))
                    
                    if chunk:
                        query = """
                            INSERT INTO staging.stg_dispatch_shifts (
                                batch_id, release_id, source_system, source_entity, source_locator,
                                source_record_id, source_extract_at, row_hash,
                                shift_id, driver_id, vehicle_id, vendor_id, shift_start, shift_end,
                                assigned_start_zone, actual_end_zone, trip_count, occupied_minutes,
                                idle_minutes, shift_status
                            ) VALUES %s
                        """
                        with dwh.cursor() as cur:
                            execute_values(cur, query, chunk)
                        loaded_entity += len(chunk)
                        chunk.clear()
            
            extracted_total += extracted_entity
            loaded_total += loaded_entity
            status = "SUCCEEDED" if extracted_entity == loaded_entity else "FAILED"
            self.stats.append(("DISPATCH_POSTGRES", entity, extracted_entity, loaded_entity, status))
            self.write_source_extract_log("DISPATCH_POSTGRES", entity, f"{source_locator}/shifts", extract_at, status, extracted_entity, loaded_entity)

        except Exception as e:
            dwh.rollback()
            self.stats.append(("DISPATCH_POSTGRES", entity, 0, 0, "FAILED"))
            self.write_source_extract_log("DISPATCH_POSTGRES", entity, f"{source_locator}/shifts", extract_at, "FAILED", 0, 0, error_msg=str(e))
            raise e

        # --- 2. Load Trip Assignments ---
        entity = "trip_assignments"
        try:
            # Idempotency delete
            with dwh.cursor() as cur:
                cur.execute("DELETE FROM staging.stg_dispatch_trip_assignments WHERE release_id = %s", (self.release_id,))
            
            # Extract
            with self.dispatch_conn.cursor() as dummy_cur:
                dummy_cur.execute("SELECT * FROM public.trip_assignments LIMIT 0")
                colnames = [desc[0] for desc in dummy_cur.description]

            with self.dispatch_conn.cursor(name="trip_assignments_cursor") as ds_cur:
                ds_cur.execute("SELECT * FROM public.trip_assignments")
                
                chunk = []
                extracted_entity = 0
                loaded_entity = 0
                
                while True:
                    rows = ds_cur.fetchmany(5000)
                    if not rows:
                        break
                    
                    extracted_entity += len(rows)
                    
                    for row_tuple in rows:
                        row = dict(zip(colnames, row_tuple))
                        payload = {
                            "trip_key": row["trip_key"],
                            "driver_id": row["driver_id"],
                            "vehicle_id": row["vehicle_id"],
                            "shift_id": row["shift_id"],
                            "assignment_timestamp": row["assignment_timestamp"],
                            "assignment_method": row["assignment_method"]
                        }
                        row_hash = make_row_hash(payload)
                        
                        chunk.append((
                            str(self.batch_id),
                            self.release_id,
                            "DISPATCH_POSTGRES",
                            entity,
                            f"{source_locator}/trip_assignments",
                            str(row["trip_key"]),
                            extract_at,
                            row_hash,
                            row["trip_key"],
                            row["source_file"],
                            row["source_row_number"],
                            row["driver_id"],
                            row["vehicle_id"],
                            row["shift_id"],
                            row["assignment_timestamp"],
                            row["assignment_method"]
                        ))
                    
                    # Bulk insert chunk
                    query = """
                        INSERT INTO staging.stg_dispatch_trip_assignments (
                            batch_id, release_id, source_system, source_entity, source_locator,
                            source_record_id, source_extract_at, row_hash,
                            trip_key, source_file, source_row_number, driver_id, vehicle_id,
                            shift_id, assignment_timestamp, assignment_method
                        ) VALUES %s
                    """
                    with dwh.cursor() as cur:
                        execute_values(cur, query, chunk)
                    
                    loaded_entity += len(chunk)
                    chunk.clear()
            
            extracted_total += extracted_entity
            loaded_total += loaded_entity
            status = "SUCCEEDED" if extracted_entity == loaded_entity else "FAILED"
            self.stats.append(("DISPATCH_POSTGRES", entity, extracted_entity, loaded_entity, status))
            self.write_source_extract_log("DISPATCH_POSTGRES", entity, f"{source_locator}/trip_assignments", extract_at, status, extracted_entity, loaded_entity)

        except Exception as e:
            dwh.rollback()
            self.stats.append(("DISPATCH_POSTGRES", entity, 0, 0, "FAILED"))
            self.write_source_extract_log("DISPATCH_POSTGRES", entity, f"{source_locator}/trip_assignments", extract_at, "FAILED", 0, 0, error_msg=str(e))
            raise e

        # Commit transaction for entire Dispatch source
        dwh.commit()
        return extracted_total, loaded_total

    def load_lookup(self, data_root_path: Path) -> tuple[int, int]:
        """Load lookup files (vendor.csv and taxi_zone.csv) into PostgreSQL Warehouse."""
        dwh = self.connect_warehouse()
        extract_at = datetime.now(timezone.utc)
        
        extracted_total = 0
        loaded_total = 0

        # --- 1. Load Vendor lookup ---
        entity = "vendor"
        try:
            # Idempotency delete
            with dwh.cursor() as cur:
                cur.execute("DELETE FROM staging.stg_lookup_vendor WHERE release_id = %s", (self.release_id,))
            
            vendor_path = data_root_path / "lookup" / "vendor.csv"
            if not vendor_path.exists():
                vendor_path = REPO_ROOT / "data" / "lookup" / "vendor.csv"
                
            if not vendor_path.exists():
                raise FileNotFoundError(f"Missing lookup file vendor.csv at {vendor_path}")
                
            checksum = calculate_file_checksum(vendor_path)
            size_bytes = vendor_path.stat().st_size
            rel_file = vendor_path.relative_to(REPO_ROOT).as_posix() if vendor_path.is_relative_to(REPO_ROOT) else "data/lookup/vendor.csv"
            
            extracted = 0
            records = []
            
            with vendor_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                row_num = 1
                for row in reader:
                    row_num += 1
                    extracted += 1
                    
                    payload = {
                        "vendor_id": to_int(row.get("vendor_id")),
                        "vendor_name": to_str(row.get("vendor_name"))
                    }
                    row_hash = make_row_hash(payload)
                    
                    records.append((
                        str(self.batch_id),
                        self.release_id,
                        "LOOKUP_FILE",
                        entity,
                        f"file://{rel_file}",
                        str(payload["vendor_id"]),
                        rel_file,
                        row_num,
                        extract_at,
                        checksum,
                        row_hash,
                        payload["vendor_id"],
                        payload["vendor_name"]
                    ))
            
            extracted_total += extracted
            
            if records:
                query = """
                    INSERT INTO staging.stg_lookup_vendor (
                        batch_id, release_id, source_system, source_entity, source_locator,
                        source_record_id, source_file, source_row_number, source_extract_at,
                        source_checksum, row_hash, vendor_id, vendor_name
                    ) VALUES %s
                """
                with dwh.cursor() as cur:
                    execute_values(cur, query, records)
                
            loaded = len(records)
            loaded_total += loaded
            status = "SUCCEEDED" if extracted == loaded else "FAILED"
            self.stats.append(("LOOKUP_FILE", entity, extracted, loaded, status))
            self.write_source_extract_log("LOOKUP_FILE", entity, f"file://{rel_file}", extract_at, status, extracted, loaded, checksum=checksum)
            self.write_file_checksum_log("LOOKUP_FILE", entity, rel_file, checksum, size_bytes, extracted)

        except Exception as e:
            dwh.rollback()
            self.stats.append(("LOOKUP_FILE", entity, 0, 0, "FAILED"))
            self.write_source_extract_log("LOOKUP_FILE", entity, "file://lookup/vendor.csv", extract_at, "FAILED", 0, 0, error_msg=str(e))
            raise e

        # --- 2. Load Taxi Zone lookup ---
        entity = "taxi_zone"
        try:
            # Idempotency delete
            with dwh.cursor() as cur:
                cur.execute("DELETE FROM staging.stg_lookup_taxi_zone WHERE release_id = %s", (self.release_id,))
            
            zone_path = data_root_path / "lookup" / "taxi_zone.csv"
            if not zone_path.exists():
                zone_path = REPO_ROOT / "data" / "lookup" / "taxi_zone.csv"
                
            if not zone_path.exists():
                raise FileNotFoundError(f"Missing lookup file taxi_zone.csv at {zone_path}")
                
            checksum = calculate_file_checksum(zone_path)
            size_bytes = zone_path.stat().st_size
            rel_file = zone_path.relative_to(REPO_ROOT).as_posix() if zone_path.is_relative_to(REPO_ROOT) else "data/lookup/taxi_zone.csv"
            
            extracted = 0
            records = []
            
            with zone_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                row_num = 1
                for row in reader:
                    row_num += 1
                    extracted += 1
                    
                    payload = {
                        "location_id": to_int(row.get("LocationID")),
                        "borough": to_str(row.get("Borough")),
                        "zone": to_str(row.get("Zone")),
                        "service_zone": to_str(row.get("service_zone"))
                    }
                    row_hash = make_row_hash(payload)
                    
                    records.append((
                        str(self.batch_id),
                        self.release_id,
                        "LOOKUP_FILE",
                        entity,
                        f"file://{rel_file}",
                        str(payload["location_id"]),
                        rel_file,
                        row_num,
                        extract_at,
                        checksum,
                        row_hash,
                        payload["location_id"],
                        payload["borough"],
                        payload["zone"],
                        payload["service_zone"]
                    ))
            
            extracted_total += extracted
            
            if records:
                query = """
                    INSERT INTO staging.stg_lookup_taxi_zone (
                        batch_id, release_id, source_system, source_entity, source_locator,
                        source_record_id, source_file, source_row_number, source_extract_at,
                        source_checksum, row_hash, location_id, borough, zone, service_zone
                    ) VALUES %s
                """
                with dwh.cursor() as cur:
                    execute_values(cur, query, records)
                
            loaded = len(records)
            loaded_total += loaded
            status = "SUCCEEDED" if extracted == loaded else "FAILED"
            self.stats.append(("LOOKUP_FILE", entity, extracted, loaded, status))
            self.write_source_extract_log("LOOKUP_FILE", entity, f"file://{rel_file}", extract_at, status, extracted, loaded, checksum=checksum)
            self.write_file_checksum_log("LOOKUP_FILE", entity, rel_file, checksum, size_bytes, extracted)

        except Exception as e:
            dwh.rollback()
            self.stats.append(("LOOKUP_FILE", entity, 0, 0, "FAILED"))
            self.write_source_extract_log("LOOKUP_FILE", entity, "file://lookup/taxi_zone.csv", extract_at, "FAILED", 0, 0, error_msg=str(e))
            raise e

        # Commit transaction for entire Lookup source
        dwh.commit()
        return extracted_total, loaded_total

    def load_tlc(self, data_root_path: Path, limit_files: int | None = None, limit_rows: int | None = None) -> tuple[int, int]:
        """Scan and load TLC Green Taxi trips CSV files to PostgreSQL Warehouse staging."""
        dwh = self.connect_warehouse()
        extract_at = datetime.now(timezone.utc)
        
        extracted_total = 0
        loaded_total = 0
        entity = "tlc_green_tripdata"
        
        tlc_dir = data_root_path / "raw" / "tlc"
        if not tlc_dir.exists():
            tlc_dir = REPO_ROOT / "data" / "raw" / "tlc"
            
        csv_files = sorted(list(tlc_dir.glob("year=*/month=*/*.csv"))) if tlc_dir.exists() else []
        if not tlc_dir.exists() or not csv_files:
            # Log SKIPPED state for TLC when files or directory is missing
            self.stats.append(("TLC_FILE", entity, 0, 0, "SKIPPED"))
            self.write_source_extract_log(
                "TLC_FILE",
                entity,
                "file://raw/tlc",
                extract_at,
                "SKIPPED",
                0,
                0,
                checksum="SKIPPED"
            )
            print(f"[!] Warning: TLC raw directory or CSV files not found. Skipped TLC load.", file=sys.stderr)
            return 0, 0
            
        if limit_files is not None:
            csv_files = csv_files[:limit_files]
            print(f"[*] Limiting TLC import to {limit_files} files for testing.")

        for file_path in csv_files:
            rel_file = file_path.relative_to(REPO_ROOT).as_posix() if file_path.is_relative_to(REPO_ROOT) else f"data/raw/tlc/{file_path.name}"
            print(f"[*] Processing TLC file: {rel_file}")
            
            try:
                checksum = calculate_file_checksum(file_path)
                size_bytes = file_path.stat().st_size
                
                # Idempotency delete for this file
                with dwh.cursor() as cur:
                    cur.execute(
                        "DELETE FROM staging.stg_tlc_green_trips WHERE release_id = %s AND source_file = %s",
                        (self.release_id, rel_file)
                    )
                
                extracted_file = 0
                loaded_file = 0
                
                with file_path.open("r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    row_num = 1
                    chunk = []
                    
                    for row in reader:
                        row_num += 1
                        extracted_file += 1
                        
                        payload = {
                            "vendor_id": to_int(row.get("VendorID")),
                            "lpep_pickup_datetime": to_datetime_str(row.get("lpep_pickup_datetime")),
                            "lpep_dropoff_datetime": to_datetime_str(row.get("lpep_dropoff_datetime")),
                            "store_and_fwd_flag": to_str(row.get("store_and_fwd_flag")),
                            "ratecode_id": to_int(row.get("RatecodeID")),
                            "pu_location_id": to_int(row.get("PULocationID")),
                            "do_location_id": to_int(row.get("DOLocationID")),
                            "passenger_count": to_int(row.get("passenger_count")),
                            "trip_distance": to_decimal(row.get("trip_distance")),
                            "fare_amount": to_decimal(row.get("fare_amount")),
                            "extra": to_decimal(row.get("extra")),
                            "mta_tax": to_decimal(row.get("mta_tax")),
                            "tip_amount": to_decimal(row.get("tip_amount")),
                            "tolls_amount": to_decimal(row.get("tolls_amount")),
                            "ehail_fee": to_decimal(row.get("ehail_fee")),
                            "improvement_surcharge": to_decimal(row.get("improvement_surcharge")),
                            "total_amount": to_decimal(row.get("total_amount")),
                            "payment_type": to_int(row.get("payment_type")),
                            "trip_type": to_int(row.get("trip_type")),
                            "congestion_surcharge": to_decimal(row.get("congestion_surcharge"))
                        }
                        row_hash = make_row_hash(payload)
                        
                        chunk.append((
                            str(self.batch_id),
                            self.release_id,
                            "TLC_FILE",
                            entity,
                            f"file://{rel_file}",
                            f"{rel_file}:{row_num}",
                            rel_file,
                            row_num,
                            extract_at,
                            checksum,
                            row_hash,
                            payload["vendor_id"],
                            payload["lpep_pickup_datetime"],
                            payload["lpep_dropoff_datetime"],
                            payload["store_and_fwd_flag"],
                            payload["ratecode_id"],
                            payload["pu_location_id"],
                            payload["do_location_id"],
                            payload["passenger_count"],
                            payload["trip_distance"],
                            payload["fare_amount"],
                            payload["extra"],
                            payload["mta_tax"],
                            payload["tip_amount"],
                            payload["tolls_amount"],
                            payload["ehail_fee"],
                            payload["improvement_surcharge"],
                            payload["total_amount"],
                            payload["payment_type"],
                            payload["trip_type"],
                            payload["congestion_surcharge"]
                        ))
                        
                        if len(chunk) >= 5000:
                            self._insert_tlc_chunk(dwh, chunk)
                            loaded_file += len(chunk)
                            chunk.clear()
                            
                        if limit_rows is not None and extracted_file >= limit_rows:
                            break
                    
                    if chunk:
                        self._insert_tlc_chunk(dwh, chunk)
                        loaded_file += len(chunk)
                        chunk.clear()
                        
                extracted_total += extracted_file
                loaded_total += loaded_file
                
                status = "SUCCEEDED" if extracted_file == loaded_file else "FAILED"
                self.stats.append(("TLC_FILE", f"{entity} ({file_path.name})", extracted_file, loaded_file, status))
                
                self.write_source_extract_log("TLC_FILE", f"{entity}#{file_path.name}", f"file://{rel_file}", extract_at, status, extracted_file, loaded_file, checksum=checksum)
                self.write_file_checksum_log("TLC_FILE", entity, rel_file, checksum, size_bytes, extracted_file)
                
                # Commit at file level after successful file ingestion
                dwh.commit()

            except Exception as e:
                dwh.rollback()
                self.stats.append(("TLC_FILE", f"{entity} ({file_path.name})", 0, 0, "FAILED"))
                self.write_source_extract_log("TLC_FILE", f"{entity}#{file_path.name}", f"file://{rel_file}", extract_at, "FAILED", 0, 0, error_msg=str(e))
                raise e
                
        return extracted_total, loaded_total

    def _insert_tlc_chunk(self, dwh: Any, chunk: list[tuple]) -> None:
        """Insert a chunk of TLC records into stg_tlc_green_trips."""
        query = """
            INSERT INTO staging.stg_tlc_green_trips (
                batch_id, release_id, source_system, source_entity, source_locator,
                source_record_id, source_file, source_row_number, source_extract_at,
                source_checksum, row_hash,
                vendor_id, lpep_pickup_datetime, lpep_dropoff_datetime, store_and_fwd_flag,
                ratecode_id, pu_location_id, do_location_id, passenger_count, trip_distance,
                fare_amount, extra, mta_tax, tip_amount, tolls_amount, ehail_fee,
                improvement_surcharge, total_amount, payment_type, trip_type, congestion_surcharge
            ) VALUES %s
        """
        with dwh.cursor() as cur:
            execute_values(cur, query, chunk)
