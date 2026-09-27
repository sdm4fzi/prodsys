"""Schedule-conform admission of transports into a scheduled resource's input.

With a schedule, a resource starts its production requests strictly in plan
order (see :meth:`Controller._schedule_next_event_blocks_request`).  Transports
into its input queue, however, used to run as soon as a product was routed and
the queue had free space.  On lines with bounded input buffers this lets
products that are planned *later* fill the queue while the product the
resource waits for cannot get in — a deadlock (e.g. a tray of a later work
request occupying all 34 places of a station whose next planned product is
still upstream).

:class:`ScheduleAdmission` closes that gap for every resource that has a
schedule:

* **Plan order** — a transport into the resource's input queue is admitted
  only when every product planned on the resource *before* the transported
  product(s) has already been admitted (in the queue, on its way, or started).
* **Tray slots** — for lot transports (e.g. an order-pure tray moved via a
  :class:`~prodsys.models.dependency_data.LinkLotDependencyData` link) the
  queue holds at most ``capacity // max_lot_size`` orders at a time.  An order
  occupies its slot from admission until each of its products has *started
  its last planned process* on the resource; returning products (output →
  input shuffles between two processes on the same resource) therefore never
  compete with the next tray.

Transport controllers blocked by a gate register as waiters and are woken
whenever the gated resource starts a scheduled process or admits products.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Iterable, Optional

from prodsys.simulation.product_info import extract_order_id_from_product_id

if TYPE_CHECKING:
    from prodsys.simulation.control import Controller
    from prodsys.simulation.port import Queue


_PRODUCTION_STATE_TYPES = ("Production", "ProcessModel")


def entity_order_id(entity) -> Optional[str]:
    """Order id of a product entity (``info.order_ID``, else parsed from its id)."""
    if entity is None:
        return None
    info = getattr(entity, "info", None)
    order_id = getattr(info, "order_ID", None) if info is not None else None
    if order_id:
        return str(order_id)
    data = getattr(entity, "data", None)
    pid = getattr(data, "ID", None) if data is not None else None
    return extract_order_id_from_product_id(pid) if pid else None


class ScheduleAdmission:
    """Plan-order / tray-slot gate for the input queue of one scheduled resource."""

    def __init__(self, controller: "Controller") -> None:
        self.controller = controller
        self.position: dict[str, int] = {}
        self.sequence: list[str] = []
        self.last_index: dict[str, int] = {}
        #: product -> order id as planned (schedule ``Order ID``)
        self._order_of: dict[str, Optional[str]] = {}
        for idx, event in enumerate(controller.resource_schedule or []):
            if getattr(event, "state_type", None) not in _PRODUCTION_STATE_TYPES:
                continue
            product = getattr(event, "product", None)
            if not product:
                continue
            self._order_of.setdefault(product, getattr(event, "order_id", None))
            if product not in self.position:
                self.position[product] = len(self.sequence)
                self.sequence.append(product)
            self.last_index[product] = idx
        self.admitted: set[str] = set()
        self._cursor = 0
        #: order id -> products admitted but not yet started their last process here
        self._occupying: dict[str, set[str]] = {}
        self._waiters: list["Controller"] = []

    # ------------------------------------------------------------------ query

    def _advance_cursor(self) -> None:
        while self._cursor < len(self.sequence) and self.sequence[self._cursor] in self.admitted:
            self._cursor += 1

    def _prune_occupancy(self) -> None:
        completed = self.controller.completed_schedule_indices
        for order_id in list(self._occupying):
            pending = {
                p
                for p in self._occupying[order_id]
                if self.last_index.get(p) is not None and self.last_index[p] not in completed
            }
            if pending:
                self._occupying[order_id] = pending
            else:
                del self._occupying[order_id]

    def quick_check(self, product_id: str, order_id: Optional[str]) -> Optional[bool]:
        """Cheap verdict for a single-product request, ``None`` if undecided.

        ``True``: not gated here.  ``False``: an earlier planned product of a
        *different* order is still outstanding, so no lot of this product's
        order can be admitted either.  Avoids scanning lot candidates for the
        many requests that simply have to wait their turn.
        """
        pos = self.position.get(product_id)
        if pos is None:
            return True
        if product_id in self.admitted:
            return True
        self._advance_cursor()
        if self._cursor >= pos:
            return None
        blocker = self.sequence[self._cursor]
        if order_id is None or self._order_of.get(blocker) in (None, order_id):
            return None
        return False

    def plans(self, product_ids: Iterable[str]) -> bool:
        return any(p in self.position for p in product_ids)

    def is_admissible(
        self,
        products: dict[str, Optional[str]],
        queue: "Queue",
        max_lot_size: int = 1,
    ) -> bool:
        """``products`` maps product id -> order id of the (lot) transport."""
        indices = [self.position[p] for p in products if p in self.position]
        if not indices:
            return True
        if all(p in self.admitted for p in products):
            return True
        self._advance_cursor()
        first = min(indices)
        for k in range(self._cursor, first):
            planned = self.sequence[k]
            if planned not in self.admitted and planned not in products:
                return False
        capacity = getattr(queue, "capacity", math.inf)
        if max_lot_size > 1 and capacity != math.inf:
            slots = int(capacity // max_lot_size)
            if slots >= 1:
                self._prune_occupancy()
                orders = set(self._occupying)
                orders.update(o for o in products.values() if o is not None)
                if len(orders) > slots:
                    return False
        return True

    # ----------------------------------------------------------------- update

    def admit(self, products: dict[str, Optional[str]]) -> None:
        changed = False
        for product_id, order_id in products.items():
            if product_id not in self.position or product_id in self.admitted:
                continue
            self.admitted.add(product_id)
            key = order_id if order_id is not None else product_id
            self._occupying.setdefault(key, set()).add(product_id)
            changed = True
        if changed:
            self.notify()

    def add_waiter(self, controller: "Controller") -> None:
        if controller is not self.controller and controller not in self._waiters:
            self._waiters.append(controller)

    def notify(self) -> None:
        waiters, self._waiters = self._waiters, []
        for controller in waiters:
            if not controller.state_changed.triggered:
                controller.state_changed.succeed()


def admission_for_queue(queue: "Queue") -> Optional[ScheduleAdmission]:
    """Gate of the scheduled resource that owns ``queue`` as an input, if any."""
    owner = getattr(queue, "owner_resource", None)
    if owner is None or not getattr(queue, "is_input", False):
        return None
    controller = getattr(owner, "controller", None)
    if controller is None or not getattr(controller, "resource_schedule", None):
        return None
    admission = getattr(controller, "admission", None)
    if admission is None:
        admission = ScheduleAdmission(controller)
        controller.admission = admission
    return admission
