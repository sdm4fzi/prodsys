"""Lot options ``order_pure`` / ``lot_slots`` without a plan.

* :class:`prodsys.simulation.lot_slots.LotSlotGate` — an input queue counts in
  whole lots (``capacity // max_lot_size`` orders at a time);
* router order affinity — all products of an order follow the routing decision
  of its first product (per process and per transport hop);
* an end-to-end run of a small lot line released without a full plan.
"""

from __future__ import annotations

from types import SimpleNamespace

from prodsys.models.dependency_data import LotDependencyData
from prodsys.simulation import request as request_module
from prodsys.simulation import runner
from prodsys.simulation.lot_slots import LotSlotGate
from prodsys.simulation.router import Router

from tests.test_prodsys.test_simulation.test_schedule_admission import _ev, _tray_line


def test_lot_slot_gate_counts_orders_not_items() -> None:
    queue = SimpleNamespace(capacity=4, items={})
    gate = LotSlotGate(queue)  # two lots of size 2
    assert gate.is_admissible({"a0": "A", "a1": "A"}, max_lot_size=2)
    gate.admit({"a0": "A", "a1": "A"})
    assert gate.is_admissible({"b0": "B"}, max_lot_size=2)  # second slot (partial lot)
    gate.admit({"b0": "B", "b1": "B"})
    assert not gate.is_admissible({"c0": "C"}, max_lot_size=2)  # both slots taken
    # A's pieces arrive and leave again -> A's slot is free
    for pid in ("a0", "a1"):
        gate.on_put(SimpleNamespace(ID=pid))
    queue.items = {"b0": object()}
    assert gate.is_admissible({"c0": "C"}, max_lot_size=2)
    # single-item transports and unbounded queues are never gated
    assert gate.is_admissible({"x": "X"}, max_lot_size=1)
    assert LotSlotGate(SimpleNamespace(capacity=float("inf"), items={})).is_admissible(
        {"x": "X"}, max_lot_size=2
    )


def test_lot_dependency_flags_default_off_and_keep_hash() -> None:
    dep = LotDependencyData(ID="d", description="", min_lot_size=2, max_lot_size=2)
    assert dep.order_pure is False and dep.lot_slots is False
    flagged = dep.model_copy(update={"order_pure": True, "lot_slots": True})
    assert dep.hash(None) != flagged.hash(None)


def _req(product_id: str, order_id: str, resource_id: str, process_id: str = "p"):
    return SimpleNamespace(
        request_type=request_module.RequestType.PRODUCTION,
        requesting_item=SimpleNamespace(
            info=SimpleNamespace(order_ID=order_id),
            data=SimpleNamespace(ID=product_id),
            routing_heuristic=lambda requests: None,  # keeps the given order
        ),
        process=SimpleNamespace(data=SimpleNamespace(ID=process_id)),
        resource=SimpleNamespace(data=SimpleNamespace(ID=resource_id)),
    )


def _router(order_affinity: bool) -> Router:
    router = object.__new__(Router)
    router.order_affinity = order_affinity
    router._order_routes = {}
    router.schedule_routing_heuristic = None
    router.dependency_move_routing_heuristic = None
    return router


def test_order_affinity_routes_an_order_like_its_first_product() -> None:
    router = _router(order_affinity=True)
    first = router.route_request([_req("a0", "A", "S1"), _req("a0", "A", "S2")])
    assert first.resource.data.ID == "S1"
    # the heuristic would pick S2 first; affinity pins the order to S1
    second = router.route_request([_req("a1", "A", "S2"), _req("a1", "A", "S1")])
    assert second.resource.data.ID == "S1"
    # another order is free
    other = router.route_request([_req("b0", "B", "S2"), _req("b0", "B", "S1")])
    assert other.resource.data.ID == "S2"


def test_without_order_pure_routing_is_unchanged() -> None:
    router = _router(order_affinity=False)
    router.route_request([_req("a0", "A", "S1"), _req("a0", "A", "S2")])
    second = router.route_request([_req("a1", "A", "S2"), _req("a1", "A", "S1")])
    assert second.resource.data.ID == "S2"
    assert router._order_routes == {}


def test_lot_line_runs_without_plan_order_admission() -> None:
    """Orders released at A only (no plan downstream); B's input holds one lot."""
    ps = _tray_line()
    ps.schedule = [
        _ev(0, "A", "a_manual", "P_0", "O1"),
        _ev(0, "A", "a_manual", "P_1", "O1"),
        _ev(0, "A", "a_manual", "P_2", "O2"),
    ]
    sim = runner.Runner(production_system_data=ps)
    sim.initialize_simulation()
    info = sim.run_until_complete(time_range_max=5000)
    assert len(sim.product_factory.finished_products) == 3
    assert info.get("early_exit")
    b_input = next(q for q in sim.resource_factory.get_resource("B").ports if q.data.ID == "B_input")
    assert getattr(b_input, "lot_slot_gate", None) is not None  # lot slots were enforced
