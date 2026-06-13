import unittest

from scripts import seed_mysql_hr


class SeedMysqlHrTest(unittest.TestCase):
    def test_mysql_literal_escapes_strings(self):
        self.assertEqual("'O''Brien \\\\ HR'", seed_mysql_hr.mysql_literal("O'Brien \\ HR"))
        self.assertEqual("1", seed_mysql_hr.mysql_literal(True))
        self.assertEqual("NULL", seed_mysql_hr.mysql_literal(None))

    def test_insert_sql_uses_upsert_key(self):
        sql = seed_mysql_hr.insert_sql(
            "drivers",
            ["driver_id", "display_name"],
            [["DRV000001", "Synthetic Driver"]],
        )

        self.assertIn("INSERT INTO drivers", sql)
        self.assertIn("ON DUPLICATE KEY UPDATE", sql)
        self.assertIn("display_name = VALUES(display_name)", sql)
        self.assertNotIn("driver_id = VALUES(driver_id)", sql)

    def test_parse_counts(self):
        output = "table_name\trow_count\ndrivers\t860\ndriver_changes\t77\n"

        self.assertEqual(
            {"drivers": 860, "driver_changes": 77},
            seed_mysql_hr.parse_counts(output),
        )


if __name__ == "__main__":
    unittest.main()
