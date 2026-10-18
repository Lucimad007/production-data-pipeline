"""Clean order rows and compute line totals."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrderLine:
    order_id: str
    sku: str
    quantity: int
    unit_price: float

    @property
    def line_total(self) -> float:
        return round(self.quantity * self.unit_price, 2)


def transform_orders(rows: list[dict[str, str]]) -> tuple[list[OrderLine], list[str]]:
    clean: list[OrderLine] = []
    rejected: list[str] = []
    for index, row in enumerate(rows, start=1):
        order_id = (row.get("order_id") or "").strip()
        sku = (row.get("sku") or "").strip()
        try:
            quantity = int(row.get("quantity") or "")
            unit_price = float(row.get("unit_price") or "")
        except ValueError:
            rejected.append(f"row {index}: quantity or unit_price is not numeric")
            continue
        if not order_id or not sku or quantity <= 0 or unit_price < 0:
            rejected.append(f"row {index}: missing id/sku or non-positive quantity")
            continue
        clean.append(
            OrderLine(
                order_id=order_id,
                sku=sku,
                quantity=quantity,
                unit_price=unit_price,
            )
        )
    return clean, rejected
