import pytest
from prodsys.models.production_system_data import ProductionSystemData
import prodsys.express as psx
from prodsys import runner


@pytest.fixture
def simulation_adapter() -> ProductionSystemData:
    t1 = psx.FunctionTimeModel("constant", 0.8, 0, "t1")

    p1 = psx.ProductionProcess(t1, "p1")

    t3 = psx.FunctionTimeModel("normal", 0.1, 0.01, ID="t3")

    tp = psx.TransportProcess(t3, "tp")

    machine = psx.Resource([p1], [5, 0], 1, ID="machine")

    transport = psx.Resource([tp], [0, 0], 1, ID="transport")

    product1 = psx.Product([p1], tp, "product1")

    sink1 = psx.Sink(product1, [10, 0], "sink1")

    arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")

    source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")

    system = psx.ProductionSystem([machine, transport], [source1], [sink1])
    adapter = system.to_model()
    return adapter


def test_initialize_simulation(simulation_adapter: ProductionSystemData):
    runner_instance = runner.Runner(production_system_data=simulation_adapter)
    runner_instance.initialize_simulation()


def test_hashing(simulation_adapter: ProductionSystemData):
    hash_str = simulation_adapter.hash()
    assert hash_str == "961381a81312651fe2b2d1086c090eaa"


def test_run_simulation(simulation_adapter: ProductionSystemData):
    runner_instance = runner.Runner(production_system_data=simulation_adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(2000)
    runner_instance.print_results()
    assert runner_instance.env.now == 2000
    post_processor = runner_instance.get_post_processor()
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output":
            assert kpi.product_type == "product1"
            assert kpi.value > 1950 and kpi.value < 2050
    for kpi in post_processor.machine_state_KPIS:
        if kpi.name == "productive_time" and kpi.resource == "machine":
            assert kpi.value < 82 and kpi.value > 78

        if kpi.name == "productive_time" and kpi.resource == "transport":
            assert kpi.value > 30 and kpi.value < 35

    for kpi in post_processor.WIP_KPIs:
        if kpi.name == "WIP" and kpi.product_type == "product1":
            assert kpi.value > 3.0 and kpi.value < 3.5

    for kpi in post_processor.aggregated_throughput_time_KPIs:
        if kpi.name == "throughput_time":
            assert kpi.value > 2.4 and kpi.value < 2.8


def test_run_simulation_with_cut_off(simulation_adapter: ProductionSystemData):
    runner_instance = runner.Runner(
        production_system_data=simulation_adapter,
        warm_up_cutoff=True,
        cut_off_method="static_ratio",
    )
    runner_instance.initialize_simulation()
    runner_instance.run(2000)
    runner_instance.print_results()
    assert runner_instance.env.now == 2000
    post_processor = runner_instance.get_post_processor()
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output":
            assert kpi.product_type == "product1"
            assert kpi.value > 1650 and kpi.value < 1750
    for kpi in post_processor.machine_state_KPIS:
        if kpi.name == "productive_time" and kpi.resource == "machine":
            assert kpi.value < 82 and kpi.value > 78

        if kpi.name == "productive_time" and kpi.resource == "transport":
            assert kpi.value > 30 and kpi.value < 35

    for kpi in post_processor.WIP_KPIs:
        if kpi.name == "WIP" and kpi.product_type == "product1":
            assert kpi.value < 3.5 and kpi.value > 3.0
    for kpi in post_processor.aggregated_throughput_time_KPIs:
        if kpi.name == "throughput_time":
            assert kpi.value < 2.8 and kpi.value > 2.4
