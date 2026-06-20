"""
Integration tests for explicit standby state logging (Blocked, Starved, Idle, WaitingForTransport).
"""

from __future__ import annotations

import pandas as pd
import pytest

import prodsys.express as psx
from prodsys import runner
from prodsys.analytics.store import AnalyticsStore
from prodsys.models import port_data
from prodsys.util.post_processing import PostProcessor


def _run_simulation(adapter, run_time: float = 50.0):
    sim_runner = runner.Runner(production_system_data=adapter)
    sim_runner.initialize_simulation()
    sim_runner.run(run_time)
    return sim_runner.event_logger.get_data_as_dataframe(), adapter


def _resource_state_time(df_raw, resource_id: str, time_type: str) -> float:
    store = AnalyticsStore.from_raw(df_raw, time_range=df_raw["Time"].max())
    rs = store.resource_states()
    rows = rs[(rs["Resource"] == resource_id) & (rs["Time_type"] == time_type)]
    if len(rows) == 0:
        return 0.0
    return float(rows["time_increment"].sum())


def _state_events(df_raw, resource_id: str, state_type: str):
    return df_raw[
        (df_raw["Resource"] == resource_id)
        & (df_raw["State Type"] == state_type)
        & (df_raw["Activity"] == "start state")
    ]


def test_blocked_time_with_small_output_queue():
    """Machine blocked when output queue is full (capacity=1)."""
    t = psx.FunctionTimeModel("constant", 1.0, ID="t")
    t_arrival = psx.FunctionTimeModel("exponential", 0.4, ID="t_arr")
    t_transport = psx.DistanceTimeModel(speed=5, reaction_time=1.0, ID="t_tr")

    p1 = psx.ProductionProcess(t, "p1")
    tp = psx.TransportProcess(t_transport, "tp")

    machine = psx.Resource([p1], [5, 0], 1, ID="machine")
    machine.ports = [
        psx.Queue(
            ID="machine_iq",
            capacity=2,
            location=[5, 0],
            interface_type=port_data.PortInterfaceType.INPUT,
        ),
        psx.Queue(
            ID="machine_oq",
            capacity=1,
            location=[5, 0],
            interface_type=port_data.PortInterfaceType.OUTPUT,
        ),
    ]
    transport = psx.Resource([tp], [2, 0], 1, ID="transport")
    product = psx.Product(process=[p1], transport_process=tp, ID="product")
    source = psx.Source(product, t_arrival, [0, 0], ID="source")
    sink = psx.Sink(product, [10, 0], ID="sink")

    system = psx.ProductionSystem([machine, transport], [source], [sink])
    adapter = system.to_model()
    df_raw, _ = _run_simulation(adapter, run_time=40.0)

    bl_time = _resource_state_time(df_raw, "machine", "BL")
    assert bl_time > 0, "Expected blocked time on machine with capacity-1 output queue"

    blocked_events = _state_events(df_raw, "machine", "Blocked")
    assert len(blocked_events) > 0
    assert blocked_events["Target location"].iloc[0] == "machine_oq"


def test_idle_time_with_slow_arrivals():
    """Machine idle when no products are requested."""
    t = psx.FunctionTimeModel("constant", 1.0, ID="t")
    t_arrival = psx.FunctionTimeModel("exponential", 15.0, ID="t_arr")
    t_transport = psx.DistanceTimeModel(speed=180, reaction_time=0.1, ID="t_tr")

    p1 = psx.ProductionProcess(t, "p1")
    tp = psx.TransportProcess(t_transport, "tp")

    machine = psx.Resource([p1], [5, 0], 1, ID="machine")
    transport = psx.Resource([tp], [2, 0], 1, ID="transport")
    product = psx.Product(process=[p1], transport_process=tp, ID="product")
    source = psx.Source(product, t_arrival, [0, 0], ID="source")
    sink = psx.Sink(product, [10, 0], ID="sink")

    system = psx.ProductionSystem([machine, transport], [source], [sink])
    adapter = system.to_model()
    df_raw, _ = _run_simulation(adapter, run_time=50.0)

    id_time = _resource_state_time(df_raw, "machine", "ID")
    assert id_time > 0, "Expected idle time with slow arrivals"


def test_resource_states_sum_to_100_percent():
    """All mapped state percentages should sum to ~100% per resource."""
    t = psx.FunctionTimeModel("constant", 1.0, ID="t")
    t_arrival = psx.FunctionTimeModel("exponential", 2.0, ID="t_arr")
    t_transport = psx.DistanceTimeModel(speed=180, reaction_time=0.1, ID="t_tr")

    p1 = psx.ProductionProcess(t, "p1")
    tp = psx.TransportProcess(t_transport, "tp")

    machine = psx.Resource([p1], [5, 0], 1, ID="machine")
    transport = psx.Resource([tp], [2, 0], 1, ID="transport")
    product = psx.Product(process=[p1], transport_process=tp, ID="product")
    source = psx.Source(product, t_arrival, [0, 0], ID="source")
    sink = psx.Sink(product, [10, 0], ID="sink")

    system = psx.ProductionSystem([machine, transport], [source], [sink])
    adapter = system.to_model()
    df_raw, _ = _run_simulation(adapter, run_time=30.0)

    store = AnalyticsStore.from_raw(df_raw, time_range=df_raw["Time"].max())
    rs = store.resource_states()
    for resource in rs["Resource"].unique():
        if resource in ("source", "sink"):
            continue
        total = rs[rs["Resource"] == resource]["percentage"].sum()
        assert abs(total - 100.0) < 1.0, f"{resource} percentages sum to {total}"


def test_standby_state_aggregation_from_synthetic_log():
    """Unit-style check that Blocked/Starved map to BL/SV in aggregation."""
    data = {
        "Time": [0.0, 5.0, 5.0, 10.0, 10.0, 20.0],
        "Resource": ["M1"] * 6,
        "State": ["s"] * 6,
        "State Type": ["Blocked", "Blocked", "Starved", "Starved", "Idle", "Idle"],
        "Activity": ["start state", "end state", "start state", "end state", "start state", "end state"],
        "Product": [None] * 6,
        "Expected End Time": [None] * 6,
        "Origin location": [None, None, "iq1", "iq1", None, None],
        "Target location": ["oq1", "oq1", None, None, None, None],
        "Empty Transport": [None] * 6,
        "Requesting Item": [None] * 6,
        "Dependency": [None] * 6,
        "process": [None] * 6,
        "Initial Transport Step": [None] * 6,
        "Last Transport Step": [None] * 6,
    }
    pp = PostProcessor(df_raw=pd.DataFrame(data))
    df = pp.df_aggregated_resource_states
    types = set(df[df["Resource"] == "M1"]["Time_type"])
    assert "BL" in types
    assert "SV" in types
    assert "ID" in types
