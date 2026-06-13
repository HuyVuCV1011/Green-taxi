import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.generate_synthetic_sources import (
    Shift,
    calculate_shift_end,
    calculate_total_idle_minutes,
    write_vendor_lookup,
)


class GeneratorShiftLogicTest(unittest.TestCase):
    def make_shift(self) -> Shift:
        first_pickup = datetime(2020, 1, 1, 8, 0)
        return Shift(
            shift_id="SHF0000000001",
            driver_id="DRV000001",
            vehicle_id="VEH000001",
            vendor_id=1,
            start=first_pickup - timedelta(minutes=30),
            first_pickup=first_pickup,
            first_zone=1,
            last_dropoff=datetime(2020, 1, 1, 10, 0),
            last_zone=2,
            trip_count=2,
            occupied_minutes=60.0,
            idle_minutes=30.0,
        )

    def test_dynamic_shift_end_uses_half_of_short_gap(self):
        shift = self.make_shift()
        next_pickup = shift.last_dropoff + timedelta(minutes=40)

        end = calculate_shift_end(shift, 30, next_pickup)

        self.assertEqual(
            shift.last_dropoff + timedelta(minutes=20),
            end,
        )

    def test_total_idle_includes_start_and_end_buffers(self):
        shift = self.make_shift()
        end = shift.last_dropoff + timedelta(minutes=30)

        total_idle = calculate_total_idle_minutes(shift, end)

        self.assertEqual(90.0, total_idle)

    def test_vendor_lookup_always_contains_legacy_pool(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.csv"
            target = root / "target.csv"
            source.write_text(
                'vendor_id, vendor_name\n'
                '1,"Creative Mobile Technologies, LLC"\n'
                '2,"VeriFone Inc"\n',
                encoding="utf-8",
            )

            write_vendor_lookup(source, target)

            self.assertEqual(
                [
                    "vendor_id,vendor_name",
                    "0,Legacy / Unknown Pool",
                    '1,"Creative Mobile Technologies, LLC"',
                    "2,VeriFone Inc",
                ],
                target.read_text(encoding="utf-8").splitlines(),
            )


if __name__ == "__main__":
    unittest.main()
