"""Unit tests for deterministic, inspectable Data Mining output metadata."""

import unittest

from src.analytics.data_mining import rule_dimension_fields, run_apriori


class DataMiningProvenanceTests(unittest.TestCase):
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
