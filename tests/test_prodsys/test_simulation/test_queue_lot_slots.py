"""``QueueData.lot_slots``: queues that count lot places (orders) besides pieces.

* :class:`~prodsys.simulation.port.Queue` — a put of a new order waits for a
  free lot place; taking the last item of an order frees its place;
* :func:`~prodsys.simulation.lot_slots.processes_after` /
  :func:`~prodsys.simulation.lot_slots.stays_at_resource` — products whose next
  process runs on the same resource do not take a place in its output;
* an end-to-end tray line whose station output holds a single tray.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import simpy

from prodsys.models.port_data import QueueData
from prodsys.simulation import runner
from prodsys.simulation.lot_slots import lot_key_for_put, processes_after, stays_at_resource
from prodsys.simulation.port import Queue
from prodsys.simulation.process_models import ListProcessModel, PrecedenceGraphProcessModel

from tests.test_prodsys.test_simulation.test_schedule_admission import _ev, _tray_line


def _item(item_id: str):
    return SimpleNamespace(ID=item_id)


def test_queue_data_lot_slots_default_and_hash() -> None:
    plain = QueueData(ID="q", description="", capacity=68)
    trays = QueueData(ID="q", description="", capacity=68, lot_slots=2)
    assert plain.lot_slots is None
    assert plain.hash() != trays.hash()
    with pytest.raises(ValueError):
        QueueData(ID="q", description="", capacity=68, lot_slots=0)


def test_put_of_new_order_waits_for_a_lot_place() -> None:
    env = simpy.Environment()
    queue = Queue(env, QueueData(ID="q", description="", capacity=68, lot_slots=1))
    done: dict[str, float] = {}

    def put(item_id: str, order: str, delay: float = 0.0):
        yield env.timeout(delay)
        yield from queue.put(_item(item_id), lot_key=order, wait_for_lot_place=True)
        done[item_id] = env.now

    def take(item_id: str, at: float):
        yield env.timeout(at)
        yield from queue.get(item_id)

    env.process(put("a0", "A"))
    env.process(put("b0", "B", delay=1))  # second order: no place left
    env.process(put("a1", "A", delay=2))  # same order joins its place
    env.process(take("a0", at=5))
    env.process(take("a1", at=7))  # last item of A frees the place
    env.run(until=20)
    assert done == {"a0": 0, "a1": 2, "b0": 7}
    assert queue.occupied_lots() == {"B"}
    # items without an order are never limited by lot places
    assert queue.has_lot_place(None)


def test_queue_without_lot_slots_ignores_lot_keys() -> None:
    env = simpy.Environment()
    queue = Queue(env, QueueData(ID="q", description="", capacity=68))
    for i, order in enumerate("ABC"):
        env.process(queue.put(_item(f"x{i}"), lot_key=order, wait_for_lot_place=True))
    env.run(until=1)
    assert len(queue.items) == 3 and queue.occupied_lots() == set()


def _proc(process_id: str):
    return SimpleNamespace(data=SimpleNamespace(ID=process_id, capability=None, type="ProductionProcesses"))


def test_processes_after_list_and_graph_models() -> None:
    manual, auto, other = _proc("manual"), _proc("auto"), _proc("other")
    listed = ListProcessModel([manual, auto, other])
    assert processes_after(listed, manual) == [auto]

    graph = PrecedenceGraphProcessModel()
    graph.add_node(manual, successors=[auto], predecessors=[])
    graph.add_node(auto, successors=[other], predecessors=[manual])
    graph.add_node(other, successors=[], predecessors=[auto])
    assert processes_after(graph, manual) == [auto]
    graph.update_marking_from_transition(manual)
    assert processes_after(graph, auto) == [other]

    station = SimpleNamespace(processes=[manual, auto])
    product = SimpleNamespace(process_model_state=listed, current_process=manual)
    assert stays_at_resource(product, station)  # manual -> auto on the same station
    product.current_process = auto
    listed.update_marking_from_transition(manual)
    assert not stays_at_resource(product, station)  # auto -> other leaves the station

    queue = SimpleNamespace(lot_slots=1)
    product.info = SimpleNamespace(order_ID="O1")
    assert lot_key_for_put(station, queue, product) == "O1"
    product.current_process = manual
    listed.current_marking = 0
    assert lot_key_for_put(station, queue, product) is None
    assert lot_key_for_put(station, SimpleNamespace(lot_slots=None), product) is None


def _run_tray_line(a_output_lot_slots):
    """Four single-piece orders released at A; B (500 s) is the bottleneck.

    A's output has room for two trays (68 pieces), B's input for one tray;
    a_manual -> a_auto passes through A's output inside the station. Returns the run and the peak number
    of orders whose finished products waited in A's output at the same time.
    """
    from prodsys.models.order_data import OrderData

    ps = _tray_line()
    for port in ps.port_data:
        if port.ID == "A_output":
            port.lot_slots = a_output_lot_slots
        if port.ID == "B_input":
            port.lot_slots = 1  # one tray in front of B, so finished orders wait at A
    for tm in ps.time_model_data:
        if tm.ID == "tm_b_auto":
            tm.location = 500.0
    ps.order_data = [
        OrderData(ID=f"O{i}", ordered_products=[{"product_type": "P", "quantity": 1}],
                  order_time=0.0, release_time=0.0, due_time=1e5, priority=1)
        for i in range(4)
    ]
    ps.schedule = [_ev(0, "A", "a_manual", f"P_{i}", f"O{i}") for i in range(4)]
    sim = runner.Runner(production_system_data=ps)
    sim.initialize_simulation()
    station = sim.resource_factory.get_resource("A")
    a_output = next(q for q in station.ports if q.data.ID == "A_output")
    peak = {"orders": 0}
    finished_at_a: set[str] = set()
    original_put = a_output.put

    def recording_put(item, *args, **kwargs):
        yield from original_put(item, *args, **kwargs)
        if sim.product_factory.get_product(item.ID).current_process.data.ID == "a_auto":
            finished_at_a.add(item.ID)
        orders = {
            sim.product_factory.get_product(pid).info.order_ID
            for pid in a_output.items
            if pid in finished_at_a
        }
        peak["orders"] = max(peak["orders"], len(orders))

    a_output.put = recording_put
    info = sim.run_until_complete(time_range_max=10000)
    return sim, info, peak["orders"]


def test_station_output_with_one_tray_place_blocks_instead_of_holding_two_orders() -> None:
    sim, info, peak = _run_tray_line(a_output_lot_slots=None)
    assert len(sim.product_factory.finished_products) == 4
    assert peak >= 2  # pieces only: finished orders pile up in A's output

    sim, info, peak = _run_tray_line(a_output_lot_slots=1)
    assert len(sim.product_factory.finished_products) == 4  # intra-station hop does not deadlock
    assert info.get("early_exit")
    assert peak == 1
