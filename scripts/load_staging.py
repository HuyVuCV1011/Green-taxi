#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI Entry point for loading source data into PostgreSQL Warehouse Staging."""

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

from src.ingestion.staging_loader import StagingLoader


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
        description="Extract source databases and raw files to PostgreSQL Warehouse Staging."
    )
    parser.add_argument(
        "--source",
        choices=["hr", "fleet", "dispatch", "tlc", "lookup", "all"],
        default="all",
        help="Specify source system to load. Default: all."
    )
    parser.add_argument(
        "--release-id",
        default="green-taxi-full-v1",
        help="Data release identifier. Default: green-taxi-full-v1."
    )
    parser.add_argument(
        "--data-root",
        default=os.environ.get("DATA_ROOT", "data"),
        help="Repository-relative or absolute data root path. Default: data."
    )
    parser.add_argument(
        "--limit-files",
        type=int,
        default=None,
        help="Limit the number of TLC CSV files imported (for testing)."
    )
    parser.add_argument(
        "--limit-rows",
        type=int,
        default=None,
        help="Limit the number of rows processed per TLC CSV file (for testing)."
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

    data_root = Path(args.data_root)
    if not data_root.is_absolute():
        data_root = REPO_ROOT / data_root
    data_root = data_root.resolve()

    print(f"[*] Starting warehouse staging load for release '{args.release_id}'...")
    print(f"[*] Target source(s): {args.source}")
    print(f"[*] Data root directory: {data_root}")

    loader = StagingLoader(release_id=args.release_id)
    
    # Map CLI source option to database constraint values
    source_system_map = {
        "hr": "HR_MYSQL",
        "fleet": "FLEET_MONGODB",
        "dispatch": "DISPATCH_POSTGRES",
        "tlc": "TLC_FILE",
        "lookup": "LOOKUP_FILE",
    }
    target_system = source_system_map.get(args.source)

    # Initialize batch logs
    try:
        loader.start_batch_log(
            source_system=target_system,
            input_params=vars(args)
        )
    except Exception as e:
        print(f"[!] LỖI: Không khởi tạo được batch log trong Warehouse: {e}", file=sys.stderr)
        return 1

    expected_total = 0
    loaded_total = 0
    success = True
    error_msg = None

    try:
        # 1. Load HR (MySQL)
        if args.source in ("hr", "all"):
            print("\n[*] Loading HR (MySQL)...")
            ext, lod = loader.load_hr()
            expected_total += ext
            loaded_total += lod

        # 2. Load Fleet (MongoDB)
        if args.source in ("fleet", "all"):
            print("\n[*] Loading Fleet (MongoDB)...")
            ext, lod = loader.load_fleet()
            expected_total += ext
            loaded_total += lod

        # 3. Load Dispatch (PostgreSQL Source)
        if args.source in ("dispatch", "all"):
            print("\n[*] Loading Dispatch (PostgreSQL Source)...")
            ext, lod = loader.load_dispatch()
            expected_total += ext
            loaded_total += lod

        # 4. Load Lookups (CSV files)
        if args.source in ("lookup", "all"):
            print("\n[*] Loading Lookups (CSV files)...")
            ext, lod = loader.load_lookup(data_root)
            expected_total += ext
            loaded_total += lod

        # 5. Load TLC Green Taxi Trips (CSV files)
        if args.source in ("tlc", "all"):
            print("\n[*] Loading TLC Green Taxi Trips (CSV files)...")
            ext, lod = loader.load_tlc(data_root, limit_files=args.limit_files, limit_rows=args.limit_rows)
            expected_total += ext
            loaded_total += lod

    except Exception as e:
        success = False
        error_msg = str(e)
        print(f"\n[!] LỖI TRONG QUÁ TRÌNH LOAD: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

    # Reconcile batch status
    batch_status = "SUCCEEDED" if success else "FAILED"
    for stat in loader.stats:
        if stat[4] == "FAILED":
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
    print("\n=== ĐỐI SOÁT VÀ TỔNG HỢP TIẾN TRÌNH LOAD STAGING (RECONCILIATION SUMMARY) ===")
    headers = ["Hệ thống nguồn", "Thực thể nguồn", "Extracted Rows (Nguồn)", "Loaded Rows (Staging)", "Trạng thái"]
    print(tabulate(loader.stats, headers=headers, tablefmt="grid"))
    print(f"[*] Batch ID: {loader.batch_id}")
    print(f"[*] Trạng thái Batch: {batch_status}")
    print("============================================================================\n")

    loader.close_all()
    return 0 if success else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"CRITICAL ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
