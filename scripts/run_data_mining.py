#!/usr/bin/env python3
"""CLI script to run K-Means driver segmentation and Apriori association rules."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.analytics.data_mining import execute_data_mining

ANALYTICS_SQL = REPO_ROOT / "sql" / "analytics" / "01_certified_datasets.sql"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Green Taxi BI Data Mining step.")
    parser.add_argument("--release-id", default="green-taxi-full-v1", help="Data release identifier.")
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
    
    print(f"Starting Data Mining models for release: {args.release_id}")
    
    try:
        conn = connect()
        try:
            with conn.cursor() as cur:
                cur.execute(ANALYTICS_SQL.read_text(encoding="utf-8"))
            conn.commit()
            counts = execute_data_mining(conn)
            conn.commit()
            print(f"Data Mining completed successfully. Counts: {counts}")
            return 0
        except Exception as exc:
            conn.rollback()
            print(f"Data Mining failed: {exc}", file=sys.stderr)
            return 1
        finally:
            conn.close()
    except Exception as conn_exc:
        print(f"Failed to connect to database: {conn_exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
