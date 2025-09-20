import pytest
from prodsys.models.production_system_data import ProductionSystemData
import prodsys.express as psx
from prodsys import runner
from prodsys.models import resource_data


@pytest.fixture
def batch_simulation_adapter() -> ProductionSystemData:
    t1 = psx.FunctionTimeModel("exponential", 0.8, 0, "t1")

    p1 = psx.ProductionProcess(t1, "p1")

    t3 = psx.FunctionTimeModel("constant", 0.1, ID="t3")

    tp = psx.TransportProcess(t3, "tp")

    machine = psx.Resource(
        [p1],
        [5, 0],
        capacity=2,
        ID="machine",
        controller=resource_data.ControllerEnum.BatchController,
        batch_size=2,
    )

    transport = psx.Resource([tp], [0, 0], 1, ID="transport")

    product1 = psx.Product([p1], tp, "product1")

    sink1 = psx.Sink(product1, [10, 0], "sink1")

    arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")

    source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")

    system = psx.ProductionSystem([machine, transport], [source1], [sink1])
    adapter = system.to_model()
    return adapter


def test_initialize_simulation(batch_simulation_adapter: ProductionSystemData):
    runner_instance = runner.Runner(production_system_data=batch_simulation_adapter)
    runner_instance.initialize_simulation()


def test_hashing(batch_simulation_adapter: ProductionSystemData):
    hash_str = batch_simulation_adapter.hash()
    assert hash_str == "033c7bc03c97031f0b32ddd01812a949"


def test_run_simulation(batch_simulation_adapter: ProductionSystemData):
    runner_instance = runner.Runner(production_system_data=batch_simulation_adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(2000)
    assert runner_instance.env.now == 2000
    post_processor = runner_instance.get_post_processor()
    runner_instance.print_results()
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output":
            assert kpi.product_type == "product1"
            assert kpi.value > 1900 and kpi.value < 1950
    for kpi in post_processor.machine_state_KPIS:
        if kpi.name == "productive_time" and kpi.resource == "machine":
            assert kpi.value < 40 and kpi.value > 37

        if kpi.name == "productive_time" and kpi.resource == "transport":
            assert kpi.value > 34 and kpi.value < 36

    for kpi in post_processor.WIP_KPIs:
        if kpi.name == "WIP" and kpi.product_type == "product1":
            assert kpi.value < 2.95 and kpi.value > 2.8

    for kpi in post_processor.aggregated_throughput_time_KPIs:
        if kpi.name == "throughput_time":
            assert kpi.value < 2.2 and kpi.value > 2.0
