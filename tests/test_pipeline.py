import sqlite3
import unittest
from pathlib import Path

from pipeline.run import run

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "sample_orders.csv"


class PipelineTest(unittest.TestCase):
    def test_sample_orders(self) -> None:
        database = ROOT / "data" / "output" / "test_orders.db"
        if database.exists():
            database.unlink()

        extracted, rejected, stored = run(SOURCE, database)

        self.assertEqual(extracted, 8)
        self.assertEqual(rejected, 5)
        self.assertEqual(stored, 3)

        with sqlite3.connect(database) as connection:
            amounts = dict(connection.execute("SELECT order_id, amount FROM order_lines"))
        self.assertEqual(amounts, {1001: 39.0, 1002: 42.0, 1005: 126.0})


if __name__ == "__main__":
    unittest.main()
