"""Shared result contracts for pipeline orchestration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    """Return an aware UTC timestamp for result contracts."""
    return datetime.now(timezone.utc)


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


@dataclass(slots=True)
class PipelineStepResult:
    """Uniform result emitted by every orchestration step."""

    pipeline_run_id: str
    batch_id: str
    release_id: str
    step_name: str
    status: str
    started_at: datetime
    finished_at: datetime
    rows_read: int = 0
    loaded: int = 0
    rejected: int = 0
    error_code: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass(slots=True)
class PipelineRunResult:
    """Result contract for one pipeline invocation."""

    pipeline_run_id: str
    batch_id: str
    release_id: str
    status: str
    started_at: datetime
    finished_at: datetime
    steps: list[PipelineStepResult] = field(default_factory=list)

    @classmethod
    def start(cls, release_id: str, batch_id: str | None = None) -> "PipelineRunResult":
        run_id = str(uuid4())
        started_at = utc_now()
        return cls(
            pipeline_run_id=run_id,
            batch_id=batch_id or run_id,
            release_id=release_id,
            status="STARTED",
            started_at=started_at,
            finished_at=started_at,
        )

    def finish(self) -> None:
        self.finished_at = utc_now()
        if any(step.status == "FAILED" for step in self.steps):
            self.status = "FAILED"
        elif self.steps and all(step.status == "DRY_RUN" for step in self.steps):
            self.status = "DRY_RUN"
        elif self.steps and all(step.status in {"SUCCEEDED", "SKIPPED", "DRY_RUN"} for step in self.steps):
            self.status = "SUCCEEDED"
        else:
            self.status = "UNKNOWN"

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))
