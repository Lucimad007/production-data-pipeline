"""Run extract, transform, and load for the sample orders pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.extract import extract_orders
from pipeline.load import load_orders
from pipeline.transform import transform_orders


def run_pipeline(source: Path, output_dir: Path) -> dict:
    rows = extract_orders(source)
    lines, rejected = transform_orders(rows)
    summary_path = load_orders(lines, rejected, output_dir)
    return json.loads(summary_path.read_text(encoding="utf-8"))


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Run the sample orders pipeline.")
    parser.add_argument(
        "--source",
        type=Path,
        default=root / "data" / "samples" / "orders.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "data" / "output",
    )
    args = parser.parse_args()
    summary = run_pipeline(args.source, args.output)
    print(
        f"accepted={summary['accepted_rows']} "
        f"rejected={summary['rejected_rows']} "
        f"revenue={summary['revenue']:.2f}"
    )


if __name__ == "__main__":
    main()
