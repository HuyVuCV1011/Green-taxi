"""Warehouse reconciliation and database-backed DQ fixture validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from src.warehouse.dds_loader import DDSLoader
from src.warehouse.nds_loader import NDSLoader


@dataclass(frozen=True)
class ValidationResult:
    name: str
    actual: Any
    expected: Any

    @property
    def passed(self) -> bool:
        return self.actual == self.expected


def _scalar(conn: Any, query: str, params: tuple[Any, ...] = ()) -> Any:
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchone()[0]


def validate_release_reconciliation(conn: Any, release_id: str) -> list[ValidationResult]:
    """Validate source lineage, layer counts, measures, grain, and SCD2 state."""
    results: list[ValidationResult] = []

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT row_count_expected, row_count_loaded
            FROM audit.metadata_etl_batch
            WHERE release_id = %s
              AND pipeline_name = 'warehouse_staging'
              AND batch_status = 'SUCCEEDED'
            ORDER BY batch_completed_at DESC
            LIMIT 1
            """,
            (release_id,),
        )
        staging_audit = cur.fetchone()

    expected_staging_audit = (
        (staging_audit[0], staging_audit[0])
        if staging_audit
        else ("audit row present", "expected equals loaded")
    )
    results.append(
        ValidationResult(
            "source_to_staging_audit",
            staging_audit,
            expected_staging_audit,
        )
    )

    staging_assignments = _scalar(
        conn,
        "SELECT COUNT(*) FROM staging.stg_dispatch_trip_assignments WHERE release_id = %s",
        (release_id,),
    )
    nds_trips = _scalar(conn, "SELECT COUNT(*) FROM nds.nds_trip")
    nds_assignments = _scalar(conn, "SELECT COUNT(*) FROM nds.nds_trip_assignment")
    dds_trips = _scalar(conn, "SELECT COUNT(*) FROM dds.fact_driver_trip")
    nds_completed_shifts = _scalar(
        conn, "SELECT COUNT(*) FROM nds.nds_shift WHERE shift_status = 'COMPLETED'"
    )
    dds_shifts = _scalar(conn, "SELECT COUNT(*) FROM dds.fact_driver_shift")

    results.extend(
        (
            ValidationResult("staging_assignments_to_nds_trips", nds_trips, staging_assignments),
            ValidationResult("staging_assignments_to_nds_assignments", nds_assignments, staging_assignments),
            ValidationResult("nds_trips_to_dds_trips", dds_trips, nds_trips),
            ValidationResult("completed_nds_shifts_to_dds_shifts", dds_shifts, nds_completed_shifts),
        )
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COALESCE(SUM(total_amount), 0),
                COALESCE(SUM(trip_distance), 0),
                COALESCE(SUM(ROUND(
                    (EXTRACT(EPOCH FROM (dropoff_datetime - pickup_datetime)) / 60)::numeric,
                    2
                )), 0)
            FROM nds.nds_trip
            """
        )
        nds_revenue, nds_distance, nds_duration = cur.fetchone()
        cur.execute(
            """
            SELECT
                COALESCE(SUM(total_amount), 0),
                COALESCE(SUM(trip_distance), 0),
                COALESCE(SUM(trip_duration_minutes), 0)
            FROM dds.fact_driver_trip
            """
        )
        dds_revenue, dds_distance, dds_duration = cur.fetchone()

    results.extend(
        (
            ValidationResult("trip_revenue", dds_revenue, nds_revenue),
            ValidationResult("trip_distance", dds_distance, nds_distance),
            ValidationResult("trip_duration_rounded_per_row", dds_duration, nds_duration),
            ValidationResult(
                "duplicate_nds_trip_nk",
                _scalar(conn, "SELECT COUNT(*) - COUNT(DISTINCT trip_nk) FROM nds.nds_trip"),
                0,
            ),
            ValidationResult(
                "duplicate_dds_trip_id",
                _scalar(conn, "SELECT COUNT(*) - COUNT(DISTINCT trip_id) FROM dds.fact_driver_trip"),
                0,
            ),
            ValidationResult(
                "duplicate_dds_shift_id",
                _scalar(conn, "SELECT COUNT(*) - COUNT(DISTINCT shift_id) FROM dds.fact_driver_shift"),
                0,
            ),
            ValidationResult(
                "driver_multiple_current",
                _scalar(
                    conn,
                    """
                    SELECT COUNT(*) FROM (
                        SELECT driver_id
                        FROM dds.dim_driver
                        WHERE is_current
                        GROUP BY driver_id
                        HAVING COUNT(*) > 1
                    ) duplicated
                    """,
                ),
                0,
            ),
            ValidationResult(
                "vehicle_multiple_current",
                _scalar(
                    conn,
                    """
                    SELECT COUNT(*) FROM (
                        SELECT vehicle_id
                        FROM dds.dim_vehicle
                        WHERE is_current
                        GROUP BY vehicle_id
                        HAVING COUNT(*) > 1
                    ) duplicated
                    """,
                ),
                0,
            ),
            ValidationResult(
                "invalid_shift_minutes",
                _scalar(
                    conn,
                    """
                    SELECT COUNT(*)
                    FROM dds.fact_driver_shift
                    WHERE occupied_minutes < 0
                       OR idle_minutes < 0
                       OR occupied_minutes + idle_minutes <> shift_duration_minutes
                    """,
                ),
                0,
            ),
        )
    )
    return results


def _seed_fixture_staging(conn: Any, release_id: str, batch_id: str) -> None:
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO nds.nds_vendor (vendor_nk, vendor_name, source_system_code)
            VALUES
                (0, 'Legacy Pool', 'LOOKUP_FILE'),
                (1, 'Fixture Vendor', 'LOOKUP_FILE')
            ON CONFLICT (vendor_nk) DO NOTHING
            """
        )
        cur.execute(
            """
            INSERT INTO nds.nds_location (
                location_nk, borough, zone, service_zone, source_system_code
            ) VALUES
                (1, 'Fixture', 'Zone 1', 'Boro Zone', 'LOOKUP_FILE'),
                (2, 'Fixture', 'Zone 2', 'Boro Zone', 'LOOKUP_FILE')
            ON CONFLICT (location_nk) DO NOTHING
            """
        )
        cur.execute(
            """
            INSERT INTO staging.stg_hr_drivers (
                batch_id, release_id, source_system, source_entity, source_locator,
                source_record_id, source_extract_at, row_hash, driver_id, vendor_id,
                driver_code, display_name, hire_date, employment_status,
                license_status, license_expiry_date, experience_years,
                home_borough, source_updated_at
            ) VALUES (
                %s, %s, 'HR_MYSQL', 'drivers', 'fixture://hr',
                'DRV900001', %s, 'fixture-invalid-enum', 'DRV900001', 1,
                'D900001', 'Invalid Enum Driver', %s, 'BROKEN_STATUS',
                'ACTIVE', %s, 1, 'Fixture', %s
            )
            """,
            (batch_id, release_id, now, date(2020, 1, 1), date(2030, 1, 1), now.replace(tzinfo=None)),
        )
        shifts = (
            ("SHF9000000001", datetime(2020, 1, 1, 8), datetime(2020, 1, 1, 10)),
            ("SHF9000000002", datetime(2020, 1, 1, 9), datetime(2020, 1, 1, 11)),
        )
        for shift_id, shift_start, shift_end in shifts:
            cur.execute(
                """
                INSERT INTO staging.stg_dispatch_shifts (
                    batch_id, release_id, source_system, source_entity, source_locator,
                    source_record_id, source_extract_at, row_hash, shift_id, driver_id,
                    vehicle_id, vendor_id, shift_start, shift_end, assigned_start_zone,
                    actual_end_zone, trip_count, occupied_minutes, idle_minutes, shift_status
                ) VALUES (
                    %s, %s, 'DISPATCH_POSTGRES', 'shifts', 'fixture://dispatch',
                    %s, %s, %s, %s, 'DRV900002', 'VEH900002', 1,
                    %s, %s, 1, 2, 1, 30, 90, 'COMPLETED'
                )
                """,
                (
                    batch_id, release_id, shift_id, now, f"hash-{shift_id}",
                    shift_id, shift_start, shift_end,
                ),
            )
        cur.execute(
            """
            INSERT INTO staging.stg_dispatch_trip_assignments (
                batch_id, release_id, source_system, source_entity, source_locator,
                source_record_id, source_extract_at, row_hash, trip_key, source_file,
                source_row_number, driver_id, vehicle_id, shift_id,
                assignment_timestamp, assignment_method
            ) VALUES (
                %s, %s, 'DISPATCH_POSTGRES', 'trip_assignments', 'fixture://dispatch',
                'fixture-trip-key-preserved', %s, 'fixture-assignment',
                'fixture-trip-key-preserved', 'fixture.csv', 2,
                'DRV900002', 'VEH900002', 'SHF9000000001',
                %s, 'CONTINUITY'
            )
            """,
            (batch_id, release_id, now, datetime(2020, 1, 1, 6, 50)),
        )
        cur.execute(
            """
            INSERT INTO staging.stg_tlc_green_trips (
                batch_id, release_id, source_system, source_entity, source_locator,
                source_record_id, source_file, source_row_number, source_extract_at,
                source_checksum, row_hash, vendor_id, lpep_pickup_datetime,
                lpep_dropoff_datetime, store_and_fwd_flag, ratecode_id,
                pu_location_id, do_location_id, passenger_count, trip_distance,
                fare_amount, extra, mta_tax, tip_amount, tolls_amount, ehail_fee,
                improvement_surcharge, total_amount, payment_type, trip_type,
                congestion_surcharge
            ) VALUES (
                %s, %s, 'TLC_FILE', 'tlc_green_tripdata', 'fixture://tlc',
                'fixture.csv:2', 'fixture.csv', 2, %s, 'fixture-checksum',
                'fixture-trip-row', 1, %s, %s, 'N', 1, 1, 2, 1,
                -1.000, -5.00, 0, 0.50, 0, 0, 0, 0.30, -4.20, 1, 1, 0
            )
            """,
            (
                batch_id, release_id, now,
                datetime(2020, 1, 1, 7), datetime(2020, 1, 1, 7, 30),
            ),
        )
    conn.commit()


def _run_fixture_pipeline(release_id: str) -> dict[str, int]:
    nds = NDSLoader(release_id, uuid4())
    nds.start_batch_log(input_params={"validation_fixture": True})
    if _scalar(
        nds.connect_warehouse(),
        "SELECT COUNT(*) FROM staging.stg_hr_drivers WHERE release_id = %s",
        (release_id,),
    ) == 0:
        _seed_fixture_staging(nds.connect_warehouse(), release_id, str(nds.batch_id))
    nds.load_drivers()
    nds.load_shifts()
    nds.load_trips()
    nds.load_trip_assignments()
    nds.complete_batch_log("SUCCEEDED")
    nds.close_all()

    dds = DDSLoader(release_id, uuid4())
    dds.start_batch_log(input_params={"validation_fixture": True})
    dds.load_dim_date()
    dds.load_dim_time()
    dds.load_dim_vendor()
    dds.load_dim_location()
    _, driver_versions, _ = dds.load_dim_driver()
    _, vehicle_versions, _ = dds.load_dim_vehicle()
    dq_results = dds.run_dq_gate2()
    dds.load_fact_driver_trip()
    dds.load_fact_driver_shift()
    dds.complete_batch_log("SUCCEEDED")
    dds.close_all()
    return {
        "driver_versions": driver_versions,
        "vehicle_versions": vehicle_versions,
        **dq_results,
    }


def validate_dq_fixture(conn: Any, release_id: str = "dq-validation-v1") -> list[ValidationResult]:
    """Run the same fixture twice and validate DQ behavior plus idempotency."""
    first = _run_fixture_pipeline(release_id)
    before = {
        "drivers": _scalar(conn, "SELECT COUNT(*) FROM nds.nds_driver"),
        "vehicles": _scalar(conn, "SELECT COUNT(*) FROM nds.nds_vehicle"),
        "trips": _scalar(conn, "SELECT COUNT(*) FROM nds.nds_trip"),
        "shifts": _scalar(conn, "SELECT COUNT(*) FROM nds.nds_shift"),
        "driver_versions": _scalar(conn, "SELECT COUNT(*) FROM dds.dim_driver"),
        "vehicle_versions": _scalar(conn, "SELECT COUNT(*) FROM dds.dim_vehicle"),
        "trip_facts": _scalar(conn, "SELECT COUNT(*) FROM dds.fact_driver_trip"),
        "shift_facts": _scalar(conn, "SELECT COUNT(*) FROM dds.fact_driver_shift"),
        "issues": _scalar(conn, "SELECT COUNT(*) FROM dq.dq_issue"),
        "quarantine": _scalar(conn, "SELECT COUNT(*) FROM dq.quarantine_record"),
    }
    second = _run_fixture_pipeline(release_id)
    after = {
        key: _scalar(conn, query)
        for key, query in {
            "drivers": "SELECT COUNT(*) FROM nds.nds_driver",
            "vehicles": "SELECT COUNT(*) FROM nds.nds_vehicle",
            "trips": "SELECT COUNT(*) FROM nds.nds_trip",
            "shifts": "SELECT COUNT(*) FROM nds.nds_shift",
            "driver_versions": "SELECT COUNT(*) FROM dds.dim_driver",
            "vehicle_versions": "SELECT COUNT(*) FROM dds.dim_vehicle",
            "trip_facts": "SELECT COUNT(*) FROM dds.fact_driver_trip",
            "shift_facts": "SELECT COUNT(*) FROM dds.fact_driver_shift",
            "issues": "SELECT COUNT(*) FROM dq.dq_issue",
            "quarantine": "SELECT COUNT(*) FROM dq.quarantine_record",
        }.items()
    }

    issue_quarantine_match = _scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM dq.dq_issue i
        JOIN dq.quarantine_record q
          ON q.release_id = i.release_id
         AND q.source_system_code = i.source_system_code
         AND q.source_entity = i.source_entity
         AND q.source_record_id = i.source_record_id
         AND q.error_rule_code = i.rule_code
        WHERE i.release_id = %s AND i.severity = 'ERROR'
        """,
        (release_id,),
    )
    error_issues = _scalar(
        conn,
        "SELECT COUNT(*) FROM dq.dq_issue WHERE release_id = %s AND severity = 'ERROR'",
        (release_id,),
    )

    results = [
        ValidationResult(
            "error_invalid_enum_not_loaded",
            _scalar(conn, "SELECT COUNT(*) FROM nds.nds_driver WHERE driver_nk = 'DRV900001'"),
            0,
        ),
        ValidationResult("error_issue_matches_quarantine", issue_quarantine_match, error_issues),
        ValidationResult(
            "warn_negative_trip_loaded",
            _scalar(conn, "SELECT COUNT(*) FROM nds.nds_trip WHERE trip_nk = 'fixture-trip-key-preserved'"),
            1,
        ),
        ValidationResult(
            "warn_negative_issue_exists",
            _scalar(
                conn,
                """
                SELECT COUNT(*) FROM dq.dq_issue
                WHERE release_id = %s AND rule_code = 'DQ_NEGATIVE_VAL' AND severity = 'WARN'
                """,
                (release_id,),
            ),
            1,
        ),
        ValidationResult(
            "inferred_driver_created",
            _scalar(conn, "SELECT COUNT(*) FROM nds.nds_driver WHERE driver_nk = 'DRV900002' AND is_inferred"),
            1,
        ),
        ValidationResult(
            "inferred_vehicle_created",
            _scalar(conn, "SELECT COUNT(*) FROM nds.nds_vehicle WHERE vehicle_nk = 'VEH900002' AND is_inferred"),
            1,
        ),
        ValidationResult("driver_overlap_detected", first["driver_shift_overlap"], 1),
        ValidationResult("vehicle_overlap_detected", first["vehicle_shift_overlap"], 1),
        ValidationResult("trip_outside_shift_detected", first["trip_outside_shift"], 1),
        ValidationResult("rerun_driver_scd_versions", second["driver_versions"], 0),
        ValidationResult("rerun_vehicle_scd_versions", second["vehicle_versions"], 0),
    ]
    results.extend(
        ValidationResult(f"rerun_stable_{key}", after[key], value)
        for key, value in before.items()
    )
    return results


def assert_results(results: list[ValidationResult]) -> None:
    failed = [result for result in results if not result.passed]
    if failed:
        details = "; ".join(
            f"{item.name}: actual={item.actual!r}, expected={item.expected!r}"
            for item in failed
        )
        raise AssertionError(details)
