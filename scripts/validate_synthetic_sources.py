#!/usr/bin/env python3
"""Validate referential and temporal integrity of generated synthetic sources."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default="data/raw/synthetic",
        help="Synthetic root relative to repository root.",
    )
    parser.add_argument(
        "--report",
        default="data/metadata/synthetic_validation_report.json",
    )
    parser.add_argument(
        "--config",
        default="configs/synthetic_generation.json",
    )
    return parser.parse_args()


def read_jsonl_ids(path: Path, field: str) -> set[str]:
    result: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                result.add(json.loads(line)[field])
    return result


def compute_trip_key(source_file: str, row_number: int, row: dict[str, str]) -> str:
    payload = "|".join(
        [
            source_file,
            str(row_number),
            row.get("lpep_pickup_datetime", ""),
            row.get("lpep_dropoff_datetime", ""),
            row.get("PULocationID", ""),
            row.get("DOLocationID", ""),
            row.get("total_amount", ""),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def validate(
    repo_root: Path,
    synthetic_root: Path,
    report_path: Path,
    config_path: Path,
) -> int:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    trip_root = (repo_root / config["source_trip_root"]).resolve()
    issues = Counter()
    with (repo_root / "data" / "lookup" / "vendor.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        vendor_lookup_ids = {
            int(row["vendor_id"])
            for row in csv.DictReader(handle)
        }
    if 0 not in vendor_lookup_ids:
        issues["missing_legacy_vendor_lookup"] += 1

    drivers: set[str] = set()
    driver_vendor: dict[str, int] = {}
    with (synthetic_root / "driver_hr" / "drivers.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        for row in csv.DictReader(handle):
            drivers.add(row["driver_id"])
            vendor_id = int(row["vendor_id"])
            driver_vendor[row["driver_id"]] = vendor_id
            if vendor_id not in vendor_lookup_ids:
                issues["driver_vendor_missing_lookup"] += 1

    vehicles = read_jsonl_ids(synthetic_root / "fleet" / "vehicles.jsonl", "vehicle_id")
    vehicle_vendor: dict[str, int] = {}
    with (synthetic_root / "fleet" / "vehicles.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            vendor_id = int(record["vendor_id"])
            vehicle_vendor[record["vehicle_id"]] = vendor_id
            if vendor_id not in vendor_lookup_ids:
                issues["vehicle_vendor_missing_lookup"] += 1
            service_start = date.fromisoformat(record["service_start_date"])
            inspection_date = date.fromisoformat(record["last_inspection_date"])
            if inspection_date < service_start:
                issues["inspection_before_service_start"] += 1

    shifts: dict[str, dict[str, object]] = {}
    shifts_by_driver: dict[str, list[tuple[datetime, datetime]]] = {}
    shifts_by_vehicle: dict[str, list[tuple[datetime, datetime]]] = {}
    with (synthetic_root / "dispatch" / "shifts.tsv").open(
        encoding="utf-8", newline=""
    ) as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row["shift_id"] in shifts:
                issues["duplicate_shift_id"] += 1
            start = datetime.fromisoformat(row["shift_start"])
            end = datetime.fromisoformat(row["shift_end"])
            if end < start:
                issues["negative_shift"] += 1
            occupied_minutes = float(row["occupied_minutes"])
            idle_minutes = float(row["idle_minutes"])
            shift_minutes = (end - start).total_seconds() / 60
            if abs((occupied_minutes + idle_minutes) - shift_minutes) > 0.02:
                issues["shift_time_balance_mismatch"] += 1
            if row["driver_id"] not in drivers:
                issues["shift_missing_driver"] += 1
            if row["vehicle_id"] not in vehicles:
                issues["shift_missing_vehicle"] += 1
            vendor = int(row["vendor_id"])
            if vendor not in vendor_lookup_ids:
                issues["shift_vendor_missing_lookup"] += 1
            if driver_vendor.get(row["driver_id"]) != vendor:
                issues["shift_driver_vendor_mismatch"] += 1
            if vehicle_vendor.get(row["vehicle_id"]) != vendor:
                issues["shift_vehicle_vendor_mismatch"] += 1
            shifts_by_driver.setdefault(row["driver_id"], []).append((start, end))
            shifts_by_vehicle.setdefault(row["vehicle_id"], []).append((start, end))
            shifts[row["shift_id"]] = {
                "driver_id": row["driver_id"],
                "vehicle_id": row["vehicle_id"],
                "vendor_id": vendor,
                "start": start,
                "end": end,
                "declared_trip_count": int(row["trip_count"]),
                "observed_trip_count": 0,
            }

    for intervals in shifts_by_driver.values():
        intervals.sort()
        latest_end = datetime.min
        for start, end in intervals:
            if start < latest_end:
                issues["driver_shift_overlap"] += 1
            latest_end = max(latest_end, end)
    for intervals in shifts_by_vehicle.values():
        intervals.sort()
        latest_end = datetime.min
        for start, end in intervals:
            if start < latest_end:
                issues["vehicle_shift_overlap"] += 1
            latest_end = max(latest_end, end)

    seen_trip_keys: set[str] = set()
    assignment_count = 0
    last_driver_dropoff: dict[str, datetime] = {}
    last_vehicle_dropoff: dict[str, datetime] = {}
    for assignment_file in sorted(
        (synthetic_root / "trip_assignment").rglob("trip_assignment_*.csv")
    ):
        assignments_by_source: dict[str, dict[int, dict[str, str]]] = {}
        with assignment_file.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                assignment_count += 1
                key = row["trip_key"]
                if key in seen_trip_keys:
                    issues["duplicate_trip_key"] += 1
                seen_trip_keys.add(key)
                if row["driver_id"] not in drivers:
                    issues["assignment_missing_driver"] += 1
                if row["vehicle_id"] not in vehicles:
                    issues["assignment_missing_vehicle"] += 1
                shift = shifts.get(row["shift_id"])
                if shift is None:
                    issues["assignment_missing_shift"] += 1
                    continue
                if shift["driver_id"] != row["driver_id"]:
                    issues["assignment_driver_shift_mismatch"] += 1
                if shift["vehicle_id"] != row["vehicle_id"]:
                    issues["assignment_vehicle_shift_mismatch"] += 1
                shift["observed_trip_count"] = int(shift["observed_trip_count"]) + 1
                source_file = row["source_file"]
                assignments_by_source.setdefault(source_file, {})[
                    int(row["source_row_number"])
                ] = row

        for source_file, source_assignments in assignments_by_source.items():
            source_path = trip_root / Path(source_file)
            if not source_path.exists():
                issues["missing_source_file"] += 1
                continue
            temporal_rows: list[tuple[datetime, datetime, dict[str, str]]] = []
            with source_path.open(encoding="utf-8-sig", newline="") as handle:
                for source_row_number, trip in enumerate(
                    csv.DictReader(handle), start=2
                ):
                    assignment = source_assignments.get(source_row_number)
                    if assignment is None:
                        continue
                    if assignment["trip_key"] != compute_trip_key(
                        source_file, source_row_number, trip
                    ):
                        issues["trip_key_mismatch"] += 1
                    try:
                        pickup = datetime.fromisoformat(
                            trip["lpep_pickup_datetime"]
                        )
                        dropoff = datetime.fromisoformat(
                            trip["lpep_dropoff_datetime"]
                        )
                    except ValueError:
                        issues["assigned_invalid_datetime"] += 1
                        continue
                    temporal_rows.append((pickup, dropoff, assignment))

            temporal_rows.sort(key=lambda item: item[0])
            for pickup, dropoff, assignment in temporal_rows:
                shift = shifts[assignment["shift_id"]]
                if pickup < shift["start"] or dropoff > shift["end"]:
                    issues["trip_outside_shift"] += 1
                driver_id = assignment["driver_id"]
                vehicle_id = assignment["vehicle_id"]
                if last_driver_dropoff.get(driver_id, datetime.min) > pickup:
                    issues["driver_trip_overlap"] += 1
                if last_vehicle_dropoff.get(vehicle_id, datetime.min) > pickup:
                    issues["vehicle_trip_overlap"] += 1
                last_driver_dropoff[driver_id] = dropoff
                last_vehicle_dropoff[vehicle_id] = dropoff

    for shift in shifts.values():
        if shift["declared_trip_count"] != shift["observed_trip_count"]:
            issues["shift_trip_count_mismatch"] += 1

    report = {
        "validated_at": datetime.now().isoformat(timespec="seconds"),
        "driver_count": len(drivers),
        "vehicle_count": len(vehicles),
        "shift_count": len(shifts),
        "assignment_count": assignment_count,
        "issues": dict(sorted(issues.items())),
        "passed": sum(issues.values()) == 0,
        "notes": [
            "Assignments were checked against the original TLC source rows.",
            "Driver and vehicle trip/shift overlap were validated across all months.",
            "Shift occupied and idle minutes were reconciled to shift duration.",
            "Vehicle inspection dates were checked against service start dates.",
            "Driver, vehicle and shift vendors were checked against vendor lookup.",
            "Source-period and invalid-duration exceptions are stored separately.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    args = parse_args()
    repo = Path.cwd().resolve()
    raise SystemExit(
        validate(
            repo,
            (repo / args.root).resolve(),
            (repo / args.report).resolve(),
            (repo / args.config).resolve(),
        )
    )
