"""Write transformed order lines into SQLite."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pipeline.transform import OrderLine

_SCHEMA = """
CREATE TABLE IF NOT EXISTS order_lines (
    order_id INTEGER PRIMARY KEY,
    customer TEXT NOT NULL,
    sku TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    amount REAL NOT NULL,
    ordered_at TEXT NOT NULL
)
"""


def load_orders(lines: list[OrderLine], database: Path) -> int:
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.execute(_SCHEMA)
        connection.executemany(
            """
            INSERT INTO order_lines (
                order_id, customer, sku, quantity, unit_price, amount, ordered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(order_id) DO UPDATE SET
                customer = excluded.customer,
                sku = excluded.sku,
                quantity = excluded.quantity,
                unit_price = excluded.unit_price,
                amount = excluded.amount,
                ordered_at = excluded.ordered_at
            """,
            [
                (
                    line.order_id,
                    line.customer,
                    line.sku,
                    line.quantity,
                    line.unit_price,
                    line.amount,
                    line.ordered_at.isoformat(),
                )
                for line in lines
            ],
        )
        connection.commit()
        count = connection.execute("SELECT COUNT(*) FROM order_lines").fetchone()[0]
    return int(count)
