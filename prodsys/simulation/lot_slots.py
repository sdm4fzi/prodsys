"""Lot slots: queues that count in whole lots (orders) instead of pieces.

Two sources set the number of lot places of a queue:

* ``QueueData.lot_slots`` — explicit lot places (e.g. trays) of any queue. A
  resource putting a product of a new order into its output blocks while all
  places hold other orders (:func:`lot_key_for_put`, :meth:`Queue.put`);
  transports into an input only start while the order has a place.
* a lot dependency with ``lot_slots`` — for input queues only, the places are
  ``capacity // max_lot_size``.

Input queues without a schedule:

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
        #: admitted products that have not started their last process at the
        #: resource yet (SICK: a tray holds its input place until then — its
        #: pieces may leave the input for a manual step and come back)
        self.pending: dict[str, str] = {}
        self._waiters: list = []

    def occupying(self) -> set[str]:
        orders = {self.order_of_product.get(pid) for pid in self.queue.items}
        orders.update(o for o, n in self.inflight.items() if n > 0)
        orders.update(self.pending.values())
        orders.discard(None)
        return orders  # type: ignore[return-value]

    def started_last_process(self, product_id: str) -> None:
        """The product started its last process at the resource (frees its order's place
        once no other piece of the order is pending)."""
        if self.pending.pop(product_id, None) is not None:
            self.notify()

    def add_waiter(self, controller) -> None:
        if controller not in self._waiters:
            self._waiters.append(controller)

    def notify(self) -> None:
        waiters, self._waiters = self._waiters, []
        for controller in waiters:
            if not controller.state_changed.triggered:
                controller.state_changed.succeed()

    def is_admissible(self, products: dict[str, Optional[str]], max_lot_size: int) -> bool:
        slots = input_lot_places(self.queue, max_lot_size)
        if slots is None:
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
            self.pending[product_id] = order_id

    def on_put(self, item) -> None:
        order_id = self.order_of_product.get(getattr(item, "ID", None))
        if order_id is not None and self.inflight.get(order_id, 0) > 0:
            self.inflight[order_id] -= 1


def input_lot_places(queue: "Queue", max_lot_size: int = 1) -> Optional[int]:
    """Lot places of an input queue: ``lot_slots`` if set, else ``capacity // max_lot_size``
    for lot transports (None = not limited)."""
    explicit = getattr(queue, "lot_slots", None)
    if explicit is not None:
        return int(explicit)
    capacity = getattr(queue, "capacity", math.inf)
    if max_lot_size <= 1 or capacity == math.inf:
        return None
    slots = int(capacity // max_lot_size)
    return slots if slots >= 1 else None


def lot_slot_gate_for(queue: "Queue") -> Optional[LotSlotGate]:
    """Gate of a resource input queue (created on first use)."""
    if getattr(queue, "owner_resource", None) is None or not getattr(queue, "is_input", False):
        return None
    gate = getattr(queue, "lot_slot_gate", None)
    if gate is None:
        gate = LotSlotGate(queue)
        queue.lot_slot_gate = gate
    return gate


def _same_process(a, b) -> bool:
    if a is b:
        return True
    a_data, b_data = getattr(a, "data", None), getattr(b, "data", None)
    if a_data is None or b_data is None:
        return False
    if a_data.ID == b_data.ID:
        return True
    capability = getattr(a_data, "capability", None)
    return capability is not None and capability == getattr(b_data, "capability", None)


def processes_after(process_model_state, current_process) -> list:
    """Processes a product may run next once ``current_process`` is done.

    ``process_model_state`` is the product's live process model instance; its
    marking does not include ``current_process`` yet (the process is still
    being completed). Unknown process models give an empty list.
    """
    from prodsys.simulation.process_models import (
        ListProcessModel,
        PrecedenceGraphProcessModel,
    )

    if isinstance(process_model_state, ListProcessModel):
        index = process_model_state.current_marking
        return list(process_model_state.process_list[index + 1 : index + 2])
    if isinstance(process_model_state, PrecedenceGraphProcessModel):
        current = next(
            (
                node
                for node in process_model_state.nodes
                if not node.marking and _same_process(node.process, current_process)
            ),
            None,
        )
        if current is None:
            return []
        return [
            node.process
            for node in process_model_state.nodes
            if node is not current
            and not node.marking
            and all(pred.marking or pred is current for pred in node.predecessors)
        ]
    return []


def stays_at_resource(entity, resource, current_process=None) -> bool:
    """Does the product's next process run on ``resource`` again?

    Such a product only passes through the resource's output on the way back
    into its input (e.g. a manual and an automatic phase of one station) and
    does not take a lot place there.
    """
    state = getattr(entity, "process_model_state", None)
    current = current_process if current_process is not None else getattr(entity, "current_process", None)
    if state is None or current is None:
        return False
    following = processes_after(state, current)
    offered = getattr(resource, "processes", None) or []
    return any(_same_process(p, q) for p in following for q in offered)


def lot_key_for_put(resource, queue, entity) -> Optional[str]:
    """Lot (order) whose place a product takes when ``resource`` puts it into ``queue``.

    None when the queue has no ``lot_slots``, the product has no order or it
    stays at the resource (see :func:`stays_at_resource`).
    """
    if entity is None or getattr(queue, "lot_slots", None) is None:
        return None
    if stays_at_resource(entity, resource):
        return None
    from prodsys.simulation.schedule_admission import entity_order_id

    return entity_order_id(entity)
