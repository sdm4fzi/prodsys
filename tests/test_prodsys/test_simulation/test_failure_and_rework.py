import pytest
from prodsys.adapters import JsonProductionSystemAdapter
import prodsys.express as psx
from prodsys import runner


@pytest.fixture
def simulation_adapter() -> JsonProductionSystemAdapter:
    t1 = psx.FunctionTimeModel("exponential", 0.8, 0, "t1")

    p1 = psx.ProductionProcess(t1, "p1", failure_rate=0.05)
    p2 = psx.ProductionProcess(t1, "p2", failure_rate=0.1)
    p3 = psx.ProductionProcess(t1, "p3")

    t3 = psx.FunctionTimeModel("constant", 0.1, ID="t3")

    tp = psx.TransportProcess(t3, "tp")

    rework_time_model = psx.FunctionTimeModel("constant", 1, ID="rework_time_model")
    rework_time_model2 = psx.FunctionTimeModel("constant", 5, ID="rework_time_model")
    rework_time_model3 = psx.FunctionTimeModel("constant", 2, ID="rework_time_model")

    # FIXME: rework process is used as normal production process.... -> adjust match process or so
    rework_process = psx.ReworkProcess(rework_time_model, [p1], True, "rework_process")
    rework_process2 = psx.ReworkProcess(
        rework_time_model2, [p2], False, "rework_process2"
    )
    rework_process3 = psx.ReworkProcess(
        rework_time_model3, [p1], False, "rework_process3"
    )

    machine = psx.ProductionResource([p1], [5, 0], 1, ID="machine")
    machine2 = psx.ProductionResource([p2], [10, 0], 1, ID="machine2")
    machine3 = psx.ProductionResource([p3], [5, 5], 1, ID="machine3")

    reworker = psx.ProductionResource(
        [rework_process, rework_process2, rework_process3], [8, 0], 1, ID="reworker"
    )

    transport = psx.TransportResource([tp], [0, 0], 1, ID="transport")

    product1 = psx.Product([p1, p2, p3], tp, "product1")

    sink1 = psx.Sink(product1, [15, 0], "sink1")

    arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")

    source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_2")

    system = psx.ProductionSystem(
        [machine, machine2, machine3, reworker, transport], [source1], [sink1]
    )
    adapter = system.to_model()
    return adapter


def test_initialize_simulation(simulation_adapter: JsonProductionSystemAdapter):
    runner_instance = runner.Runner(adapter=simulation_adapter)
    runner_instance.initialize_simulation()


def test_hashing(simulation_adapter: JsonProductionSystemAdapter):
    hash_str = simulation_adapter.hash()
    assert hash_str == "57e81e816c8e98e0747d9b9b90b8c06f"


def test_run_simulation(simulation_adapter: JsonProductionSystemAdapter):
    runner_instance = runner.Runner(adapter=simulation_adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(2000)
    assert runner_instance.env.now == 2000
    post_processor = runner_instance.get_post_processor()
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output":
            assert kpi.product_type == "product1"
            assert kpi.value > 2000 and kpi.value < 2030
    for kpi in post_processor.machine_state_KPIS:
        if kpi.name == "productive_time" and kpi.resource == "machine":
            assert kpi.value < 83 and kpi.value > 81

        if kpi.name == "productive_time" and kpi.resource == "transport":
            assert kpi.value > 75 and kpi.value < 77

        if kpi.name == "productive_time" and kpi.resource == "reworker":
            assert kpi.value > 15 and kpi.value < 16

    for kpi in post_processor.WIP_KPIs:
        if kpi.name == "WIP" and kpi.product_type == "product1":
            assert kpi.value < 16 and kpi.value > 15

    for kpi in post_processor.aggregated_throughput_time_KPIs:
        if kpi.name == "throughput_time":
            assert kpi.value < 15 and kpi.value > 14
