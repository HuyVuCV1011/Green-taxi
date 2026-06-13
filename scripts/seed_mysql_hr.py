#!/usr/bin/env python3
"""Seed the MySQL Driver HR source from the canonical data release."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE_ID = "green-taxi-full-v1"
DRIVER_COLUMNS = [
    "driver_id",
    "vendor_id",
    "driver_code",
    "display_name",
    "hire_date",
    "employment_status",
    "license_status",
    "license_expiry_date",
    "experience_years",
    "home_borough",
    "source_updated_at",
]
CHANGE_COLUMNS = [
    "event_id",
    "driver_id",
    "event_type",
    "effective_at",
    "delivered_at",
    "changes",
    "is_late_arriving",
]


@dataclass(frozen=True)
class MysqlConfig:
    host: str
    port: int
    database: str
    user: str
    password: str


@dataclass(frozen=True)
class SourceFileStats:
    source_entity: str
    source_file: str
    checksum: str
    row_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed MySQL Driver HR from data/raw/synthetic/driver_hr."
    )
    parser.add_argument("--release-id", default=DEFAULT_RELEASE_ID)
    parser.add_argument(
        "--data-root",
        default=os.environ.get("DATA_ROOT", "data"),
        help="Repository-relative or absolute data root. Default: DATA_ROOT or data.",
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--client",
        choices=["auto", "mysql-cli", "docker-compose"],
        default="auto",
        help="SQL execution client. auto prefers local mysql, then docker compose exec.",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Controlled full reload: truncate HR tables before seeding.",
    )
    parser.add_argument(
        "--skip-ddl",
        action="store_true",
        help="Skip applying sql/source_mysql_hr/01_driver_tables.sql before seeding.",
    )
    return parser.parse_args()


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    values: dict[str, str] = {}
    pattern = re.compile(r"\$\{([^}:]+)(?::-[^}]*)?\}")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        def replace_var(match: re.Match[str]) -> str:
            name = match.group(1)
            return os.environ.get(name, values.get(name, ""))

        value = pattern.sub(replace_var, value)
        values[key] = value
        os.environ.setdefault(key, value)


def env_config() -> MysqlConfig:
    missing = [
        name
        for name in [
            "MYSQL_HR_DATABASE",
            "MYSQL_HR_USER",
            "MYSQL_HR_PASSWORD",
        ]
        if not os.environ.get(name)
    ]
    if missing:
        raise RuntimeError(
            "Missing required MySQL HR environment variables: " + ", ".join(missing)
        )
    return MysqlConfig(
        host=os.environ.get("MYSQL_HR_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_HR_PORT", "3307")),
        database=os.environ["MYSQL_HR_DATABASE"],
        user=os.environ["MYSQL_HR_USER"],
        password=os.environ["MYSQL_HR_PASSWORD"],
    )


def resolve_data_root(raw_value: str) -> Path:
    path = Path(raw_value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def require_source_files(data_root: Path) -> tuple[Path, Path]:
    driver_dir = data_root / "raw" / "synthetic" / "driver_hr"
    drivers_path = driver_dir / "drivers.csv"
    changes_path = driver_dir / "driver_changes.jsonl"
    missing = [str(path) for path in [drivers_path, changes_path] if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing Driver HR release files. Download/extract the canonical release "
            "into data/raw first. Missing: " + "; ".join(missing)
        )
    return drivers_path, changes_path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_timestamp(value: str) -> str:
    return value.replace("T", " ")


def mysql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace("'", "''")
    return f"'{text}'"


def insert_sql(table: str, columns: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    values = ",\n".join(
        "  (" + ", ".join(mysql_literal(value) for value in row) + ")" for row in rows
    )
    updates = ", ".join(
        f"{column} = VALUES({column})" for column in columns if column not in {"driver_id", "event_id"}
    )
    return (
        f"INSERT INTO {table} ({', '.join(columns)})\n"
        f"VALUES\n{values}\n"
        f"ON DUPLICATE KEY UPDATE {updates};\n"
    )


def metadata_sql(release_id: str, stats: SourceFileStats, seeded_at: str) -> str:
    columns = [
        "release_id",
        "source_entity",
        "source_file",
        "checksum_sha256",
        "row_count",
        "seeded_at_utc",
    ]
    row = [
        release_id,
        stats.source_entity,
        stats.source_file,
        stats.checksum,
        stats.row_count,
        seeded_at,
    ]
    updates = ", ".join(
        f"{column} = VALUES({column})" for column in columns if column not in {"release_id", "source_file"}
    )
    return (
        f"INSERT INTO seed_release_files ({', '.join(columns)})\n"
        f"VALUES ({', '.join(mysql_literal(value) for value in row)})\n"
        f"ON DUPLICATE KEY UPDATE {updates};\n"
    )


def batched(rows: Iterable[Sequence[object]], batch_size: int) -> Iterable[list[Sequence[object]]]:
    batch: list[Sequence[object]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def driver_rows(path: Path) -> Iterable[Sequence[object]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in DRIVER_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"drivers.csv is missing columns: {', '.join(missing)}")
        for row in reader:
            yield [
                row["driver_id"].strip(),
                int(row["vendor_id"]),
                row["driver_code"].strip(),
                row["display_name"].strip(),
                row["hire_date"],
                row["employment_status"].strip(),
                row["license_status"].strip(),
                row["license_expiry_date"],
                int(row["experience_years"]),
                row["home_borough"].strip(),
                normalize_timestamp(row["source_updated_at"]),
            ]


def change_rows(path: Path) -> Iterable[Sequence[object]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            missing = [column for column in CHANGE_COLUMNS if column not in record]
            if missing:
                raise ValueError(
                    f"driver_changes.jsonl line {line_number} is missing fields: {', '.join(missing)}"
                )
            yield [
                record["event_id"].strip(),
                record["driver_id"].strip(),
                record["event_type"].strip(),
                normalize_timestamp(record["effective_at"]),
                normalize_timestamp(record["delivered_at"]),
                json.dumps(record["changes"], ensure_ascii=True, sort_keys=True),
                bool(record["is_late_arriving"]),
            ]


def count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def count_jsonl_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


class MysqlRunner:
    def __init__(self, config: MysqlConfig, client: str) -> None:
        self.config = config
        self.client = self._resolve_client(client)

    def _resolve_client(self, requested: str) -> str:
        if requested == "auto":
            if shutil.which("mysql"):
                return "mysql-cli"
            if shutil.which("docker"):
                return "docker-compose"
            raise RuntimeError("No MySQL client found. Install mysql CLI or Docker Compose.")
        if requested == "mysql-cli" and not shutil.which("mysql"):
            raise RuntimeError("mysql CLI was requested but was not found on PATH.")
        if requested == "docker-compose" and not shutil.which("docker"):
            raise RuntimeError("docker-compose client was requested but docker was not found on PATH.")
        return requested

    def run(self, sql: str) -> str:
        if self.client == "mysql-cli":
            command = [
                "mysql",
                "--batch",
                "--raw",
                "--host",
                self.config.host,
                "--port",
                str(self.config.port),
                "--user",
                self.config.user,
                self.config.database,
            ]
            env = os.environ.copy()
            env["MYSQL_PWD"] = self.config.password
        else:
            command = [
                "docker",
                "compose",
                "exec",
                "-T",
                "-e",
                "MYSQL_PWD",
                "mysql_hr",
                "mysql",
                "--batch",
                "--raw",
                "--protocol=TCP",
                "--host",
                "127.0.0.1",
                "--port",
                "3306",
                "--user",
                self.config.user,
                self.config.database,
            ]
            env = os.environ.copy()
            env["MYSQL_PWD"] = self.config.password
        result = subprocess.run(
            command,
            input=sql,
            text=True,
            capture_output=True,
            cwd=REPO_ROOT,
            env=env,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return result.stdout


def truncate_sql() -> str:
    return """
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE driver_changes;
TRUNCATE TABLE drivers;
TRUNCATE TABLE seed_release_files;
SET FOREIGN_KEY_CHECKS = 1;
"""


def apply_tables_ddl(runner: MysqlRunner) -> None:
    ddl_path = REPO_ROOT / "sql" / "source_mysql_hr" / "01_driver_tables.sql"
    runner.run(ddl_path.read_text(encoding="utf-8"))


def source_file_stats(data_root: Path, drivers_path: Path, changes_path: Path) -> list[SourceFileStats]:
    return [
        SourceFileStats(
            source_entity="drivers",
            source_file=drivers_path.relative_to(data_root).as_posix(),
            checksum=sha256_file(drivers_path),
            row_count=count_csv_rows(drivers_path),
        ),
        SourceFileStats(
            source_entity="driver_changes",
            source_file=changes_path.relative_to(data_root).as_posix(),
            checksum=sha256_file(changes_path),
            row_count=count_jsonl_rows(changes_path),
        ),
    ]


def parse_counts(output: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in output.splitlines()[1:]:
        if not line.strip():
            continue
        name, value = line.split("\t", 1)
        counts[name] = int(value)
    return counts


def validate_counts(runner: MysqlRunner, release_id: str, expected: dict[str, int]) -> None:
    output = runner.run(
        f"""
SELECT 'drivers' AS table_name, COUNT(*) AS row_count FROM drivers
UNION ALL
SELECT 'driver_changes', COUNT(*) FROM driver_changes
UNION ALL
SELECT 'seed_release_files', COUNT(*) FROM seed_release_files
WHERE release_id = {mysql_literal(release_id)};
"""
    )
    actual = parse_counts(output)
    for table_name, expected_count in expected.items():
        if actual.get(table_name) != expected_count:
            raise RuntimeError(
                f"Row count validation failed for {table_name}: "
                f"expected {expected_count}, got {actual.get(table_name)}"
            )


def main() -> int:
    args = parse_args()
    load_env_file(REPO_ROOT / ".env")
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be greater than zero")
    config = env_config()
    data_root = resolve_data_root(args.data_root)
    drivers_path, changes_path = require_source_files(data_root)
    stats = source_file_stats(data_root, drivers_path, changes_path)
    runner = MysqlRunner(config, args.client)

    if not args.skip_ddl:
        apply_tables_ddl(runner)

    if args.truncate:
        runner.run(truncate_sql())

    for batch in batched(driver_rows(drivers_path), args.batch_size):
        runner.run(insert_sql("drivers", DRIVER_COLUMNS, batch))

    for batch in batched(change_rows(changes_path), args.batch_size):
        runner.run(insert_sql("driver_changes", CHANGE_COLUMNS, batch))

    seeded_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ", timespec="microseconds")
    for item in stats:
        runner.run(metadata_sql(args.release_id, item, seeded_at))

    validate_counts(
        runner,
        args.release_id,
        {
            "drivers": stats[0].row_count,
            "driver_changes": stats[1].row_count,
            "seed_release_files": len(stats),
        },
    )
    print(
        "Seeded MySQL HR release "
        f"{args.release_id}: drivers={stats[0].row_count}, "
        f"driver_changes={stats[1].row_count}, metadata_files={len(stats)}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
