#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI Entry point for loading NDS data into PostgreSQL Warehouse DDS."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from tabulate import tabulate
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.warehouse.dds_loader import DDSLoader


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        if getattr(stream, "encoding", None) != "utf-8":
            try:
                stream.reconfigure(encoding="utf-8")
            except AttributeError:
                pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load PostgreSQL Warehouse NDS data into Dimensional Data Store (DDS)."
    )
    parser.add_argument(
        "--release-id",
        default="green-taxi-full-v1",
        help="Data release identifier. Default: green-taxi-full-v1.",
    )
    return parser.parse_args()


def main() -> int:
    configure_console()

    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        print(
            f"[!] Warning: .env file not found at {env_path}. Using system environment variables.",
            file=sys.stderr,
        )

    args = parse_args()

    print(f"[*] Starting warehouse DDS load for release '{args.release_id}'...")

    loader = DDSLoader(release_id=args.release_id)

    try:
        loader.start_batch_log(input_params=vars(args))
    except Exception as e:
        print(f"[!] LỖI: Không khởi tạo được batch log: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1

    loaded_total = 0
    success = True
    error_msg = None

    try:
        print("\n[*] Loading dim_date...")
        r, q = loader.load_dim_date()
        loaded_total += r
        print(f"    -> {r} dates loaded")

        print("[*] Loading dim_time...")
        r, q = loader.load_dim_time()
        loaded_total += r
        print(f"    -> {r} time rows loaded")

        print("[*] Loading dim_vendor...")
        r, q = loader.load_dim_vendor()
        loaded_total += r
        print(f"    -> {r} vendors loaded")

        print("[*] Loading dim_location...")
        r, q = loader.load_dim_location()
        loaded_total += r
        print(f"    -> {r} locations loaded")

        print("[*] Loading dim_driver (SCD2)...")
        r, new_v, noop = loader.load_dim_driver()
        loaded_total += new_v
        print(f"    -> {r} NDS drivers processed, {new_v} new/changed versions, {noop} no-op")

        print("[*] Loading dim_vehicle (SCD2)...")
        r, new_v, noop = loader.load_dim_vehicle()
        loaded_total += new_v
        print(f"    -> {r} NDS vehicles processed, {new_v} new/changed versions, {noop} no-op")

        print("\n[*] Running DQ Gate 2 anomaly checks...")
        dq_results = loader.run_dq_gate2()
        for rule, count in dq_results.items():
            if count > 0:
                print(f"    -> {rule}: {count} warnings")
            else:
                print(f"    -> {rule}: OK")

        print("\n[*] Loading fact_driver_trip...")
        r, q = loader.load_fact_driver_trip()
        loaded_total += r
        print(f"    -> {r} trips loaded")

        print("[*] Loading fact_driver_shift...")
        r, q = loader.load_fact_driver_shift()
        loaded_total += r
        print(f"    -> {r} shifts loaded")

    except Exception as e:
        success = False
        error_msg = str(e)
        print(f"\n[!] LỖI TRONG QUÁ TRÌNH LOAD DDS: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

    batch_status = "SUCCEEDED" if success else "FAILED"

    try:
        loader.complete_batch_log(
            status=batch_status,
            loaded_rows=loaded_total,
            error_msg=error_msg,
        )
    except Exception as e:
        print(f"[!] Warning: Could not finalize batch log: {e}", file=sys.stderr)

    print(f"\n=== DDS LOAD SUMMARY ===")
    print(f"Batch ID:      {loader.batch_id}")
    print(f"Release ID:    {loader.release_id}")
    print(f"Total Loaded:  {loaded_total}")
    print(f"Status:        {batch_status}")

    if dq_results:
        print(f"\nDQ Gate 2 Results:")
        dq_table = [(rule, count) for rule, count in dq_results.items()]
        print(tabulate(dq_table, headers=["Rule", "Warnings"], tablefmt="grid"))

    print("=========================\n")

    loader.close_all()
    return 0 if success else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"CRITICAL ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
