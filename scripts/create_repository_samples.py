#!/usr/bin/env python3
"""Create a small referentially complete sample for Git and automated tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path


SAMPLE_SIZE = 100


def main() -> None:
    repo = Path.cwd().resolve()
    synthetic = repo / "data" / "raw" / "synthetic"
    sample = repo / "data" / "sample"
    sample.mkdir(parents=True, exist_ok=True)

    assignment_file = next(
        iter(sorted((synthetic / "trip_assignment").rglob("trip_assignment_*.csv")))
    )
    with assignment_file.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assignments = [row for _, row in zip(range(SAMPLE_SIZE), reader)]
        assignment_fields = reader.fieldnames or []

    driver_ids = {row["driver_id"] for row in assignments}
    vehicle_ids = {row["vehicle_id"] for row in assignments}
    shift_ids = {row["shift_id"] for row in assignments}

    with (sample / "trip_assignments_sample.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=assignment_fields)
        writer.writeheader()
        writer.writerows(assignments)

    with (synthetic / "driver_hr" / "drivers.csv").open(
        encoding="utf-8", newline=""
    ) as source, (sample / "drivers_sample.csv").open(
        "w", encoding="utf-8", newline=""
    ) as target:
        reader = csv.DictReader(source)
        writer = csv.DictWriter(target, fieldnames=reader.fieldnames or [])
        writer.writeheader()
        writer.writerows(row for row in reader if row["driver_id"] in driver_ids)

    with (synthetic / "fleet" / "vehicles.jsonl").open(
        encoding="utf-8"
    ) as source, (sample / "vehicles_sample.jsonl").open(
        "w", encoding="utf-8"
    ) as target:
        for line in source:
            record = json.loads(line)
            if record["vehicle_id"] in vehicle_ids:
                target.write(json.dumps(record, ensure_ascii=True) + "\n")

    with (synthetic / "dispatch" / "shifts.tsv").open(
        encoding="utf-8", newline=""
    ) as source, (sample / "shifts_sample.tsv").open(
        "w", encoding="utf-8", newline=""
    ) as target:
        reader = csv.DictReader(source, delimiter="\t")
        writer = csv.DictWriter(
            target, fieldnames=reader.fieldnames or [], delimiter="\t"
        )
        writer.writeheader()
        writer.writerows(row for row in reader if row["shift_id"] in shift_ids)

    assignments_by_source: dict[str, dict[int, dict[str, str]]] = {}
    for assignment in assignments:
        assignments_by_source.setdefault(assignment["source_file"], {})[
            int(assignment["source_row_number"])
        ] = assignment

    trip_config = json.loads(
        (repo / "configs" / "synthetic_generation.json").read_text(encoding="utf-8")
    )
    trip_root = (repo / trip_config["source_trip_root"]).resolve()
    trip_rows: list[dict[str, str]] = []
    trip_fields: list[str] = []
    for source_file, row_map in assignments_by_source.items():
        with (trip_root / Path(source_file)).open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            reader = csv.DictReader(handle)
            trip_fields = ["source_file", "source_row_number"] + (
                reader.fieldnames or []
            )
            for row_number, row in enumerate(reader, start=2):
                if row_number in row_map:
                    trip_rows.append(
                        {
                            "source_file": source_file,
                            "source_row_number": str(row_number),
                            **row,
                        }
                    )

    with (sample / "tlc_trips_sample.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=trip_fields)
        writer.writeheader()
        writer.writerows(trip_rows)

    print(
        f"Created {len(assignments)} linked assignments, "
        f"{len(driver_ids)} drivers, {len(vehicle_ids)} vehicles, "
        f"{len(shift_ids)} shifts, and {len(trip_rows)} TLC trip rows."
    )


if __name__ == "__main__":
    main()

