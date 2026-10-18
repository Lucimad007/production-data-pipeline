"""Run the sample orders pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.extract import extract_orders
from pipeline.load import load_orders
from pipeline.transform import transform_orders

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "sample_orders.csv"
DEFAULT_DATABASE = ROOT / "data" / "output" / "orders.db"


def run(source: Path, database: Path) -> tuple[int, int, int]:
    rows = extract_orders(source)
    lines, rejected = transform_orders(rows)
    stored = load_orders(lines, database)
    return len(rows), len(rejected), stored


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the sample orders pipeline")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()

    extracted, rejected, stored = run(args.source, args.database)
    print(f"extracted={extracted} rejected={rejected} stored={stored}")
    print(f"database={args.database}")


if __name__ == "__main__":
    main()
