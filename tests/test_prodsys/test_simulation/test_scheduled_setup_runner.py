"""Runner E2E: explicit Setup events in a schedule are accepted and simulated."""

from __future__ import annotations

import prodsys.express as psx
from prodsys import runner
from prodsys.models.performance_data import Event
from prodsys.models.production_system_data import ProductionSystemData


def _system_with_setup_states() -> ProductionSystemData:
    t1 = psx.FunctionTimeModel("constant", 1.0, 0, "t1")
    t2 = psx.FunctionTimeModel("constant", 1.0, 0, "t2")
    p1 = psx.ProductionProcess(t1, "p1")
    p2 = psx.ProductionProcess(t2, "p2")
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "tp")
    setup_tm = psx.FunctionTimeModel("constant", 2.0, ID="setup_tm")
    setup_s1 = psx.SetupState(setup_tm, p1, p2, "S1")
    setup_s2 = psx.SetupState(setup_tm, p2, p1, "S2")
    machine = psx.Resource(
        [p1, p2], [10, 0], 1, ID="machine", states=[setup_s1, setup_s2]
    )
    transport = psx.Resource([tp], [5, 0], 1, ID="transport")
    product1 = psx.Product([p1], tp, "product1")
    product2 = psx.Product([p2], tp, "product2")
    sink1 = psx.Sink(product1, [20, 0], "sink1")
    sink2 = psx.Sink(product2, [20, 0], "sink2")
    arrival1 = psx.FunctionTimeModel("constant", 100.0, ID="arrival1")
    arrival2 = psx.FunctionTimeModel("constant", 100.0, ID="arrival2")
    source1 = psx.Source(product1, arrival1, [0, 0], ID="source1")
    source2 = psx.Source(product2, arrival2, [0, 0], ID="source2")
    system = psx.ProductionSystem(
        [machine, transport], [source1, source2], [sink1, sink2]
    )
    return system.to_model()


def test_scheduled_setup_runner_accepts_and_logs_setup():
    """model.schedule with S1 must not raise; simulation logs Setup activity."""
    model = _system_with_setup_states()
    schedule = [
        Event(
            time=0.0,
            resource="machine",
            state="p1",
            state_type="Production",
            activity="start state",
            product="product1_1",
            expected_end_time=1.0,
            process="p1",
        ),
        Event(
            time=1.0,
            resource="machine",
            state="S1",
            state_type="Setup",
            activity="start state",
            product="product2_1",
            expected_end_time=3.0,
            process="S1",
        ),
        Event(
            time=3.0,
            resource="machine",
            state="p2",
            state_type="Production",
            activity="start state",
            product="product2_1",
            expected_end_time=4.0,
            process="p2",
        ),
    ]
    model.schedule = schedule

    runner_instance = runner.Runner(production_system_data=model)
    runner_instance.initialize_simulation()
    runner_instance.run(20.0)

    df = runner_instance.event_logger.get_data_as_dataframe()
    setup_rows = df[df["State Type"] == "Setup"]
    assert not setup_rows.empty, "expected Setup rows in simulation event log"
    assert "S1" in set(setup_rows["State"].dropna().astype(str))
