"""Simulation tests for MaintenanceState."""

import pytest

import prodsys.express as psx
from prodsys import runner
from prodsys.analytics.store import AnalyticsStore
from prodsys.models.production_system_data import ProductionSystemData
from prodsys.models.state_data import StateTypeEnum

SIMULATION_TIME = 500.0
MAINTENANCE_INTERVAL = 50.0
MAINTENANCE_DURATION = 5.0
MAINTENANCE_STATE_ID = "maintenance_state"
MACHINE_ID = "machine"


@pytest.fixture
def maintenance_simulation_adapter() -> ProductionSystemData:
    process_time = psx.FunctionTimeModel("constant", 2.0, 0.0, ID="process_time")
    transport_time = psx.FunctionTimeModel("constant", 0.5, 0.0, ID="transport_time")

    production = psx.ProductionProcess(process_time, ID="P1")
    transport = psx.TransportProcess(transport_time, ID="TP")

    maintenance_interval = psx.FunctionTimeModel(
        "constant", MAINTENANCE_INTERVAL, 0.0, ID="maintenance_interval"
    )
    maintenance_duration = psx.FunctionTimeModel(
        "constant", MAINTENANCE_DURATION, 0.0, ID="maintenance_duration"
    )
    maintenance = psx.MaintenanceState(
        maintenance_interval,
        maintenance_duration,
        ID=MAINTENANCE_STATE_ID,
    )

    machine = psx.Resource(
        [production],
        [5, 0],
        1,
        states=[maintenance],
        ID=MACHINE_ID,
    )
    agv = psx.Resource([transport], [2, 0], 1, ID="transport")

    product = psx.Product([production], transport, ID="product")
    source = psx.Source(
        product,
        psx.FunctionTimeModel("constant", 4.0, 0.0, ID="arrival"),
        [0, 0],
        ID="source",
    )
    sink = psx.Sink(product, [10, 0], ID="sink")

    system = psx.ProductionSystem([machine, agv], [source], [sink])
    return system.to_model()


def test_adapter_contains_maintenance_state(
    maintenance_simulation_adapter: ProductionSystemData,
):
    maint_states = [
        s
        for s in maintenance_simulation_adapter.state_data
        if s.type == StateTypeEnum.MaintenanceState
    ]
    assert len(maint_states) == 1
    assert maint_states[0].ID == MAINTENANCE_STATE_ID

    machine = next(
        r for r in maintenance_simulation_adapter.resource_data if r.ID == MACHINE_ID
    )
    assert MAINTENANCE_STATE_ID in machine.state_ids


def test_initialize_simulation(maintenance_simulation_adapter: ProductionSystemData):
    runner_instance = runner.Runner(
        production_system_data=maintenance_simulation_adapter
    )
    runner_instance.initialize_simulation()


def test_maintenance_simulation_events(
    maintenance_simulation_adapter: ProductionSystemData,
):
    runner_instance = runner.Runner(
        production_system_data=maintenance_simulation_adapter
    )
    runner_instance.initialize_simulation()
    runner_instance.run(SIMULATION_TIME)

    assert runner_instance.env.now == SIMULATION_TIME

    df_raw = runner_instance.get_post_processor().df_raw
    maint = df_raw[df_raw["State Type"] == "Maintenance"]
    assert not maint.empty, "No Maintenance events in simulation log"

    by_state = maint[maint["State"] == MAINTENANCE_STATE_ID]
    starts = by_state[by_state["Activity"] == "start state"]
    ends = by_state[by_state["Activity"] == "end state"]

    assert len(starts) == len(ends)
    assert len(starts) >= int(SIMULATION_TIME // MAINTENANCE_INTERVAL) - 1

    durations = ends["Time"].values - starts["Time"].values
    assert all(abs(d - MAINTENANCE_DURATION) < 1e-6 for d in durations)

    assert starts["Time"].iloc[0] == pytest.approx(MAINTENANCE_INTERVAL)
    assert not by_state[by_state["Resource"] == MACHINE_ID].empty


def test_maintenance_simulation_analytics_mt(
    maintenance_simulation_adapter: ProductionSystemData,
):
    runner_instance = runner.Runner(
        production_system_data=maintenance_simulation_adapter
    )
    runner_instance.initialize_simulation()
    runner_instance.run(SIMULATION_TIME)

    df_raw = runner_instance.get_post_processor().df_raw
    store = AnalyticsStore()
    store.ingest_events(df_raw)
    resource_states = store.resource_states()

    machine_mt = resource_states[
        (resource_states["Resource"] == MACHINE_ID)
        & (resource_states["Time_type"] == "MT")
    ]
    assert not machine_mt.empty

    total_mt = float(machine_mt["time_increment"].sum())
    expected_cycles = int(SIMULATION_TIME // MAINTENANCE_INTERVAL) - 1
    assert total_mt == pytest.approx(expected_cycles * MAINTENANCE_DURATION)

    post_processor = runner_instance.get_post_processor()
    df_aggregated = post_processor.df_aggregated_resource_states
    pp_mt = df_aggregated[
        (df_aggregated["Resource"] == MACHINE_ID)
        & (df_aggregated["Time_type"] == "MT")
    ]
    assert not pp_mt.empty
    assert float(pp_mt["time_increment"].sum()) == pytest.approx(total_mt)
