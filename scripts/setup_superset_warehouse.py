"""Apply analytics views and provision the least-privilege Superset login."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from psycopg import sql

from scripts.apply_warehouse_ddl import load_dotenv, warehouse_conninfo


ROOT = Path(__file__).resolve().parents[1]
ANALYTICS_SQL = ROOT / "sql" / "analytics" / "01_certified_datasets.sql"
GRANTS_SQL = ROOT / "sql" / "analytics" / "02_superset_readonly_role.sql"


def main() -> int:
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / ".env.superset")
    password = os.environ.get("SUPERSET_WAREHOUSE_PASSWORD")
    if not password or password.startswith("CHANGE_ME"):
        print("SUPERSET_WAREHOUSE_PASSWORD is missing or still a placeholder.", file=sys.stderr)
        return 2

    conninfo = warehouse_conninfo()
    with psycopg.connect(**conninfo) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'superset_ro'")
            if cur.fetchone():
                cur.execute(
                    sql.SQL("ALTER ROLE superset_ro WITH LOGIN PASSWORD {}").format(
                        sql.Literal(password)
                    )
                )
            else:
                cur.execute(
                    sql.SQL(
                        "CREATE ROLE superset_ro WITH LOGIN NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOINHERIT NOREPLICATION PASSWORD {}"
                    ).format(sql.Literal(password))
                )
            cur.execute(ANALYTICS_SQL.read_text(encoding="utf-8"))
            cur.execute(GRANTS_SQL.read_text(encoding="utf-8"))
        conn.commit()

    print("Applied analytics views and configured superset_ro.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
