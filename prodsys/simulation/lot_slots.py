"""Lot slots for input queues without a schedule.

A lot dependency with ``lot_slots`` (see
:class:`prodsys.models.dependency_data.LotDependencyData`) makes the input
queues it feeds count in whole lots: a queue with ``capacity`` places holds
at most ``capacity // max_lot_size`` orders at a time, even if their lots are
only partly filled (e.g. an order-pure carrier with 10 of 34 places used).
Without this rule several partial lots of different orders share one input
and lines with small buffers block.

For resources planned with ``strict_schedule_admission`` the same rule is
enforced by :class:`prodsys.simulation.schedule_admission.ScheduleAdmission`
(with the more precise release "all products started their last planned
process").  :class:`LotSlotGate` covers everything else: an order occupies a
slot while any of its products is in the queue or on its way into it.
Transports inside one resource (output → input between two of its processes)
are not lot transports and are never gated.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from prodsys.simulation.port import Queue


class LotSlotGate:
    """Order slots of one input queue (see module docstring)."""

    def __init__(self, queue: "Queue") -> None:
        self.queue = queue
        #: order id -> products admitted but not yet put into the queue
        self.inflight: dict[str, int] = {}
        #: product id -> order id for products admitted through the gate
        self.order_of_product: dict[str, str] = {}

    def occupying(self) -> set[str]:
        orders = {self.order_of_product.get(pid) for pid in self.queue.items}
        orders.update(o for o, n in self.inflight.items() if n > 0)
        orders.discard(None)
        return orders  # type: ignore[return-value]

    def is_admissible(self, products: dict[str, Optional[str]], max_lot_size: int) -> bool:
        capacity = getattr(self.queue, "capacity", math.inf)
        if max_lot_size <= 1 or capacity == math.inf:
            return True
        slots = int(capacity // max_lot_size)
        if slots < 1:
            return True
        orders = self.occupying()
        orders.update(o for o in products.values() if o is not None)
        return len(orders) <= slots

    def admit(self, products: dict[str, Optional[str]]) -> None:
        for product_id, order_id in products.items():
            if order_id is None:
                continue
            self.order_of_product[product_id] = order_id
            self.inflight[order_id] = self.inflight.get(order_id, 0) + 1

    def on_put(self, item) -> None:
        order_id = self.order_of_product.get(getattr(item, "ID", None))
        if order_id is not None and self.inflight.get(order_id, 0) > 0:
            self.inflight[order_id] -= 1


def lot_slot_gate_for(queue: "Queue") -> Optional[LotSlotGate]:
    """Gate of a resource input queue (created on first use)."""
    if getattr(queue, "owner_resource", None) is None or not getattr(queue, "is_input", False):
        return None
    gate = getattr(queue, "lot_slot_gate", None)
    if gate is None:
        gate = LotSlotGate(queue)
        queue.lot_slot_gate = gate
    return gate
