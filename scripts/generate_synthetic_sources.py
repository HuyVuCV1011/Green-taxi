#!/usr/bin/env python3
"""Generate deterministic synthetic Driver Operations source systems.

The TLC trip rows remain the authoritative trip source. This script creates
separate HR, fleet, dispatch, assignment, and HR-change feeds around them.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import heapq
import json
import random
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


BOROUGHS = ["Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island"]
FIRST_NAMES = [
    "Alex", "Avery", "Casey", "Drew", "Emery", "Hayden", "Jamie", "Jordan",
    "Kai", "Morgan", "Parker", "Quinn", "Reese", "Riley", "Robin", "Taylor",
]
LAST_NAMES = [
    "Adams", "Baker", "Carter", "Diaz", "Evans", "Foster", "Garcia", "Harris",
    "Ivanov", "Johnson", "Kim", "Lee", "Martin", "Nguyen", "Patel", "Rivera",
]


@dataclass
class Shift:
    shift_id: str
    driver_id: str
    vehicle_id: str
    vendor_id: int
    start: datetime
    first_pickup: datetime
    first_zone: int
    last_dropoff: datetime
    last_zone: int
    trip_count: int = 0
    occupied_minutes: float = 0.0
    idle_minutes: float = 0.0


@dataclass
class Resource:
    index: int
    driver_id: str
    vehicle_id: str
    vendor_id: int
    home_zone: int
    available_at: datetime = datetime(1900, 1, 1)
    last_zone: int = 0
    is_idle: bool = True
    idle_token: int = 0
    current_shift: Shift | None = None


class VendorPool:
    def __init__(self, resources: list[Resource]):
        self.resources = resources
        self.busy: list[tuple[datetime, int, int]] = []
        self.by_zone: dict[int, list[tuple[int, int]]] = defaultdict(list)
        self.global_idle: list[tuple[int, int]] = []
        for resource in resources:
            self._mark_idle(resource, resource.home_zone)

    def _mark_idle(self, resource: Resource, zone: int) -> None:
        resource.is_idle = True
        resource.last_zone = zone
        resource.idle_token += 1
        token = resource.idle_token
        self.by_zone[zone].append((resource.index, token))
        self.global_idle.append((resource.index, token))

    def release_available(self, pickup: datetime) -> None:
        while self.busy and self.busy[0][0] <= pickup:
            _, index, token = heapq.heappop(self.busy)
            resource = self.resources[index]
            if token == resource.idle_token and not resource.is_idle:
                self._mark_idle(resource, resource.last_zone)

    def _take_from(self, queue: list[tuple[int, int]]) -> Resource | None:
        while queue:
            index, token = queue.pop()
            resource = self.resources[index]
            if resource.is_idle and token == resource.idle_token:
                resource.is_idle = False
                return resource
        return None

    def acquire(self, pickup: datetime, pickup_zone: int) -> tuple[Resource | None, str]:
        self.release_available(pickup)
        resource = self._take_from(self.by_zone[pickup_zone])
        if resource is not None:
            return resource, "CONTINUITY"
        resource = self._take_from(self.global_idle)
        if resource is not None:
            return resource, "AVAILABLE_POOL"
        return None, "NO_CAPACITY"

    def set_busy(self, resource: Resource, available_at: datetime, end_zone: int) -> None:
        resource.available_at = available_at
        resource.last_zone = end_zone
        resource.idle_token += 1
        token = resource.idle_token
        resource.is_idle = False
        heapq.heappush(self.busy, (available_at, resource.index, token))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="configs/synthetic_generation.json",
        help="Config path relative to repository root.",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_vendor_lookup(source_path: Path, target_path: Path) -> None:
    vendors: dict[int, str] = {0: "Legacy / Unknown Pool"}
    if source_path.exists():
        with source_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                normalized = {key.strip(): value for key, value in row.items()}
                vendor_id = parse_int(normalized.get("vendor_id"), default=-1)
                vendor_name = (normalized.get("vendor_name") or "").strip()
                if vendor_id >= 0 and vendor_name:
                    vendors[vendor_id] = vendor_name

    with target_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["vendor_id", "vendor_name"],
        )
        writer.writeheader()
        for vendor_id, vendor_name in sorted(vendors.items()):
            writer.writerow(
                {
                    "vendor_id": vendor_id,
                    "vendor_name": vendor_name,
                }
            )


def parse_int(value: str | None, default: int = 0) -> int:
    try:
        return int(float(value or ""))
    except (TypeError, ValueError):
        return default


def parse_datetime(value: str | None) -> datetime:
    return datetime.fromisoformat(value or "")


def source_period(path: Path) -> tuple[int, int]:
    year = int(path.parent.parent.name.split("=", 1)[1])
    month = int(path.parent.name.split("=", 1)[1])
    return year, month


def trip_key(source_file: str, row_number: int, row: dict[str, str]) -> str:
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


def write_drivers(
    output_path: Path,
    resources: list[Resource],
    randomizer: random.Random,
    period_start: date,
) -> dict[str, dict[str, Any]]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records: dict[str, dict[str, Any]] = {}
    fields = [
        "driver_id", "vendor_id", "driver_code", "display_name", "hire_date",
        "employment_status", "license_status", "license_expiry_date",
        "experience_years", "home_borough", "source_updated_at",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for resource in resources:
            years = randomizer.randint(0, 18)
            hire_date = period_start - timedelta(days=365 * years + randomizer.randint(0, 364))
            record = {
                "driver_id": resource.driver_id,
                "vendor_id": resource.vendor_id,
                "driver_code": f"EMP-{resource.driver_id[3:]}",
                "display_name": (
                    f"{randomizer.choice(FIRST_NAMES)} "
                    f"{randomizer.choice(LAST_NAMES)} (Synthetic)"
                ),
                "hire_date": hire_date.isoformat(),
                "employment_status": "ACTIVE",
                "license_status": "ACTIVE",
                "license_expiry_date": date(2023, 12, 31).isoformat(),
                "experience_years": years,
                "home_borough": randomizer.choice(BOROUGHS),
                "source_updated_at": "2019-12-15T00:00:00",
            }
            records[resource.driver_id] = record
            writer.writerow(record)
    return records


def write_vehicles(
    output_path: Path,
    resources: list[Resource],
    randomizer: random.Random,
    period_start: date,
    period_end: date,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for resource in resources:
            model_year = randomizer.randint(2012, 2020)
            service_start = max(
                date(model_year, 1, 1),
                period_start - timedelta(days=randomizer.randint(60, 1800)),
            )
            inspection_date = min(
                service_start + timedelta(days=randomizer.randint(5, 365)),
                period_end,
            )
            record = {
                "vehicle_id": resource.vehicle_id,
                "vendor_id": resource.vendor_id,
                "plate_token": f"SYN-{resource.vehicle_id[3:]}",
                "model_year": model_year,
                "vehicle_type": randomizer.choices(
                    ["SEDAN", "HYBRID", "WAV"], weights=[55, 30, 15], k=1
                )[0],
                "service_start_date": service_start.isoformat(),
                "vehicle_status": "ACTIVE",
                "last_inspection_date": inspection_date.isoformat(),
                "source_updated_at": f"{period_end.isoformat()}T23:59:59",
            }
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")


def write_driver_changes(
    output_path: Path,
    drivers: dict[str, dict[str, Any]],
    randomizer: random.Random,
    event_rate: float,
    late_rate: float,
) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for driver_id, driver in sorted(drivers.items()):
            if randomizer.random() >= event_rate:
                continue
            effective = datetime(2020, 7, 1) + timedelta(
                days=randomizer.randint(0, 365), hours=randomizer.randint(0, 23)
            )
            is_late = randomizer.random() < late_rate
            delivered = effective + timedelta(days=randomizer.randint(7, 45) if is_late else 0)
            old_borough = driver["home_borough"]
            new_borough = randomizer.choice([b for b in BOROUGHS if b != old_borough])
            count += 1
            record = {
                "event_id": f"DRVCHG{count:06d}",
                "driver_id": driver_id,
                "event_type": "HOME_BOROUGH_CHANGED",
                "effective_at": effective.isoformat(timespec="seconds"),
                "delivered_at": delivered.isoformat(timespec="seconds"),
                "changes": {"home_borough": new_borough},
                "is_late_arriving": is_late,
            }
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    return count


def build_resources(config: dict[str, Any], randomizer: random.Random) -> list[Resource]:
    resources: list[Resource] = []
    serial = 0
    for vendor_text, pool_size in sorted(
        config["driver_pool_by_vendor"].items(), key=lambda item: int(item[0])
    ):
        vendor_id = int(vendor_text)
        for _ in range(int(pool_size)):
            serial += 1
            resources.append(
                Resource(
                    index=0,
                    driver_id=f"DRV{serial:06d}",
                    vehicle_id=f"VEH{serial:06d}",
                    vendor_id=vendor_id,
                    home_zone=randomizer.randint(1, 265),
                )
            )
    return resources


def calculate_shift_end(
    shift: Shift,
    buffer_minutes: int,
    next_pickup: datetime | None = None,
) -> datetime:
    if next_pickup is None:
        return shift.last_dropoff + timedelta(minutes=buffer_minutes)
    gap_seconds = max(0.0, (next_pickup - shift.last_dropoff).total_seconds())
    return shift.last_dropoff + timedelta(
        seconds=min(buffer_minutes * 60, gap_seconds / 2)
    )


def calculate_total_idle_minutes(shift: Shift, end: datetime) -> float:
    start_idle = max(
        0.0, (shift.first_pickup - shift.start).total_seconds() / 60
    )
    end_idle = max(0.0, (end - shift.last_dropoff).total_seconds() / 60)
    return shift.idle_minutes + start_idle + end_idle


def finalize_shift(
    writer: csv.DictWriter,
    shift: Shift,
    buffer_minutes: int,
    next_pickup: datetime | None = None,
) -> None:
    end = calculate_shift_end(shift, buffer_minutes, next_pickup)
    total_idle_minutes = calculate_total_idle_minutes(shift, end)
    writer.writerow(
        {
            "shift_id": shift.shift_id,
            "driver_id": shift.driver_id,
            "vehicle_id": shift.vehicle_id,
            "vendor_id": shift.vendor_id,
            "shift_start": shift.start.isoformat(sep=" ", timespec="seconds"),
            "shift_end": end.isoformat(sep=" ", timespec="seconds"),
            "assigned_start_zone": shift.first_zone,
            "actual_end_zone": shift.last_zone,
            "trip_count": shift.trip_count,
            "occupied_minutes": f"{shift.occupied_minutes:.2f}",
            "idle_minutes": f"{total_idle_minutes:.2f}",
            "shift_status": "COMPLETED",
        }
    )


def generate(config_path: Path) -> None:
    repo_root = config_path.parent.parent.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    randomizer = random.Random(int(config["seed"]))
    source_root = (repo_root / config["source_trip_root"]).resolve()
    lookup_root = (repo_root / config["source_lookup_root"]).resolve()
    output_root = (repo_root / config["output_root"]).resolve()
    metadata_root = (repo_root / config["metadata_root"]).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    metadata_root.mkdir(parents=True, exist_ok=True)

    trip_files = sorted(source_root.rglob("*.csv"))
    if not trip_files:
        raise SystemExit(f"No trip CSV files found under {source_root}")

    resources = build_resources(config, randomizer)
    by_vendor: dict[int, list[Resource]] = defaultdict(list)
    for resource in resources:
        by_vendor[resource.vendor_id].append(resource)
    pools: dict[int, VendorPool] = {}
    for vendor_id, vendor_resources in by_vendor.items():
        for local_index, resource in enumerate(vendor_resources):
            resource.index = local_index
        pools[vendor_id] = VendorPool(vendor_resources)

    period_start = date(2020, 1, 1)
    period_end = date(2021, 7, 31)
    drivers = write_drivers(
        output_root / "driver_hr" / "drivers.csv",
        resources,
        randomizer,
        period_start,
    )
    write_vehicles(
        output_root / "fleet" / "vehicles.jsonl",
        resources,
        randomizer,
        period_start,
        period_end,
    )
    change_count = write_driver_changes(
        output_root / "driver_hr" / "driver_changes.jsonl",
        drivers,
        randomizer,
        float(config["change_event_rate"]),
        float(config["late_arriving_event_rate"]),
    )

    lookup_target = repo_root / "data" / "lookup"
    lookup_target.mkdir(parents=True, exist_ok=True)
    taxi_zone_source = lookup_root / "taxi_zone.csv"
    if taxi_zone_source.exists():
        shutil.copyfile(taxi_zone_source, lookup_target / "taxi_zone.csv")
    write_vendor_lookup(
        lookup_root / "vendor.csv",
        lookup_target / "vendor.csv",
    )

    shift_path = output_root / "dispatch" / "shifts.tsv"
    exception_path = output_root / "trip_assignment" / "assignment_exceptions.csv"
    shift_path.parent.mkdir(parents=True, exist_ok=True)
    exception_path.parent.mkdir(parents=True, exist_ok=True)

    shift_fields = [
        "shift_id", "driver_id", "vehicle_id", "vendor_id", "shift_start",
        "shift_end", "assigned_start_zone", "actual_end_zone", "trip_count",
        "occupied_minutes", "idle_minutes", "shift_status",
    ]
    exception_fields = [
        "source_file", "source_row_number", "reason",
        "pickup_datetime", "dropoff_datetime", "vendor_id",
    ]

    counters = Counter()
    source_manifest: list[dict[str, Any]] = []
    shift_serial = 0
    max_shift = timedelta(hours=float(config["max_shift_hours"]))
    max_gap = timedelta(minutes=float(config["max_continuity_gap_minutes"]))
    buffer_minutes = int(config["shift_buffer_minutes"])

    with (
        shift_path.open("w", encoding="utf-8", newline="") as shift_handle,
        exception_path.open("w", encoding="utf-8", newline="") as exception_handle,
    ):
        shift_writer = csv.DictWriter(
            shift_handle, fieldnames=shift_fields, delimiter="\t"
        )
        shift_writer.writeheader()
        exception_writer = csv.DictWriter(
            exception_handle, fieldnames=exception_fields
        )
        exception_writer.writeheader()

        for trip_file in trip_files:
            relative_source = trip_file.relative_to(source_root).as_posix()
            year, month = source_period(trip_file)
            rows: list[tuple[datetime, int, dict[str, str], datetime]] = []
            raw_count = 0
            with trip_file.open("r", encoding="utf-8-sig", newline="") as handle:
                for row_number, row in enumerate(csv.DictReader(handle), start=2):
                    raw_count += 1
                    try:
                        pickup = parse_datetime(row.get("lpep_pickup_datetime"))
                        dropoff = parse_datetime(row.get("lpep_dropoff_datetime"))
                    except ValueError:
                        counters["invalid_datetime"] += 1
                        exception_writer.writerow(
                            {
                                "source_file": relative_source,
                                "source_row_number": row_number,
                                "reason": "INVALID_DATETIME",
                                "pickup_datetime": row.get("lpep_pickup_datetime", ""),
                                "dropoff_datetime": row.get("lpep_dropoff_datetime", ""),
                                "vendor_id": row.get("VendorID", ""),
                            }
                        )
                        continue
                    if pickup.year != year or pickup.month != month:
                        counters["outside_source_period"] += 1
                        exception_writer.writerow(
                            {
                                "source_file": relative_source,
                                "source_row_number": row_number,
                                "reason": "OUTSIDE_SOURCE_PERIOD",
                                "pickup_datetime": pickup.isoformat(sep=" "),
                                "dropoff_datetime": dropoff.isoformat(sep=" "),
                                "vendor_id": row.get("VendorID", ""),
                            }
                        )
                        continue
                    duration = dropoff - pickup
                    if duration.total_seconds() < 0 or duration > timedelta(hours=24):
                        counters["invalid_duration"] += 1
                        exception_writer.writerow(
                            {
                                "source_file": relative_source,
                                "source_row_number": row_number,
                                "reason": "INVALID_DURATION",
                                "pickup_datetime": pickup.isoformat(sep=" "),
                                "dropoff_datetime": dropoff.isoformat(sep=" "),
                                "vendor_id": row.get("VendorID", ""),
                            }
                        )
                        continue
                    rows.append((pickup, row_number, row, dropoff))

            rows.sort(key=lambda item: (item[0], item[1]))
            assignment_path = (
                output_root
                / "trip_assignment"
                / f"year={year}"
                / f"month={month:02d}"
                / f"trip_assignment_{year}-{month:02d}.csv"
            )
            assignment_path.parent.mkdir(parents=True, exist_ok=True)
            assignment_fields = [
                "trip_key", "source_file", "source_row_number", "driver_id",
                "vehicle_id", "shift_id", "assignment_timestamp",
                "assignment_method",
            ]
            assigned_in_file = 0
            with assignment_path.open(
                "w", encoding="utf-8", newline=""
            ) as assignment_handle:
                assignment_writer = csv.DictWriter(
                    assignment_handle, fieldnames=assignment_fields
                )
                assignment_writer.writeheader()

                for pickup, row_number, row, dropoff in rows:
                    vendor_id = parse_int(row.get("VendorID"), default=0)
                    if vendor_id not in pools:
                        vendor_id = 0
                    pickup_zone = parse_int(row.get("PULocationID"), default=0)
                    dropoff_zone = parse_int(row.get("DOLocationID"), default=0)
                    pool = pools[vendor_id]
                    resource, method = pool.acquire(pickup, pickup_zone)
                    if resource is None:
                        counters["no_capacity"] += 1
                        exception_writer.writerow(
                            {
                                "source_file": relative_source,
                                "source_row_number": row_number,
                                "reason": "NO_CAPACITY",
                                "pickup_datetime": pickup.isoformat(sep=" "),
                                "dropoff_datetime": dropoff.isoformat(sep=" "),
                                "vendor_id": vendor_id,
                            }
                        )
                        continue

                    current = resource.current_shift
                    can_continue = False
                    if current is not None:
                        gap = pickup - current.last_dropoff
                        can_continue = (
                            timedelta(0) <= gap <= max_gap
                            and dropoff - current.start <= max_shift
                        )
                    if not can_continue:
                        previous_shift_end = None
                        if current is not None:
                            previous_shift_end = calculate_shift_end(
                                current,
                                buffer_minutes,
                                next_pickup=pickup,
                            )
                            finalize_shift(
                                shift_writer,
                                current,
                                buffer_minutes,
                                next_pickup=pickup,
                            )
                            counters["shifts"] += 1
                        shift_serial += 1
                        shift_start = pickup - timedelta(minutes=buffer_minutes)
                        if previous_shift_end is not None:
                            shift_start = max(shift_start, previous_shift_end)
                        current = Shift(
                            shift_id=f"SHF{shift_serial:010d}",
                            driver_id=resource.driver_id,
                            vehicle_id=resource.vehicle_id,
                            vendor_id=vendor_id,
                            start=shift_start,
                            first_pickup=pickup,
                            first_zone=pickup_zone,
                            last_dropoff=dropoff,
                            last_zone=dropoff_zone,
                        )
                        resource.current_shift = current
                    else:
                        current.idle_minutes += max(
                            0.0, (pickup - current.last_dropoff).total_seconds() / 60
                        )

                    duration_minutes = max(
                        0.0, (dropoff - pickup).total_seconds() / 60
                    )
                    current.trip_count += 1
                    current.occupied_minutes += duration_minutes
                    current.last_dropoff = dropoff
                    current.last_zone = dropoff_zone

                    assignment_writer.writerow(
                        {
                            "trip_key": trip_key(relative_source, row_number, row),
                            "source_file": relative_source,
                            "source_row_number": row_number,
                            "driver_id": resource.driver_id,
                            "vehicle_id": resource.vehicle_id,
                            "shift_id": current.shift_id,
                            "assignment_timestamp": (
                                pickup - timedelta(minutes=randomizer.randint(1, 15))
                            ).isoformat(sep=" ", timespec="seconds"),
                            "assignment_method": method,
                        }
                    )
                    pool.set_busy(resource, dropoff, dropoff_zone)
                    assigned_in_file += 1
                    counters["assigned_trips"] += 1
                    counters[f"vendor_{vendor_id}_trips"] += 1

            source_manifest.append(
                {
                    "source_file": relative_source,
                    "year": year,
                    "month": month,
                    "raw_rows": raw_count,
                    "eligible_rows": len(rows),
                    "assigned_rows": assigned_in_file,
                    "source_sha256": sha256_file(trip_file),
                    "assignment_file": assignment_path.relative_to(repo_root).as_posix(),
                    "assignment_sha256": sha256_file(assignment_path),
                }
            )
            print(
                f"{relative_source}: raw={raw_count:,} "
                f"eligible={len(rows):,} assigned={assigned_in_file:,}"
            )

        for resource in resources:
            if resource.current_shift is not None:
                finalize_shift(
                    shift_writer,
                    resource.current_shift,
                    buffer_minutes,
                    next_pickup=None,
                )
                counters["shifts"] += 1

    output_files = [
        output_root / "driver_hr" / "drivers.csv",
        output_root / "driver_hr" / "driver_changes.jsonl",
        output_root / "fleet" / "vehicles.jsonl",
        shift_path,
        exception_path,
    ]
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "seed": config["seed"],
        "trip_period": {"start": "2020-01", "end": "2021-07"},
        "driver_count": len(resources),
        "vehicle_count": len(resources),
        "driver_change_count": change_count,
        "counts": dict(sorted(counters.items())),
        "source_files": source_manifest,
        "generated_files": [
            {
                "path": path.relative_to(repo_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in output_files
        ],
    }
    manifest_path = metadata_root / "synthetic_generation_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        "Wrote manifest: "
        f"{manifest_path.relative_to(repo_root).as_posix()}"
    )
    print(json.dumps(manifest["counts"], indent=2))


if __name__ == "__main__":
    args = parse_args()
    generate(Path(args.config).resolve())
