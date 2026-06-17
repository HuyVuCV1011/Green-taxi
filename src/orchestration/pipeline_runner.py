"""Lightweight orchestration layer over existing ETL loaders."""

from __future__ import annotations

import os
import re
import socket
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from src.orchestration.models import PipelineRunResult, PipelineStepResult, utc_now


DEFAULT_STEPS = [
    "source_health",
    "load_staging",
    "load_nds",
    "load_dds",
    "reconciliation",
    "data_mining",
    "mark_dds_ready",
]

StepHandler = Callable[["PipelineRunner", str], dict[str, int] | None]


def load_demo_steps(path: Path) -> list[str]:
    """Read ordered demo steps from a small YAML file without a YAML framework."""
    if not path.exists():
        return list(DEFAULT_STEPS)

    steps: list[str] = []
    in_steps = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.strip() == "steps:":
            in_steps = True
            continue
        if in_steps and not raw_line.startswith((" ", "-")):
            break
        if in_steps:
            match = re.match(r"\s*-\s*([A-Za-z0-9_\-]+)\s*$", line)
            if match:
                steps.append(match.group(1))
    return steps or list(DEFAULT_STEPS)


def sanitize_error(message: object) -> str:
    """Remove common password/token forms before returning errors to logs or CLI."""
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


class PipelineRunner:
    """Run demo pipeline steps and emit one shared result contract."""

    def __init__(
        self,
        release_id: str,
        *,
        data_root: Path | str = "data",
        demo_config_path: Path | str = "configs/demo/basic_demo.yml",
        step_handlers: Mapping[str, StepHandler] | None = None,
    ) -> None:
        self.release_id = release_id
        self.data_root = Path(data_root)
        self.demo_config_path = Path(demo_config_path)
        self.steps = load_demo_steps(self.demo_config_path)
        self.step_handlers: dict[str, StepHandler] = dict(step_handlers or self._default_handlers())

    def run(
        self,
        *,
        step: str | None = None,
        dry_run: bool = False,
        resume: bool = False,
        previous_results: Iterable[PipelineStepResult] | None = None,
        fail_fast: bool = True,
    ) -> PipelineRunResult:
        selected_steps = self._select_steps(step)
        completed = {
            result.step_name
            for result in previous_results or []
            if result.status in {"SUCCEEDED", "DRY_RUN"}
        }
        run_result = PipelineRunResult.start(self.release_id)

        for step_name in selected_steps:
            if resume and step_name in completed:
                run_result.steps.append(self._make_result(run_result, step_name, "SKIPPED"))
                continue
            if dry_run:
                run_result.steps.append(self._make_result(run_result, step_name, "DRY_RUN"))
                continue
            step_result = self._execute_step(run_result, step_name)
            run_result.steps.append(step_result)
            if fail_fast and step_result.status == "FAILED":
                break

        run_result.finish()
        return run_result

    def _select_steps(self, step: str | None) -> list[str]:
        unknown = [name for name in self.steps if name not in self.step_handlers]
        if unknown:
            raise ValueError(f"Unknown configured pipeline step(s): {', '.join(unknown)}")
        if step is None:
            return list(self.steps)
        if step not in self.step_handlers:
            raise ValueError(f"Unknown pipeline step: {step}")
        return [step]

    def _execute_step(self, run_result: PipelineRunResult, step_name: str) -> PipelineStepResult:
        started_at = utc_now()
        try:
            counts = self.step_handlers[step_name](self, run_result.batch_id) or {}
            return PipelineStepResult(
                pipeline_run_id=run_result.pipeline_run_id,
                batch_id=run_result.batch_id,
                release_id=self.release_id,
                step_name=step_name,
                status="SUCCEEDED",
                started_at=started_at,
                finished_at=utc_now(),
                rows_read=int(counts.get("rows_read", 0)),
                loaded=int(counts.get("loaded", 0)),
                rejected=int(counts.get("rejected", 0)),
            )
        except Exception as exc:  # noqa: BLE001 - contract must capture arbitrary loader failures.
            return PipelineStepResult(
                pipeline_run_id=run_result.pipeline_run_id,
                batch_id=run_result.batch_id,
                release_id=self.release_id,
                step_name=step_name,
                status="FAILED",
                started_at=started_at,
                finished_at=utc_now(),
                error_code=exc.__class__.__name__,
                error_message=sanitize_error(exc),
            )

    def _make_result(self, run_result: PipelineRunResult, step_name: str, status: str) -> PipelineStepResult:
        timestamp = utc_now()
        return PipelineStepResult(
            pipeline_run_id=run_result.pipeline_run_id,
            batch_id=run_result.batch_id,
            release_id=self.release_id,
            step_name=step_name,
            status=status,
            started_at=timestamp,
            finished_at=timestamp,
        )

    def _default_handlers(self) -> dict[str, StepHandler]:
        return {
            "source_health": _source_health,
            "load_staging": _load_staging,
            "load_nds": _load_nds,
            "load_dds": _load_dds,
            "reconciliation": _reconciliation,
            "data_mining": _data_mining,
            "mark_dds_ready": _mark_dds_ready,
        }


def _source_health(runner: PipelineRunner, batch_id: str) -> dict[str, int]:
    checks = (
        ("MYSQL_HR_HOST", "127.0.0.1", "MYSQL_HR_PORT", "3307"),
        ("MONGODB_FLEET_HOST", "127.0.0.1", "MONGODB_FLEET_PORT", "27018"),
        ("POSTGRES_DISPATCH_HOST", "127.0.0.1", "POSTGRES_DISPATCH_PORT", "5433"),
        ("POSTGRES_WAREHOUSE_HOST", "127.0.0.1", "POSTGRES_WAREHOUSE_PORT", "5434"),
    )
    for host_key, default_host, port_key, default_port in checks:
        host = os.getenv(host_key, default_host)
        port = int(os.getenv(port_key, default_port))
        with socket.create_connection((host, port), timeout=3):
            pass
    return {"rows_read": len(checks), "loaded": len(checks), "rejected": 0}


def _load_staging(runner: PipelineRunner, batch_id: str) -> dict[str, int]:
    from src.ingestion.staging_loader import StagingLoader

    loader = StagingLoader(release_id=runner.release_id)
    expected_total = 0
    loaded_total = 0
    success = True
    error_msg = None
    try:
        loader.start_batch_log(source_system=None, input_params={"release_id": runner.release_id, "source": "all"})
        for load_call in (
            loader.load_hr,
            loader.load_fleet,
            loader.load_dispatch,
            lambda: loader.load_lookup(runner.data_root),
            lambda: loader.load_tlc(runner.data_root),
        ):
            rows_read, loaded = load_call()
            expected_total += rows_read
            loaded_total += loaded
    except Exception as exc:  # noqa: BLE001
        success = False
        error_msg = sanitize_error(exc)
        raise
    finally:
        status = "SUCCEEDED" if success and all(stat[4] != "FAILED" for stat in loader.stats) else "FAILED"
        try:
            loader.complete_batch_log(status=status, expected_rows=expected_total, loaded_rows=loaded_total, error_msg=error_msg)
        finally:
            loader.close_all()
    return {"rows_read": expected_total, "loaded": loaded_total, "rejected": max(expected_total - loaded_total, 0)}


def _load_nds(runner: PipelineRunner, batch_id: str) -> dict[str, int]:
    from src.warehouse.nds_loader import NDSLoader

    loader = NDSLoader(release_id=runner.release_id)
    expected_total = 0
    loaded_total = 0
    rejected_total = 0
    success = True
    error_msg = None
    try:
        loader.init_nds_schema()
        loader.start_batch_log(source_system=None, input_params={"release_id": runner.release_id})
        for load_call in (
            loader.load_vendor,
            loader.load_location,
            loader.load_drivers,
            loader.load_driver_changes,
            loader.load_vehicles,
            loader.load_shifts,
            loader.load_trips,
            loader.load_trip_assignments,
        ):
            rows_read, loaded, rejected = load_call()
            expected_total += rows_read
            loaded_total += loaded
            rejected_total += rejected
    except Exception as exc:  # noqa: BLE001
        success = False
        error_msg = sanitize_error(exc)
        raise
    finally:
        status = "SUCCEEDED" if success and all(stat[5] != "FAILED" for stat in loader.stats) else "FAILED"
        try:
            loader.complete_batch_log(status=status, expected_rows=expected_total, loaded_rows=loaded_total, error_msg=error_msg)
        finally:
            loader.close_all()
    return {"rows_read": expected_total, "loaded": loaded_total, "rejected": rejected_total}


def _load_dds(runner: PipelineRunner, batch_id: str) -> dict[str, int]:
    from src.warehouse.dds_loader import DDSLoader

    loader = DDSLoader(release_id=runner.release_id)
    loaded_total = 0
    rejected_total = 0
    success = True
    error_msg = None
    try:
        loader.start_batch_log(input_params={"release_id": runner.release_id})
        for load_call in (
            loader.load_dim_date,
            loader.load_dim_time,
            loader.load_dim_vendor,
            loader.load_dim_location,
        ):
            loaded, rejected = load_call()
            loaded_total += loaded
            rejected_total += rejected
        for load_call in (loader.load_dim_driver, loader.load_dim_vehicle):
            rows_read, new_versions, noop = load_call()
            loaded_total += new_versions
        loader.run_dq_gate2()
        for load_call in (loader.load_fact_driver_trip, loader.load_fact_driver_shift):
            loaded, rejected = load_call()
            loaded_total += loaded
            rejected_total += rejected
    except Exception as exc:  # noqa: BLE001
        success = False
        error_msg = sanitize_error(exc)
        raise
    finally:
        try:
            loader.complete_batch_log(status="SUCCEEDED" if success else "FAILED", loaded_rows=loaded_total, error_msg=error_msg)
        finally:
            loader.close_all()
    return {"rows_read": loaded_total + rejected_total, "loaded": loaded_total, "rejected": rejected_total}


def _reconciliation(runner: PipelineRunner, batch_id: str) -> dict[str, int]:
    from src.warehouse.dds_loader import DDSLoader
    from src.warehouse.pipeline_validation import validate_release_reconciliation

    loader = DDSLoader(release_id=runner.release_id)
    try:
        results = validate_release_reconciliation(loader.connect_warehouse(), runner.release_id)
    finally:
        loader.close_all()
    failed = [result for result in results if not result.passed]
    if failed:
        names = ", ".join(result.name for result in failed)
        raise RuntimeError(f"Reconciliation failed: {names}")
    return {"rows_read": len(results), "loaded": len(results), "rejected": 0}


def _mark_dds_ready(runner: PipelineRunner, batch_id: str) -> dict[str, int]:
    # Contract-only marker. Readiness is represented by the orchestration result,
    # not by adding new warehouse schema objects.
    return {"rows_read": 0, "loaded": 1, "rejected": 0}


def _data_mining(runner: PipelineRunner, batch_id: str) -> dict[str, int]:
    from src.analytics.data_mining import execute_data_mining
    from src.warehouse.dds_loader import DDSLoader

    analytics_sql_path = Path(__file__).resolve().parents[2] / "sql" / "analytics" / "01_certified_datasets.sql"
    loader = DDSLoader(release_id=runner.release_id)
    try:
        conn = loader.connect_warehouse()
        with conn.cursor() as cur:
            cur.execute(analytics_sql_path.read_text(encoding="utf-8"))
        conn.commit()
        counts = execute_data_mining(conn)
        conn.commit()
        return counts
    finally:
        loader.close_all()
