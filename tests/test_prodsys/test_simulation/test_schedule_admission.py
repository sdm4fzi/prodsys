"""Schedule-conform tray admission and order-pure tray lots.

Covers :mod:`prodsys.simulation.schedule_admission`, the order lookup of
:class:`~prodsys.simulation.lot_handler.LotHandler` and a small end-to-end
tray line whose plan would deadlock without the admission gate.
"""

from __future__ import annotations

from types import SimpleNamespace

from prodsys.models.order_data import OrderData
from prodsys.models.performance_data import Event
from prodsys.models.production_system_data import ProductionSystemData
from prodsys.simulation import runner
from prodsys.simulation.lot_handler import _work_request_order_id
from prodsys.simulation.schedule_admission import ScheduleAdmission, entity_order_id


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def _event(product: str, process: str = "p", state_type: str = "Production"):
    return SimpleNamespace(product=product, process=process, state_type=state_type)


def _admission(schedule):
    controller = SimpleNamespace(
        resource_schedule=schedule, completed_schedule_indices=set()
    )
    return controller, ScheduleAdmission(controller)


def _queue(capacity):
    return SimpleNamespace(capacity=capacity)


def test_entity_order_id_prefers_info_over_id() -> None:
    entity = SimpleNamespace(
        info=SimpleNamespace(order_ID="WR007"), data=SimpleNamespace(ID="Product_J5_AFx_Bus_3")
    )
    assert entity_order_id(entity) == "WR007"
    # Lots use the release order only when they are order-pure ...
    assert _work_request_order_id(entity, use_order_info=True) == "WR007"
    # ... otherwise only the legacy id pattern (unchanged behaviour of main).
    assert _work_request_order_id(entity) is None
    legacy = SimpleNamespace(info=None, data=SimpleNamespace(ID="Product_J8_VFS_WR024_9"))
    assert entity_order_id(legacy) == "WR024"
    assert _work_request_order_id(legacy) == "WR024"


def test_admission_follows_plan_order() -> None:
    _, adm = _admission([_event("a0"), _event("a1"), _event("b0")])
    q = _queue(float("inf"))
    assert not adm.is_admissible({"b0": "B"}, q)
    assert not adm.is_admissible({"a1": "A"}, q)
    # A lot carrying the whole order is fine even if its head is not first.
    assert adm.is_admissible({"a1": "A", "a0": "A"}, q)
    adm.admit({"a0": "A", "a1": "A"})
    assert adm.is_admissible({"b0": "B"}, q)


def test_unplanned_products_are_not_gated() -> None:
    _, adm = _admission([_event("a0")])
    assert adm.is_admissible({"x": "X"}, _queue(1))


def test_lot_slot_held_until_last_process_started() -> None:
    schedule = [
        _event("a0", "manual"),
        _event("a0", "auto"),
        _event("b0", "manual"),
        _event("b0", "auto"),
    ]
    controller, adm = _admission(schedule)
    q = _queue(2)  # one lot of size 2
    adm.admit({"a0": "A"})
    # without lot slots the queue counts items only
    assert adm.is_admissible({"b0": "B"}, q, max_lot_size=2)
    assert not adm.is_admissible({"b0": "B"}, q, max_lot_size=2, lot_slots=True)
    controller.completed_schedule_indices.add(0)  # a0 manual started
    assert not adm.is_admissible({"b0": "B"}, q, max_lot_size=2, lot_slots=True)
    controller.completed_schedule_indices.add(1)  # a0 auto (last) started
    assert adm.is_admissible({"b0": "B"}, q, max_lot_size=2, lot_slots=True)
    # Returning pieces of an admitted order are always allowed.
    assert adm.is_admissible({"a0": "A"}, q, max_lot_size=1, lot_slots=True)


def test_waiters_are_woken() -> None:
    _, adm = _admission([_event("a0")])
    event = SimpleNamespace(triggered=False)
    event.succeed = lambda: setattr(event, "triggered", True)
    waiter = SimpleNamespace(state_changed=event)
    adm.add_waiter(waiter)
    adm.admit({"a0": "A"})
    assert event.triggered


# ---------------------------------------------------------------------------
# End to end: order-pure tray line
# ---------------------------------------------------------------------------

TRAY = 2


def _tm(tid: str, value: float) -> dict:
    return {
        "ID": tid,
        "description": "",
        "distribution_function": "constant",
        "location": value,
        "scale": 0.0,
        "batch_size": 100,
    }


def _port(qid: str, cap: int, itype: str, loc) -> dict:
    return {
        "ID": qid,
        "description": "",
        "capacity": cap,
        "location": loc,
        "interface_type": itype,
        "port_type": "queue",
        "dependency_ids": [],
    }


def _station(rid: str, loc, processes) -> dict:
    return {
        "ID": rid,
        "description": "",
        "location": loc,
        "capacity": 1,
        "process_ids": processes,
        "process_capacities": [1] * len(processes),
        "control_policy": "FIFO",
        "controller": "PipelineController",
        "ports": [f"{rid}_input", f"{rid}_output"],
    }


def _tray_line() -> ProductionSystemData:
    """src -> A (manual+auto, worker) -> B -> sink; B's input holds one tray.

    A's output holds two trays so an order finished early can wait there.
    """
    loc = {"A": [1.0, 0.0], "B": [3.0, 0.0]}
    nodes = {"n0": [0.0, 0.0], "nA": loc["A"], "nB": loc["B"], "n5": [5.0, 0.0]}
    pairs = [
        ("src_output", "n0"),
        ("n0", "nA"),
        ("nA", "A_input"),
        ("nA", "A_output"),
        ("nA", "nB"),
        ("nB", "B_input"),
        ("nB", "B_output"),
        ("nB", "n5"),
        ("n5", "sink_input"),
    ]
    links = [list(p) for a, b in pairs for p in ((a, b), (b, a))]
    data = {
        "ID": "tray_line",
        "time_unit": "s",
        "time_model_data": [
            _tm("tm_a_manual", 10.0),
            _tm("tm_a_auto", 20.0),
            _tm("tm_b_auto", 50.0),
            _tm("tm_attend", 1.0),
            _tm("tm_arrival", 1e9),
            {"ID": "tm_ltp", "description": "", "speed": 1.0, "reaction_time": 0.0, "metric": "manhattan"},
        ],
        "process_data": [
            {"ID": "a_manual", "description": "", "time_model_id": "tm_a_manual", "type": "ProductionProcesses", "dependency_ids": ["dep_worker"]},
            {"ID": "a_auto", "description": "", "time_model_id": "tm_a_auto", "type": "ProductionProcesses"},
            {"ID": "b_auto", "description": "", "time_model_id": "tm_b_auto", "type": "ProductionProcesses"},
            {"ID": "attend", "description": "", "time_model_id": "tm_attend", "type": "ProductionProcesses"},
            {
                "ID": "ltp",
                "description": "",
                "time_model_id": "tm_ltp",
                "type": "LinkTransportProcesses",
                "links": links,
                "capability": "carry",
                "dependency_ids": ["dep_tray"],
            },
        ],
        "dependency_data": [
            {
                "ID": "dep_worker",
                "description": "",
                "dependency_type": "process",
                "required_process": "attend",
                "interaction_node": "nA",
                "position_type": "absolute",
                "per_lot": True,
            },
            {
                "ID": "dep_tray",
                "description": "",
                "dependency_type": "lot",
                "min_lot_size": 1,
                "max_lot_size": 1,
                "order_pure": True,
                "lot_slots": True,
                "link_lot_sizes": [
                    {"origin": "A_output", "target": "B_input", "min_lot_size": TRAY, "max_lot_size": TRAY}
                ],
            },
        ],
        "node_data": [{"ID": k, "description": "", "location": v} for k, v in nodes.items()],
        "port_data": [
            _port("src_output", 50, "output", [0.0, 0.0]),
            _port("sink_input", 0, "input", [5.0, 0.0]),
            _port("W_queue", 0, "input_output", [0.0, 0.0]),
            _port("A_input", TRAY, "input", loc["A"]),
            _port("A_output", 2 * TRAY, "output", loc["A"]),
            _port("B_input", TRAY, "input", loc["B"]),
            _port("B_output", TRAY, "output", loc["B"]),
        ],
        "resource_data": [
            _station("A", loc["A"], ["a_manual", "a_auto"]),
            _station("B", loc["B"], ["b_auto"]),
            {
                "ID": "W",
                "description": "",
                "location": [0.0, 0.0],
                "capacity": TRAY,
                "process_ids": ["ltp", "attend"],
                "process_capacities": [TRAY, TRAY],
                "control_policy": "FIFO",
                "controller": "PipelineController",
                "ports": ["W_queue"],
            },
        ],
        "product_data": [
            {
                "ID": "P",
                "description": "",
                "type": "P",
                "transport_process": "ltp",
                "processes": {"a_manual": ["a_auto"], "a_auto": ["b_auto"], "b_auto": []},
            }
        ],
        "source_data": [
            {
                "ID": "src",
                "description": "",
                "location": [0.0, 0.0],
                "product_type": "P",
                "time_model_id": "tm_arrival",
                "routing_heuristic": "FIFO",
                "ports": ["src_output"],
            }
        ],
        "sink_data": [
            {"ID": "sink", "description": "", "location": [5.0, 0.0], "product_type": "P", "ports": ["sink_input"]}
        ],
        "order_data": [
            OrderData(ID="O1", ordered_products=[{"product_type": "P", "quantity": 2}], order_time=0.0, release_time=0.0, due_time=1e5, priority=1),
            OrderData(ID="O2", ordered_products=[{"product_type": "P", "quantity": 1}], order_time=0.0, release_time=0.0, due_time=1e5, priority=1),
        ],
    }
    return ProductionSystemData(**data)


def _ev(t, resource, process, product, order):
    return Event(
        **{
            "Time": t,
            "Resource": resource,
            "State": process,
            "State Type": "Production",
            "Activity": "start state",
            "Product": product,
            "Expected End Time": t,
            "process": process,
            "Order ID": order,
        }
    )


def test_later_planned_tray_waits_upstream_instead_of_deadlocking() -> None:
    """O2 (planned second at B) finishes A first; it must not take B's only tray slot.

    Without the admission gate O2's tray enters B's input, B waits for O1 per
    plan, and O1's tray can never get in — the classic buffer deadlock.
    """
    ps = _tray_line()
    plan = {
        # product: [(time, resource, process)]
        "P_2": [(0, "W", "ltp"), (1, "A", "a_manual"), (11, "W", "ltp"), (12, "A", "a_auto"),
                (240, "W", "ltp"), (242, "B", "b_auto"), (292, "W", "ltp")],
        "P_0": [(11, "W", "ltp"), (33, "A", "a_manual"), (43, "W", "ltp"), (44, "A", "a_auto"),
                (130, "W", "ltp"), (132, "B", "b_auto"), (182, "W", "ltp")],
        "P_1": [(43, "W", "ltp"), (65, "A", "a_manual"), (75, "W", "ltp"), (76, "A", "a_auto"),
                (130, "W", "ltp"), (182, "B", "b_auto"), (232, "W", "ltp")],
    }
    order = {"P_0": "O1", "P_1": "O1", "P_2": "O2"}
    events = [
        _ev(t, res, proc, pid, order[pid]) for pid, steps in plan.items() for t, res, proc in steps
    ]
    ps.schedule = sorted(events, key=lambda e: e.time)
    sim = runner.Runner(production_system_data=ps, strict_schedule_admission=True)
    sim.initialize_simulation()
    info = sim.run_until_complete(time_range_max=5000)
    assert len(sim.product_factory.finished_products) == 3
    assert info.get("early_exit")


def test_admission_is_opt_in() -> None:
    """Without ``strict_schedule_admission`` no resource gets a plan-order gate."""
    from prodsys.simulation.schedule_admission import admission_for_queue

    ps = _tray_line()
    ps.schedule = [_ev(0, "A", "a_manual", "P_0", "O1")]
    sim = runner.Runner(production_system_data=ps)
    sim.initialize_simulation()
    resource = sim.resource_factory.get_resource("A")
    assert resource.controller.strict_schedule_admission is False
    for queue in resource.ports:
        assert admission_for_queue(queue) is None


def test_transport_without_route_link_releases_its_state() -> None:
    """A route with no link (already at the target) must not leak a reserved slot.

    Leaked reservations permanently shrank a worker's transport capacity; once
    below the tray size a full tray lot could never start (line standstill).
    """
    from prodsys.simulation.process_handlers.dependency_process_handler import (
        DependencyProcessHandler,
    )
    from prodsys.simulation.process_handlers.transport_process_handler import (
        TransportProcessHandler,
    )

    state = SimpleNamespace(reserved=True, process=None)
    list(TransportProcessHandler(env=None).run_transport(state, None, [object()], empty_transport=True))
    assert state.reserved is False

    state = SimpleNamespace(reserved=True, process=None)
    list(DependencyProcessHandler(env=None).run_transport(state, [object()], True, None))
    assert state.reserved is False
