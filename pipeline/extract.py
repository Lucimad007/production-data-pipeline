"""Read raw order rows from a CSV file."""

from __future__ import annotations

import csv
from pathlib import Path


def extract_orders(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
