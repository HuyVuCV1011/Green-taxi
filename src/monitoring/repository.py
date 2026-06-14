# -*- coding: utf-8 -*-
"""Monitoring Repository for querying source databases and warehouse metadata."""

from __future__ import annotations

import os
import re
import errno
import json
import socket
import time
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Generator
from dotenv import load_dotenv

try:
    import pymysql
except ImportError:
    pymysql = None

try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None

try:
    import psycopg2
except ImportError:
    psycopg2 = None


# Configure path and load env
REPO_ROOT = Path(__file__).resolve().parents[2]
env_path = REPO_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path)


def sanitize_message(message: object) -> str:
    """Sanitize passwords, tokens, and URIs containing credentials from messages."""
    text = str(message)
    secret_values = [
        value
        for key, value in os.environ.items()
        if value and any(marker in key.upper() for marker in ("PASSWORD", "TOKEN", "SECRET", "KEY"))
    ]
    for value in sorted(secret_values, key=len, reverse=True):
        if len(value) >= 4:
            text = text.replace(value, "***")
    text = re.sub(
        r"(?i)((?:password|passwd|pwd|token|secret|api[_-]?key|access[_-]?key)\s*[=:]\s*)[^\s,;]+",
        r"\1***",
        text,
    )
    text = re.sub(r"(://[^:/\s]+:)[^@/\s]+(@)", r"\1***\2", text)
    return text


def sanitize_for_display(value: Any) -> Any:
    """Recursively sanitize values before rendering them in the UI."""
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if re.search(r"(?i)(password|passwd|pwd|token|secret|api[_-]?key|credential)", str(key)):
                sanitized[key] = "***"
            else:
                sanitized[key] = sanitize_for_display(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_for_display(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_for_display(item) for item in value)
    if isinstance(value, str):
        return sanitize_message(value)
    return value


def is_dds_ready(result: Any, dry_run: bool = False) -> bool:
    """Determine if the dimensional data store is fully populated and verified."""
    if dry_run:
        return False
    if not result:
        return False
    if getattr(result, "status", None) != "SUCCEEDED":
        return False

    has_ready_step = False
    for step in getattr(result, "steps", []):
        if getattr(step, "step_name", None) == "mark_dds_ready":
            if getattr(step, "status", None) == "SUCCEEDED":
                has_ready_step = True
            else:
                return False  # Any failure/skip on this step implies not ready
    return has_ready_step


class PipelineLock:
    """A file-based lock with JSON metadata and stale lock recovery."""

    def __init__(self, lock_file_path: Path | str, ttl_seconds: float = 21600) -> None:
        self.lock_file_path = Path(lock_file_path)
        self.recovery_lock_path = self.lock_file_path.with_name(f"{self.lock_file_path.name}.recovery")
        self.ttl_seconds = ttl_seconds
        self.owner_token = str(uuid.uuid4())

    def acquire(self) -> bool:
        metadata = {
            "pid": os.getpid(),
            "created_at": time.time(),
            "hostname": socket.gethostname(),
            "owner_token": self.owner_token
        }

        try:
            self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
            return self._create_lock(metadata)
        except FileExistsError:
            return self._recover_stale_lock(metadata)
        except Exception:
            return False

    def _create_lock(self, metadata: dict[str, Any]) -> bool:
        fd = os.open(self.lock_file_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(fd, json.dumps(metadata).encode("utf-8"))
        finally:
            os.close(fd)
        return True

    def _recover_stale_lock(self, metadata: dict[str, Any]) -> bool:
        recovery_fd: int | None = None
        try:
            recovery_fd = os.open(
                self.recovery_lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError:
            return False
        except OSError:
            return False

        try:
            # Re-check while holding the recovery guard. Only this process may
            # remove a stale lock; contenders can only race on exclusive create.
            if not self._is_stale():
                return False
            self.lock_file_path.unlink(missing_ok=True)
            try:
                return self._create_lock(metadata)
            except FileExistsError:
                return False
        except OSError:
            return False
        finally:
            if recovery_fd is not None:
                os.close(recovery_fd)
            self.recovery_lock_path.unlink(missing_ok=True)

    def release(self) -> None:
        try:
            if self.lock_file_path.exists():
                content = self.lock_file_path.read_text(encoding="utf-8")
                data = json.loads(content)
                if data.get("owner_token") == self.owner_token:
                    self.lock_file_path.unlink(missing_ok=True)
        except Exception:
            pass

    def is_locked(self) -> bool:
        return self.lock_file_path.exists()

    def get_status(self) -> dict[str, Any]:
        if not self.lock_file_path.exists():
            return {"locked": False, "pid": None, "created_at": None, "hostname": None, "owner_token": None}
        try:
            content = self.lock_file_path.read_text(encoding="utf-8")
            data = json.loads(content)
            return {
                "locked": True,
                "pid": data.get("pid"),
                "created_at": data.get("created_at"),
                "hostname": data.get("hostname"),
                "owner_token": data.get("owner_token")
            }
        except Exception:
            try:
                mtime = os.path.getmtime(self.lock_file_path)
            except Exception:
                mtime = None
            return {
                "locked": True,
                "pid": None,
                "created_at": mtime,
                "hostname": None,
                "owner_token": None,
                "corrupt": True
            }

    def _is_stale(self) -> bool:
        if not self.lock_file_path.exists():
            return True

        try:
            content = self.lock_file_path.read_text(encoding="utf-8")
            data = json.loads(content)
        except Exception:
            # Metadata is corrupt. Delete only if modification time has exceeded TTL.
            try:
                mtime = os.path.getmtime(self.lock_file_path)
                return (time.time() - mtime) > self.ttl_seconds
            except Exception:
                return True

        pid = data.get("pid")
        created_at = data.get("created_at")
        hostname = data.get("hostname")

        if not isinstance(pid, int) or not isinstance(created_at, (int, float)) or not isinstance(hostname, str):
            # Corrupt fields
            try:
                mtime = os.path.getmtime(self.lock_file_path)
                return (time.time() - mtime) > self.ttl_seconds
            except Exception:
                return True

        current_hostname = socket.gethostname()
        if hostname == current_hostname:
            # Same machine: verify if PID is still active
            return not self._is_pid_running(pid)
        else:
            # Different machine: cannot check PID, fallback to TTL from creation time
            return (time.time() - created_at) > self.ttl_seconds

    def _is_pid_running(self, pid: int) -> bool:
        if pid <= 0:
            return False
        if os.name == "nt":
            try:
                import ctypes

                process_query_limited_information = 0x1000
                handle = ctypes.windll.kernel32.OpenProcess(
                    process_query_limited_information,
                    False,
                    pid,
                )
                if not handle:
                    return False
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            except Exception:
                # An inconclusive process check must not remove a possibly
                # active lock.
                return True
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError as e:
            # Windows raises OSError with winerror 87 if process is dead
            winerror = getattr(e, "winerror", 0)
            if winerror == 87:
                return False
            if e.errno == errno.ESRCH:
                return False
            return True


class MonitoringRepository:
    """Centralized repository for database health monitoring, data exploration, and audit queries."""

    def __init__(self, repo_root: Path | str | None = None) -> None:
        self.repo_root = Path(repo_root) if repo_root else REPO_ROOT
        self.entities_config_path = self.repo_root / "configs" / "pipeline" / "entities.yml"

    def get_mysql_config(self) -> dict[str, Any]:
        return {
            "host": os.getenv("MYSQL_HR_HOST", "127.0.0.1"),
            "port": int(os.getenv("MYSQL_HR_PORT", "3307")),
            "database": os.getenv("MYSQL_HR_DATABASE", "green_taxi_hr"),
            "user": os.getenv("MYSQL_HR_USER", "green_taxi_hr_app"),
            "password": os.getenv("MYSQL_HR_PASSWORD", "change_me_hr"),
        }

    def get_mongo_config(self) -> dict[str, Any]:
        host = os.getenv("MONGODB_FLEET_HOST", "127.0.0.1")
        port = int(os.getenv("MONGODB_FLEET_PORT", "27018"))
        user = os.getenv("MONGODB_FLEET_ROOT_USER", "green_taxi_fleet_admin")
        password = os.getenv("MONGODB_FLEET_ROOT_PASSWORD", "change_me_fleet_root")
        database = os.getenv("MONGODB_FLEET_DATABASE", "green_taxi_fleet")
        uri = f"mongodb://{user}:{password}@{host}:{port}/{database}?authSource=admin"
        return {
            "uri": uri,
            "database": database,
            "host": host,
            "port": port
        }

    def get_postgres_dispatch_config(self) -> dict[str, Any]:
        return {
            "host": os.getenv("POSTGRES_DISPATCH_HOST", "127.0.0.1"),
            "port": int(os.getenv("POSTGRES_DISPATCH_PORT", "5433")),
            "database": os.getenv("POSTGRES_DISPATCH_DATABASE", "green_taxi_dispatch"),
            "user": os.getenv("POSTGRES_DISPATCH_USER", "green_taxi_dispatch_app"),
            "password": os.getenv("POSTGRES_DISPATCH_PASSWORD", "change_me_dispatch"),
        }

    def get_postgres_warehouse_config(self) -> dict[str, Any]:
        return {
            "host": os.getenv("POSTGRES_WAREHOUSE_HOST", "127.0.0.1"),
            "port": int(os.getenv("POSTGRES_WAREHOUSE_PORT", "5434")),
            "database": os.getenv("POSTGRES_WAREHOUSE_DATABASE", "green_taxi_warehouse"),
            "user": os.getenv("POSTGRES_WAREHOUSE_USER", "green_taxi_warehouse_app"),
            "password": os.getenv("POSTGRES_WAREHOUSE_PASSWORD", "change_me_warehouse"),
        }

    @contextmanager
    def mysql_conn(self) -> Generator[Any, None, None]:
        if pymysql is None:
            raise ImportError("pymysql package is not installed")
        config = self.get_mysql_config()
        conn = pymysql.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database=config["database"],
            connect_timeout=3
        )
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def mongo_client(self) -> Generator[Any, None, None]:
        if MongoClient is None:
            raise ImportError("pymongo package is not installed")
        config = self.get_mongo_config()
        client = MongoClient(config["uri"], serverSelectionTimeoutMS=3000)
        try:
            yield client
        finally:
            client.close()

    @contextmanager
    def postgres_dispatch_conn(self) -> Generator[Any, None, None]:
        if psycopg2 is None:
            raise ImportError("psycopg2 package is not installed")
        config = self.get_postgres_dispatch_config()
        conn = psycopg2.connect(
            host=config["host"],
            port=config["port"],
            dbname=config["database"],
            user=config["user"],
            password=config["password"],
            connect_timeout=3
        )
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def postgres_warehouse_conn(self) -> Generator[Any, None, None]:
        if psycopg2 is None:
            raise ImportError("psycopg2 package is not installed")
        config = self.get_postgres_warehouse_config()
        conn = psycopg2.connect(
            host=config["host"],
            port=config["port"],
            dbname=config["database"],
            user=config["user"],
            password=config["password"],
            connect_timeout=3
        )
        try:
            yield conn
        finally:
            conn.close()

    def test_connections(self) -> dict[str, dict[str, Any]]:
        """Test connectivity of all source and warehouse databases."""
        results = {}

        # 1. MySQL HR
        mysql_conf = self.get_mysql_config()
        try:
            with self.mysql_conn():
                results["mysql_hr"] = {
                    "connected": True,
                    "host": mysql_conf["host"],
                    "port": mysql_conf["port"],
                    "database": mysql_conf["database"],
                    "error": None
                }
        except Exception as e:
            results["mysql_hr"] = {
                "connected": False,
                "host": mysql_conf["host"],
                "port": mysql_conf["port"],
                "database": mysql_conf["database"],
                "error": self._sanitize_msg(str(e))
            }

        # 2. MongoDB Fleet
        mongo_conf = self.get_mongo_config()
        try:
            with self.mongo_client() as client:
                client.admin.command("ping")
                results["mongodb_fleet"] = {
                    "connected": True,
                    "host": mongo_conf["host"],
                    "port": mongo_conf["port"],
                    "database": mongo_conf["database"],
                    "error": None
                }
        except Exception as e:
            results["mongodb_fleet"] = {
                "connected": False,
                "host": mongo_conf["host"],
                "port": mongo_conf["port"],
                "database": mongo_conf["database"],
                "error": self._sanitize_msg(str(e))
            }

        # 3. PostgreSQL Dispatch
        dispatch_conf = self.get_postgres_dispatch_config()
        try:
            with self.postgres_dispatch_conn():
                results["postgres_dispatch"] = {
                    "connected": True,
                    "host": dispatch_conf["host"],
                    "port": dispatch_conf["port"],
                    "database": dispatch_conf["database"],
                    "error": None
                }
        except Exception as e:
            results["postgres_dispatch"] = {
                "connected": False,
                "host": dispatch_conf["host"],
                "port": dispatch_conf["port"],
                "database": dispatch_conf["database"],
                "error": self._sanitize_msg(str(e))
            }

        # 4. PostgreSQL Warehouse
        wh_conf = self.get_postgres_warehouse_config()
        try:
            with self.postgres_warehouse_conn():
                results["postgres_warehouse"] = {
                    "connected": True,
                    "host": wh_conf["host"],
                    "port": wh_conf["port"],
                    "database": wh_conf["database"],
                    "error": None
                }
        except Exception as e:
            results["postgres_warehouse"] = {
                "connected": False,
                "host": wh_conf["host"],
                "port": wh_conf["port"],
                "database": wh_conf["database"],
                "error": self._sanitize_msg(str(e))
            }

        return results

    def get_source_sample(self, system: str, entity: str, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch a limited whitelisted data sample from simulated source databases."""
        allowed_entities = {
            "mysql_hr": {"drivers", "driver_changes"},
            "mongodb_fleet": {"vehicles"},
            "postgres_dispatch": {"shifts", "trip_assignments"},
        }

        if system not in allowed_entities or entity not in allowed_entities[system]:
            raise ValueError(f"Unauthorized source query: system={system}, entity={entity}")

        safe_limit = max(1, min(limit, 100))

        if system == "mysql_hr":
            with self.mysql_conn() as conn:
                with conn.cursor() as cursor:
                    # Limit is parameterized to prevent injection
                    cursor.execute(f"SELECT * FROM {entity} LIMIT %s", (safe_limit,))
                    columns = [desc[0] for desc in cursor.description]
                    return [self._serialize_row(dict(zip(columns, row))) for row in cursor.fetchall()]

        elif system == "mongodb_fleet":
            with self.mongo_client() as client:
                db = client[self.get_mongo_config()["database"]]
                docs = list(db[entity].find().limit(safe_limit))
                for doc in docs:
                    if "_id" in doc:
                        doc["_id"] = str(doc["_id"])
                return [self._serialize_row(doc) for doc in docs]

        elif system == "postgres_dispatch":
            with self.postgres_dispatch_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"SELECT * FROM {entity} LIMIT %s", (safe_limit,))
                    columns = [desc[0] for desc in cursor.description]
                    return [self._serialize_row(dict(zip(columns, row))) for row in cursor.fetchall()]

        return []

    def get_warehouse_row_counts(self) -> dict[str, dict[str, int]]:
        """Fetch current row counts for Staging, NDS, and DDS tables dynamically from entities registry."""
        tables = self._parse_entities_config()
        counts = {"staging": {}, "nds": {}, "dds": {}}

        try:
            with self.postgres_warehouse_conn() as conn:
                for schema in ("staging", "nds", "dds"):
                    for table in tables[schema]:
                        counts[schema][table] = self._get_table_count(conn, table)
        except Exception:
            # If warehouse is entirely unreachable, return -1 for all
            for schema in ("staging", "nds", "dds"):
                for table in tables[schema]:
                    counts[schema][table] = -1

        return counts

    def get_reconciliation_results(self, release_id: str) -> list[dict[str, Any]]:
        """Invoke existing reconciliation validation suite and return serialization-friendly results."""
        from src.warehouse.pipeline_validation import validate_release_reconciliation
        try:
            with self.postgres_warehouse_conn() as conn:
                results = validate_release_reconciliation(conn, release_id)
                return [
                    {
                        "name": res.name,
                        "actual": str(res.actual),
                        "expected": str(res.expected),
                        "passed": res.passed
                    }
                    for res in results
                ]
        except Exception as e:
            return [{
                "name": "Connection Error",
                "actual": "ERROR",
                "expected": "SUCCESS",
                "passed": False,
                "error": self._sanitize_msg(str(e))
            }]

    def get_etl_batches(self, limit: int = 5) -> list[dict[str, Any]] | None:
        """Retrieve recent ETL batches from warehouse audit metadata."""
        safe_limit = max(1, min(limit, 100))
        query = """
            SELECT
                batch_id,
                release_id,
                pipeline_name,
                batch_status,
                batch_started_at,
                batch_completed_at,
                source_system,
                row_count_expected,
                row_count_loaded,
                error_message
            FROM audit.metadata_etl_batch
            ORDER BY batch_started_at DESC
            LIMIT %s
        """
        try:
            with self.postgres_warehouse_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (safe_limit,))
                    columns = [desc[0] for desc in cursor.description]
                    return [self._serialize_row(dict(zip(columns, row))) for row in cursor.fetchall()]
        except Exception:
            return None

    def get_dq_issues_summary(self) -> list[dict[str, Any]] | None:
        """Get summary of Data Quality issues grouped by rule and severity."""
        query = """
            SELECT rule_code, severity, COUNT(*) as issue_count
            FROM dq.dq_issue
            GROUP BY rule_code, severity
            ORDER BY issue_count DESC
        """
        try:
            with self.postgres_warehouse_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception:
            return None

    def get_quarantine_records_summary(self) -> list[dict[str, Any]] | None:
        """Get summary of Quarantine records grouped by entity and rule."""
        query = """
            SELECT source_entity, error_rule_code, COUNT(*) as record_count
            FROM dq.quarantine_record
            GROUP BY source_entity, error_rule_code
            ORDER BY record_count DESC
        """
        try:
            with self.postgres_warehouse_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception:
            return None

    def get_quarantine_records(self, limit: int = 10) -> list[dict[str, Any]] | None:
        """Fetch recent quarantine records with payloads sanitized for display."""
        safe_limit = max(1, min(limit, 100))
        query = """
            SELECT
                quarantine_id,
                batch_id,
                release_id,
                source_system_code,
                source_entity,
                source_record_id,
                error_rule_code,
                raw_payload,
                quarantined_at
            FROM dq.quarantine_record
            ORDER BY quarantined_at DESC
            LIMIT %s
        """
        try:
            with self.postgres_warehouse_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (safe_limit,))
                    columns = [desc[0] for desc in cursor.description]
                    return [self._serialize_row(dict(zip(columns, row))) for row in cursor.fetchall()]
        except Exception:
            return None

    def _get_table_count(self, conn: Any, table_name: str) -> int:
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                return cursor.fetchone()[0]
        except Exception:
            conn.rollback()
            return -1

    def _parse_entities_config(self) -> dict[str, list[str]]:
        """Parse entities.yml without using PyYAML framework."""
        if not self.entities_config_path.exists():
            return {"staging": [], "nds": [], "dds": []}

        staging_tables = []
        nds_tables = []
        dds_tables = []

        for line in self.entities_config_path.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            if "staging_table:" in line:
                val = line.split("staging_table:", 1)[1].strip()
                for t in val.split(","):
                    t = t.strip()
                    if t:
                        staging_tables.append(t)
            elif "nds_table:" in line:
                val = line.split("nds_table:", 1)[1].strip()
                for t in val.split(","):
                    t = t.strip()
                    if t:
                        nds_tables.append(t)
            elif "dds_table:" in line:
                val = line.split("dds_table:", 1)[1].strip()
                for t in val.split(","):
                    t = t.strip()
                    if t:
                        dds_tables.append(t)

        return {
            "staging": sorted(list(set(staging_tables))),
            "nds": sorted(list(set(nds_tables))),
            "dds": sorted(list(set(dds_tables)))
        }

    def _serialize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Convert datetime, Decimal, UUIDs into json-serializable/string forms."""
        serialized = {}
        for k, v in row.items():
            if isinstance(v, (datetime, date)):
                serialized[k] = v.isoformat()
            elif isinstance(v, Decimal):
                serialized[k] = float(v)
            elif hasattr(v, "hex"):  # UUID
                serialized[k] = str(v)
            elif isinstance(v, dict):
                serialized[k] = self._serialize_row(v)
            elif isinstance(v, list):
                serialized[k] = [self._serialize_row(i) if isinstance(i, dict) else i for i in v]
            else:
                serialized[k] = v
        return serialized

    def _sanitize_msg(self, text: str) -> str:
        """Strip password or secrets patterns from string messages."""
        return sanitize_message(text)
