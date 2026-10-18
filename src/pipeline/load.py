"""Write cleaned lines and a run summary."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from pipeline.transform import OrderLine


def load_orders(
    lines: list[OrderLine],
    rejected: list[str],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    cleaned_path = output_dir / "orders_clean.csv"
    summary_path = output_dir / "summary.json"

    with cleaned_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["order_id", "sku", "quantity", "unit_price", "line_total"],
        )
        writer.writeheader()
        for line in lines:
            writer.writerow(
                {
                    "order_id": line.order_id,
                    "sku": line.sku,
                    "quantity": line.quantity,
                    "unit_price": f"{line.unit_price:.2f}",
                    "line_total": f"{line.line_total:.2f}",
                }
            )

    revenue = round(sum(line.line_total for line in lines), 2)
    summary = {
        "accepted_rows": len(lines),
        "rejected_rows": len(rejected),
        "revenue": revenue,
        "rejections": rejected,
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary_path
