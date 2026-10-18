"""Clean raw orders into paid line items."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OrderLine:
    order_id: int
    customer: str
    sku: str
    quantity: int
    unit_price: float
    ordered_at: datetime

    @property
    def amount(self) -> float:
        return round(self.quantity * self.unit_price, 2)


def transform_orders(rows: list[dict[str, str]]) -> tuple[list[OrderLine], list[str]]:
    """Keep the first paid row per order id. Return lines and rejection reasons."""
    seen: set[int] = set()
    lines: list[OrderLine] = []
    rejected: list[str] = []

    for row in rows:
        reason = _reject_reason(row, seen)
        if reason:
            rejected.append(reason)
            continue
        line = OrderLine(
            order_id=int(row["order_id"]),
            customer=row["customer"].strip(),
            sku=row["sku"].strip(),
            quantity=int(row["quantity"]),
            unit_price=float(row["unit_price"]),
            ordered_at=datetime.fromisoformat(row["ordered_at"].replace("Z", "+00:00")),
        )
        seen.add(line.order_id)
        lines.append(line)

    return lines, rejected


def _reject_reason(row: dict[str, str], seen: set[int]) -> str | None:
    order_id = row.get("order_id", "").strip()
    if not order_id.isdigit():
        return f"invalid order_id: {order_id or '<blank>'}"
    if int(order_id) in seen:
        return f"duplicate order_id: {order_id}"
    if row.get("status", "").strip() != "paid":
        return f"order {order_id} status is not paid"
    if not row.get("customer", "").strip():
        return f"order {order_id} missing customer"
    try:
        quantity = int(row["quantity"])
        price = float(row["unit_price"])
    except (KeyError, ValueError):
        return f"order {order_id} has invalid quantity or price"
    if quantity <= 0 or price < 0:
        return f"order {order_id} has non-positive quantity or negative price"
    return None
