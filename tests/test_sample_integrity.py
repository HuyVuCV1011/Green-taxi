import csv
import json
import unittest
from pathlib import Path


class SampleIntegrityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample = Path(__file__).resolve().parents[1] / "data" / "sample"

    def test_sample_references_are_complete(self):
        with (self.sample / "drivers_sample.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            drivers = {row["driver_id"] for row in csv.DictReader(handle)}

        vehicles = set()
        with (self.sample / "vehicles_sample.jsonl").open(
            encoding="utf-8"
        ) as handle:
            for line in handle:
                vehicles.add(json.loads(line)["vehicle_id"])

        with (self.sample / "shifts_sample.tsv").open(
            encoding="utf-8", newline=""
        ) as handle:
            shifts = {
                row["shift_id"]: row
                for row in csv.DictReader(handle, delimiter="\t")
            }

        with (self.sample / "trip_assignments_sample.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            assignments = list(csv.DictReader(handle))

        self.assertEqual(100, len(assignments))
        for assignment in assignments:
            self.assertIn(assignment["driver_id"], drivers)
            self.assertIn(assignment["vehicle_id"], vehicles)
            self.assertIn(assignment["shift_id"], shifts)
            self.assertEqual(
                assignment["driver_id"],
                shifts[assignment["shift_id"]]["driver_id"],
            )
            self.assertEqual(
                assignment["vehicle_id"],
                shifts[assignment["shift_id"]]["vehicle_id"],
            )

    def test_sample_vendors_exist_in_lookup(self):
        lookup = self.sample.parent / "lookup" / "vendor.csv"
        with lookup.open(encoding="utf-8", newline="") as handle:
            vendors = {
                int(row["vendor_id"])
                for row in csv.DictReader(handle)
            }

        observed = set()
        with (self.sample / "drivers_sample.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            observed.update(
                int(row["vendor_id"])
                for row in csv.DictReader(handle)
            )
        with (self.sample / "vehicles_sample.jsonl").open(
            encoding="utf-8"
        ) as handle:
            observed.update(
                int(json.loads(line)["vendor_id"])
                for line in handle
                if line.strip()
            )
        with (self.sample / "shifts_sample.tsv").open(
            encoding="utf-8", newline=""
        ) as handle:
            observed.update(
                int(row["vendor_id"])
                for row in csv.DictReader(handle, delimiter="\t")
            )

        self.assertIn(0, vendors)
        self.assertTrue(observed.issubset(vendors))


if __name__ == "__main__":
    unittest.main()
