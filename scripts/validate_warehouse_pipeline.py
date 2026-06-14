#!/usr/bin/env python3
"""Validate warehouse reconciliation and optional database-backed DQ fixtures."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from tabulate import tabulate


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.warehouse.pipeline_validation import (  # noqa: E402
    assert_results,
    validate_dq_fixture,
    validate_release_reconciliation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Green Taxi warehouse pipeline.")
    parser.add_argument("--release-id", default="green-taxi-full-v1")
    parser.add_argument(
        "--dq-fixtures",
        action="store_true",
        help="Run destructive fixture inserts; use only on a dedicated test database.",
    )
    return parser.parse_args()


def connect() -> object:
    return psycopg2.connect(
        host=os.getenv("POSTGRES_WAREHOUSE_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_WAREHOUSE_PORT", "5434")),
        database=os.getenv("POSTGRES_WAREHOUSE_DATABASE", "green_taxi_warehouse"),
        user=os.getenv("POSTGRES_WAREHOUSE_USER", "green_taxi_warehouse_app"),
        password=os.getenv("POSTGRES_WAREHOUSE_PASSWORD", "change_me_warehouse"),
    )


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    conn = connect()
    try:
        if args.dq_fixtures:
            results = validate_dq_fixture(conn, args.release_id)
        else:
            results = validate_release_reconciliation(conn, args.release_id)
        print(
            tabulate(
                [(r.name, r.actual, r.expected, "PASS" if r.passed else "FAIL") for r in results],
                headers=["Check", "Actual", "Expected", "Status"],
                tablefmt="grid",
            )
        )
        assert_results(results)
        return 0
    except AssertionError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
