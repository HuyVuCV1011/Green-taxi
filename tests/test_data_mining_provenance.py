"""Unit tests for deterministic, inspectable Data Mining output metadata."""

import unittest

from src.analytics.data_mining import (
    KMEANS_BASELINE_SEED,
    KMEANS_SEEDS,
    _filter_stable_rules,
    rule_dimension_fields,
    run_apriori,
)


class DataMiningProvenanceTests(unittest.TestCase):
    def test_stability_seeds_exclude_the_baseline_fit(self) -> None:
        self.assertNotIn(KMEANS_BASELINE_SEED, KMEANS_SEEDS)
        self.assertEqual(len(KMEANS_SEEDS), len(set(KMEANS_SEEDS)))

    def test_rule_filter_preserves_pre_stability_telemetry(self) -> None:
        rules = [
            {"stability_score": 0.90},
            {"stability_score": 0.70},
            {"stability_score": 0.69},
        ]
        retained, generated_before_stability = _filter_stable_rules(rules, 0.70)
        self.assertEqual(3, generated_before_stability)
        self.assertEqual(2, len(retained))

    def test_rule_dimension_fields_parse_known_prefixes(self) -> None:
        fields = rule_dimension_fields(
            {"pb:Manhattan", "pz:Midtown", "hb:Evening", "dt:Weekday", "vn:Vendor A"},
            "dz:JFK",
        )
        self.assertEqual("Manhattan", fields["antecedent_pickup_borough"])
        self.assertEqual("Midtown", fields["antecedent_pickup_zone"])
        self.assertEqual("Evening", fields["antecedent_hour_bucket"])
        self.assertEqual("Weekday", fields["antecedent_day_type"])
        self.assertEqual("Vendor A", fields["antecedent_vendor"])
        self.assertEqual("JFK", fields["consequent_dropoff_zone"])

    def test_apriori_returns_structured_fields_with_rule(self) -> None:
        transactions = [
            {"pb:Manhattan", "dz:JFK"},
            {"pb:Manhattan", "dz:JFK"},
            {"pb:Manhattan", "dz:JFK"},
        ]
        rules = run_apriori(transactions, min_support=0.5, min_confidence=0.5, min_lift=1.0)
        self.assertTrue(rules)
        self.assertTrue(
            any(
                rule["antecedent_pickup_borough"] == "Manhattan"
                and rule["consequent_dropoff_zone"] == "JFK"
                for rule in rules
            )
        )


if __name__ == "__main__":
    unittest.main()
