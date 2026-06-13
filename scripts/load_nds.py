#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI Entry point for loading staging data into PostgreSQL Warehouse NDS."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from tabulate import tabulate
from dotenv import load_dotenv

# Add repo root to Python path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.warehouse.nds_loader import NDSLoader


def configure_console() -> None:
    """Ensure console output is encoded in UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        if getattr(stream, "encoding", None) != "utf-8":
            try:
                stream.reconfigure(encoding="utf-8")
            except AttributeError:
                pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load PostgreSQL Warehouse Staging data to Normalized Data Store (NDS)."
    )
    parser.add_argument(
        "--release-id",
        default="green-taxi-full-v1",
        help="Data release identifier. Default: green-taxi-full-v1."
    )
    parser.add_argument(
        "--limit-rows",
        type=int,
        default=None,
        help="Limit the number of rows processed for TLC trips (for testing)."
    )
    return parser.parse_args()


def main() -> int:
    configure_console()

    # Load environment variables from .env file
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        print(f"[!] Warning: .env file not found at {env_path}. Using system environment variables.", file=sys.stderr)

    args = parse_args()

    print(f"[*] Starting warehouse NDS load for release '{args.release_id}'...")

    loader = NDSLoader(release_id=args.release_id)

    # Initialize batch logs & NDS schema
    try:
        loader.init_nds_schema()
        loader.start_batch_log(
            source_system=None,
            input_params=vars(args)
        )
    except Exception as e:
        print(f"[!] LỖI: Không khởi tạo được batch log hoặc schema NDS: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1

    expected_total = 0
    loaded_total = 0
    success = True
    error_msg = None

    try:
        # Load order: lookup -> master -> transaction
        # 1. Vendors
        print("\n[*] Loading Vendors lookup...")
        r, l, q = loader.load_vendor()
        expected_total += r
        loaded_total += l
        
        # 2. Locations
        print("[*] Loading Locations lookup...")
        r, l, q = loader.load_location()
        expected_total += r
        loaded_total += l

        # 3. Master Drivers
        print("[*] Loading Master Drivers...")
        r, l, q = loader.load_drivers()
        expected_total += r
        loaded_total += l

        # 4. Driver Changes
        print("[*] Loading Driver Changes...")
        r, l, q = loader.load_driver_changes()
        expected_total += r
        loaded_total += l

        # 5. Master Vehicles
        print("[*] Loading Master Vehicles...")
        r, l, q = loader.load_vehicles()
        expected_total += r
        loaded_total += l

        # 6. Dispatch Shifts
        print("[*] Loading Dispatch Shifts...")
        r, l, q = loader.load_shifts()
        expected_total += r
        loaded_total += l

        # 7. TLC Green Trips
        print("[*] Loading TLC Green Trips...")
        r, l, q = loader.load_trips(limit_rows=args.limit_rows)
        expected_total += r
        loaded_total += l

        # 8. Dispatch Trip Assignments
        print("[*] Loading Dispatch Trip Assignments...")
        r, l, q = loader.load_trip_assignments()
        expected_total += r
        loaded_total += l

    except Exception as e:
        success = False
        error_msg = str(e)
        print(f"\n[!] LỖI TRONG QUÁ TRÌNH LOAD NDS: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

    # Reconcile batch status
    batch_status = "SUCCEEDED" if success else "FAILED"
    for stat in loader.stats:
        if stat[5] == "FAILED":
            batch_status = "FAILED"
            success = False

    try:
        loader.complete_batch_log(
            status=batch_status,
            expected_rows=expected_total,
            loaded_rows=loaded_total,
            error_msg=error_msg
        )
    except Exception as e:
        print(f"[!] Warning: Could not finalize batch log in Warehouse: {e}", file=sys.stderr)

    # Display reconciliation summary table
    print("\n=== ĐỐI SOÁT VÀ TỔNG HỢP TIẾN TRÌNH LOAD NDS (RECONCILIATION SUMMARY) ===")
    headers = ["Hệ thống nguồn", "Thực thể", "Read (Staging)", "Loaded (NDS)", "Quarantined (DQ)", "Trạng thái"]
    print(tabulate(loader.stats, headers=headers, tablefmt="grid"))
    print(f"[*] Batch ID: {loader.batch_id}")
    print(f"[*] Trạng thái Batch: {batch_status}")
    print("=========================================================================\n")

    loader.close_all()
    return 0 if success else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"CRITICAL ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
