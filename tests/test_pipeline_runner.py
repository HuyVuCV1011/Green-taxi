from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.orchestration.models import PipelineStepResult, utc_now
from src.orchestration.pipeline_runner import PipelineRunner, load_demo_steps, sanitize_error


def handler(rows_read: int = 1, loaded: int = 1, rejected: int = 0):
    def _handler(runner: PipelineRunner, batch_id: str) -> dict[str, int]:
        return {"rows_read": rows_read, "loaded": loaded, "rejected": rejected}

    return _handler


class PipelineRunnerTest(unittest.TestCase):
    def make_runner(self, steps: list[str], handlers: dict | None = None) -> PipelineRunner:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        config_path = Path(tmp.name) / "basic_demo.yml"
        config_path.write_text("steps:\n" + "".join(f"  - {step}\n" for step in steps), encoding="utf-8")
        return PipelineRunner(
            "release-test",
            demo_config_path=config_path,
            step_handlers=handlers or {step: handler() for step in steps},
        )

    def test_step_order_from_demo_config(self) -> None:
        runner = self.make_runner(["source_health", "load_staging", "load_nds"])

        result = runner.run()

        self.assertEqual([step.step_name for step in result.steps], ["source_health", "load_staging", "load_nds"])
        self.assertEqual(result.status, "SUCCEEDED")

    def test_fail_fast_stops_after_failure(self) -> None:
        def fail(runner: PipelineRunner, batch_id: str) -> dict[str, int]:
            raise RuntimeError("password=secret should be hidden")

        runner = self.make_runner(
            ["source_health", "load_staging", "load_nds"],
            {"source_health": handler(), "load_staging": fail, "load_nds": handler()},
        )

        result = runner.run()

        self.assertEqual([step.step_name for step in result.steps], ["source_health", "load_staging"])
        self.assertEqual(result.steps[-1].status, "FAILED")
        self.assertNotIn("secret", result.steps[-1].error_message or "")

    def test_resume_skips_successful_previous_steps(self) -> None:
        runner = self.make_runner(["source_health", "load_staging"])
        now = utc_now()
        previous = [
            PipelineStepResult(
                pipeline_run_id="run-1",
                batch_id="batch-1",
                release_id="release-test",
                step_name="source_health",
                status="SUCCEEDED",
                started_at=now,
                finished_at=now,
            )
        ]

        result = runner.run(resume=True, previous_results=previous)

        self.assertEqual(result.steps[0].status, "SKIPPED")
        self.assertEqual(result.steps[1].status, "SUCCEEDED")

    def test_result_serialization(self) -> None:
        runner = self.make_runner(["source_health"])

        payload = runner.run().to_dict()

        self.assertIn("pipeline_run_id", payload)
        self.assertIsInstance(payload["started_at"], str)
        self.assertIsInstance(payload["steps"][0]["started_at"], str)
        self.assertEqual(payload["steps"][0]["rows_read"], 1)

    def test_dry_run_does_not_execute_handlers(self) -> None:
        def fail_if_called(runner: PipelineRunner, batch_id: str) -> dict[str, int]:
            raise AssertionError("handler should not execute")

        runner = self.make_runner(["source_health", "load_staging"], {"source_health": fail_if_called, "load_staging": fail_if_called})

        result = runner.run(dry_run=True)

        self.assertEqual([step.status for step in result.steps], ["DRY_RUN", "DRY_RUN"])
        self.assertEqual(result.status, "SUCCEEDED")

    def test_error_sanitization(self) -> None:
        message = sanitize_error("postgres://user:super-secret@localhost/db password=abc123 token=def456")

        self.assertNotIn("super-secret", message)
        self.assertNotIn("abc123", message)
        self.assertNotIn("def456", message)
        self.assertIn("password=***", message)
        self.assertIn("token=***", message)

    def test_load_demo_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.yml"
            path.write_text("name: demo\nsteps:\n  - source_health\n  - reconciliation\n", encoding="utf-8")

            self.assertEqual(load_demo_steps(path), ["source_health", "reconciliation"])


if __name__ == "__main__":
    unittest.main()
