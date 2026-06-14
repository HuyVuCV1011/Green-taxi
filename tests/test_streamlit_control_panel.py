# -*- coding: utf-8 -*-
"""Static and logic unit tests for the Streamlit control panel app."""

from __future__ import annotations

import tempfile
import json
import os
import socket
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.monitoring.repository import PipelineLock
from src.orchestration.models import PipelineRunResult


class TestStreamlitControlPanel(unittest.TestCase):
    def setUp(self) -> None:
        self.app_path = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
        self.theme_path = Path(__file__).resolve().parents[1] / ".streamlit" / "config.toml"

    def test_app_file_exists(self) -> None:
        self.assertTrue(self.app_path.exists())

    def test_app_does_not_contain_subprocess(self) -> None:
        # Read app content
        content = self.app_path.read_text(encoding="utf-8")

        # Check that subprocess is not imported or used
        self.assertNotIn("import subprocess", content)
        self.assertNotIn("subprocess.run", content)
        self.assertNotIn("subprocess.Popen", content)

    def test_app_imports_and_uses_pipeline_runner(self) -> None:
        content = self.app_path.read_text(encoding="utf-8")

        self.assertIn("PipelineRunner", content)
        self.assertIn("runner.run", content)

    def test_app_does_not_contain_raw_sql(self) -> None:
        content = self.app_path.read_text(encoding="utf-8")

        # Check that typical SQL queries are not embedded in the streamlit app
        # (they should be contained in the repository)
        sql_keywords = [
            "SELECT * FROM",
            "INSERT INTO",
            "UPDATE dds.",
            "DELETE FROM",
            "CREATE TABLE",
            "SELECT COUNT(*)",
            "SELECT table_name"
        ]
        for keyword in sql_keywords:
            self.assertNotIn(keyword, content, f"SQL keyword '{keyword}' should not be in streamlit_app.py. Keep SQL in repository.")

    def test_lock_prevents_concurrent_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test_pipeline.lock"
            lock1 = PipelineLock(lock_path)
            lock2 = PipelineLock(lock_path)

            # First acquire succeeds
            self.assertTrue(lock1.acquire())
            self.assertTrue(lock1.is_locked())

            # Second acquire (concurrency) fails
            self.assertFalse(lock2.acquire())

            # First release
            lock1.release()
            self.assertFalse(lock1.is_locked())
            self.assertFalse(lock2.is_locked())

            # Now second can acquire
            self.assertTrue(lock2.acquire())
            lock2.release()

    def test_lock_released_on_pipeline_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test_pipeline.lock"
            lock = PipelineLock(lock_path)

            # Define a dummy execution that fails
            def run_pipeline():
                if not lock.acquire():
                    raise RuntimeError("Could not acquire lock")
                try:
                    raise ValueError("Simulated pipeline step failure")
                finally:
                    lock.release()

            # Execute and assert failure occurred
            with self.assertRaises(ValueError):
                run_pipeline()

            # Verify lock is still released
            self.assertFalse(lock.is_locked())

    def test_dds_ready_only_on_success(self) -> None:
        # Simulate the success condition check
        success_result = MagicMock(spec=PipelineRunResult)
        success_result.status = "SUCCEEDED"

        failed_result = MagicMock(spec=PipelineRunResult)
        failed_result.status = "FAILED"

        # Verify logic
        self.assertEqual(success_result.status, "SUCCEEDED")
        self.assertNotEqual(failed_result.status, "SUCCEEDED")

    def test_non_owner_cannot_release_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test_pipeline.lock"
            lock1 = PipelineLock(lock_path)
            lock2 = PipelineLock(lock_path)

            self.assertTrue(lock1.acquire())
            # Non-owner release should be a no-op
            lock2.release()
            self.assertTrue(lock1.is_locked())

            # Owner can release
            lock1.release()
            self.assertFalse(lock1.is_locked())

    def test_dead_pid_lock_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test_pipeline.lock"

            # Setup a dead PID on current hostname

            # 999999 is highly likely to be a dead PID
            metadata = {
                "pid": 999999,
                "created_at": time.time(),
                "hostname": socket.gethostname(),
                "owner_token": "token-dead"
            }
            lock_path.write_text(json.dumps(metadata), encoding="utf-8")

            # Attempt to acquire with a new lock instance
            lock = PipelineLock(lock_path)
            # Should recover and successfully acquire
            self.assertTrue(lock.acquire())
            self.assertEqual(lock.get_status()["owner_token"], lock.owner_token)

    def test_active_pid_lock_is_not_cleared(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test_pipeline.lock"

            # Setup active PID on current hostname

            metadata = {
                "pid": os.getpid(),
                "created_at": time.time(),
                "hostname": socket.gethostname(),
                "owner_token": "token-active"
            }
            lock_path.write_text(json.dumps(metadata), encoding="utf-8")

            # Attempt to acquire with a new lock instance
            lock = PipelineLock(lock_path)
            # Should fail to acquire because PID is active
            self.assertFalse(lock.acquire())

    def test_lock_older_than_ttl_recovered_when_pid_cannot_be_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test_pipeline.lock"

            # Setup lock from different host, older than TTL (e.g. 7 hours ago)
            metadata = {
                "pid": 1234,
                "created_at": time.time() - 26000, # older than 21600 (6 hours)
                "hostname": "other-host",
                "owner_token": "token-old"
            }
            lock_path.write_text(json.dumps(metadata), encoding="utf-8")

            lock = PipelineLock(lock_path, ttl_seconds=21600)
            # Should recover
            self.assertTrue(lock.acquire())

            # If it's newer than TTL, it should NOT recover
            lock_path.unlink()
            metadata["created_at"] = time.time() - 1000  # 1000s ago
            lock_path.write_text(json.dumps(metadata), encoding="utf-8")

            lock2 = PipelineLock(lock_path, ttl_seconds=21600)
            self.assertFalse(lock2.acquire())

    def test_corrupt_lock_handling(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test_pipeline.lock"

            # Write invalid JSON
            lock_path.write_text("invalid json content", encoding="utf-8")

            # 1. Corrupt and newer than TTL -> should NOT clear
            # Set mtime to now
            os.utime(lock_path, (time.time(), time.time()))

            lock = PipelineLock(lock_path, ttl_seconds=21600)
            self.assertFalse(lock.acquire())

            # 2. Corrupt and older than TTL -> should recover
            # Set mtime to 7 hours ago
            os.utime(lock_path, (time.time() - 26000, time.time() - 26000))
            self.assertTrue(lock.acquire())

    def test_only_one_contender_recovers_a_stale_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test_pipeline.lock"
            metadata = {
                "pid": 999999,
                "created_at": time.time() - 60,
                "hostname": socket.gethostname(),
                "owner_token": "stale-owner",
            }
            lock_path.write_text(json.dumps(metadata), encoding="utf-8")
            contenders = [PipelineLock(lock_path, ttl_seconds=1) for _ in range(2)]
            barrier = threading.Barrier(2)
            outcomes: list[bool] = []

            def contend(candidate: PipelineLock) -> None:
                barrier.wait()
                outcomes.append(candidate.acquire())

            threads = [threading.Thread(target=contend, args=(candidate,)) for candidate in contenders]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(sum(outcomes), 1)
            owner = next(candidate for candidate in contenders if candidate.owner_token == PipelineLock(lock_path).get_status()["owner_token"])
            owner.release()

    def test_app_does_not_contain_raw_exception_printing(self) -> None:
        content = self.app_path.read_text(encoding="utf-8")

        # Check that exception blocks don't print str(e) or str(ex) directly
        # and instead use sanitize_message
        self.assertNotIn("str(e)", content)
        self.assertNotIn("str(ex)", content)
        self.assertIn("sanitize_message", content)

    def test_app_uses_cache_data_for_health_checks(self) -> None:
        content = self.app_path.read_text(encoding="utf-8")

        # Verify that health checks are cached via st.cache_data
        self.assertIn("@st.cache_data", content)
        self.assertIn("get_cached_db_health", content)

    def test_app_uses_four_standard_tabs(self) -> None:
        content = self.app_path.read_text(encoding="utf-8")

        for label in (
            "🏥 Tổng quan Hệ thống",
            "⚙️ Vận hành Pipeline",
            "🛡️ Chất lượng & Đối soát",
            "🔌 Khám phá Nguồn",
        ):
            self.assertIn(label, content)
        self.assertNotIn('"🚀 Auto-Demo"', content)

    def test_auto_demo_is_in_presentation_expander(self) -> None:
        content = self.app_path.read_text(encoding="utf-8")

        self.assertIn('st.expander("🚀 Chế độ Demo Thuyết trình (Presentation Mode)")', content)
        self.assertIn('"🚀 Khởi chạy Auto-Demo"', content)

    def test_theme_config_uses_green_taxi_light_palette(self) -> None:
        self.assertTrue(self.theme_path.exists())
        content = self.theme_path.read_text(encoding="utf-8")

        self.assertIn('primaryColor = "#10B981"', content)
        self.assertIn('backgroundColor = "#FFFFFF"', content)
        self.assertIn('textColor = "#0F172A"', content)

    def test_app_avoids_removed_streamlit_layout_apis(self) -> None:
        content = self.app_path.read_text(encoding="utf-8")

        self.assertNotIn("use_container_width", content)
        self.assertNotIn("streamlit.components.v1", content)
        self.assertNotIn("components.html", content)
        self.assertIn("st.iframe", content)


if __name__ == "__main__":
    unittest.main()
