"""Apply PostgreSQL warehouse DDL for the Green Taxi project.

The script reads connection settings from environment variables and an optional
root .env file. It never hard-codes passwords. By default it first tries a
direct psycopg connection, then falls back to running psql inside the
postgres_warehouse Docker Compose service.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DDL_DIR = REPO_ROOT / "sql" / "warehouse"
DEFAULT_FILES = (
    "00_create_schemas.sql",
    "01_audit_metadata.sql",
    "02_staging_tables.sql",
    "03_nds_tables.sql",
    "04_dds_tables.sql",
    "05_dq_quarantine.sql",
)

VERIFY_SCHEMAS = ("staging", "audit", "dq", "nds", "dds")


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    pattern = re.compile(r"\$\{([^}:]+)(?::-[^}]*)?\}")
    values: dict[str, str] = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        def replace_var(match: re.Match[str]) -> str:
            var_name = match.group(1)
            return os.environ.get(var_name, values.get(var_name, ""))

        value = pattern.sub(replace_var, value)
        values[key] = value
        os.environ.setdefault(key, value)


def env(name: str, fallback: str | None = None) -> str | None:
    return os.environ.get(name) or (os.environ.get(fallback) if fallback else None)


def read_ddl(files: tuple[str, ...]) -> str:
    statements = []
    for file_name in files:
        path = DDL_DIR / file_name
        statements.append(
            f"-- BEGIN {file_name}\n{path.read_text(encoding='utf-8')}\n-- END {file_name}"
        )
    return "\n\n".join(statements)


def warehouse_conninfo() -> dict[str, str | None]:
    return {
        "host": env("POSTGRES_WAREHOUSE_HOST", "DB_HOST") or "localhost",
        "port": env("POSTGRES_WAREHOUSE_PORT", "DB_PORT") or "5434",
        "dbname": env("POSTGRES_WAREHOUSE_DATABASE", "DB_NAME") or "green_taxi_warehouse",
        "user": env("POSTGRES_WAREHOUSE_USER", "DB_USER") or "green_taxi_warehouse_app",
        "password": env("POSTGRES_WAREHOUSE_PASSWORD", "DB_PASSWORD"),
    }


def apply_with_psycopg(sql_text: str) -> bool:
    try:
        import psycopg  # type: ignore[import-not-found]
    except ImportError:
        return False

    with psycopg.connect(**warehouse_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_text)
        conn.commit()
    return True


def verify_with_psycopg() -> bool:
    try:
        import psycopg  # type: ignore[import-not-found]
    except ImportError:
        return False

    query = """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema = ANY(%s)
        ORDER BY table_schema, table_name;
    """
    with psycopg.connect(**warehouse_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (list(VERIFY_SCHEMAS),))
            rows = cur.fetchall()
            schemas_seen = {schema for schema, _table in rows}
    missing = set(VERIFY_SCHEMAS) - schemas_seen
    if missing:
        raise RuntimeError(f"DDL verification found no tables in schemas: {', '.join(sorted(missing))}")
    for schema, table in rows:
        print(f"{schema}.{table}")
    return True


def apply_with_docker_compose(sql_text: str) -> None:
    user = env("POSTGRES_WAREHOUSE_USER", "DB_USER") or "green_taxi_warehouse_app"
    database = env("POSTGRES_WAREHOUSE_DATABASE", "DB_NAME") or "green_taxi_warehouse"
    service = os.environ.get("POSTGRES_WAREHOUSE_SERVICE", "postgres_warehouse")
    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        service,
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        user,
        "-d",
        database,
    ]
    subprocess.run(command, input=sql_text, text=True, cwd=REPO_ROOT, check=True)


def verify_with_docker_compose() -> None:
    user = env("POSTGRES_WAREHOUSE_USER", "DB_USER") or "green_taxi_warehouse_app"
    database = env("POSTGRES_WAREHOUSE_DATABASE", "DB_NAME") or "green_taxi_warehouse"
    service = os.environ.get("POSTGRES_WAREHOUSE_SERVICE", "postgres_warehouse")
    schema_list = ", ".join(f"'{schema}'" for schema in VERIFY_SCHEMAS)
    query = f"""
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema IN ({schema_list})
        ORDER BY table_schema, table_name;

        DO $$
        DECLARE
            missing_schema TEXT;
        BEGIN
            SELECT expected.schema_name
            INTO missing_schema
            FROM unnest(ARRAY[{schema_list}]) AS expected(schema_name)
            WHERE NOT EXISTS (
                SELECT 1
                FROM information_schema.tables t
                WHERE t.table_schema = expected.schema_name
            )
            LIMIT 1;

            IF missing_schema IS NOT NULL THEN
                RAISE EXCEPTION 'DDL verification found no tables in schema: %', missing_schema;
            END IF;
        END $$;
    """
    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        service,
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        user,
        "-d",
        database,
        "-c",
        query,
    ]
    subprocess.run(command, cwd=REPO_ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply Green Taxi warehouse DDL.")
    parser.add_argument(
        "--mode",
        choices=("auto", "psycopg", "docker"),
        default=os.environ.get("WAREHOUSE_DDL_APPLY_MODE", "auto"),
        help="Connection mode. Default: auto.",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip table existence verification query after applying DDL.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(REPO_ROOT / ".env")
    sql_text = read_ddl(DEFAULT_FILES)

    try:
        applied_mode = args.mode
        if args.mode in ("auto", "psycopg"):
            applied = apply_with_psycopg(sql_text)
            if applied:
                applied_mode = "psycopg"
                print("Applied warehouse DDL using psycopg.")
            elif args.mode == "psycopg":
                raise RuntimeError("psycopg is not installed; use --mode docker or install psycopg.")
            else:
                applied_mode = "docker"
                apply_with_docker_compose(sql_text)
                print("Applied warehouse DDL using docker compose exec.")
        else:
            applied_mode = "docker"
            apply_with_docker_compose(sql_text)
            print("Applied warehouse DDL using docker compose exec.")

        if not args.skip_verify:
            if applied_mode == "psycopg":
                verify_with_psycopg()
            else:
                verify_with_docker_compose()
        return 0
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"Failed to apply warehouse DDL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
