"""Unit tests for warehouse pipeline validation helpers."""

from __future__ import annotations

import unittest

from src.warehouse.pipeline_validation import ValidationResult, assert_results


class TestValidationResult(unittest.TestCase):
    def test_passed_when_values_match(self) -> None:
        self.assertTrue(ValidationResult("count", 3, 3).passed)

    def test_failed_when_values_differ(self) -> None:
        self.assertFalse(ValidationResult("count", 2, 3).passed)

    def test_assert_results_reports_all_failures(self) -> None:
        results = [
            ValidationResult("ok", 1, 1),
            ValidationResult("trip_count", 2, 3),
            ValidationResult("revenue", 10, 11),
        ]

        with self.assertRaisesRegex(AssertionError, "trip_count.*revenue"):
            assert_results(results)


if __name__ == "__main__":
    unittest.main()
