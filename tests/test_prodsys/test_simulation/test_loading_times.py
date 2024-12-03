import pytest
from prodsys.adapters import JsonProductionSystemAdapter
import prodsys.express as psx
from prodsys import runner


@pytest.fixture
def loading_times_simulation_adapter() -> JsonProductionSystemAdapter:
    t1 = psx.FunctionTimeModel("exponential", 0.8, ID="t1")
    p1 = psx.ProductionProcess(t1, "p1")

    movement_time_model = psx.FunctionTimeModel("exponential", 0.1, ID="t3")
    loading_time_model = psx.FunctionTimeModel("constant", 0.2, ID="t4")
    unloading_time_model = psx.FunctionTimeModel("constant", 0.2, ID="t5")

    tp = psx.TransportProcess(movement_time_model, "tp", loading_time_model=loading_time_model, unloading_time_model=unloading_time_model)

    machine = psx.ProductionResource([p1], [5, 0], 1, ID="machine")

    transport = psx.TransportResource([tp], [0, 0], 1, ID="transport")

    product1 = psx.Product([p1], tp, "product1")

    sink1 = psx.Sink(product1, [10, 0], "sink1")

    arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")

    source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")

    system = psx.ProductionSystem([machine, transport], [source1], [sink1])
    adapter = system.to_model()
    return adapter


def test_initialize_simulation(loading_times_simulation_adapter: JsonProductionSystemAdapter):
    runner_instance = runner.Runner(adapter=loading_times_simulation_adapter)
    runner_instance.initialize_simulation()


def test_hashing(loading_times_simulation_adapter: JsonProductionSystemAdapter):
    hash_str = loading_times_simulation_adapter.hash()
    assert hash_str == "4f565c2d574392e23b9d807cde881ba8"


def test_run_simulation(loading_times_simulation_adapter: JsonProductionSystemAdapter):
    runner_instance = runner.Runner(adapter=loading_times_simulation_adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(2000)
    assert runner_instance.env.now == 2000
    runner_instance.print_results()
    runner_instance.save_results_as_csv()
    # FIXME: resolve problem loading times are not properly used!
    post_processor = runner_instance.get_post_processor()
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output":
            assert kpi.product_type == "product1"
            assert kpi.value > 2040 and kpi.value < 2060
    for kpi in post_processor.machine_state_KPIS:
        if kpi.name == "productive_time" and kpi.resource == "machine":
            assert kpi.value < 83 and kpi.value > 81

        if kpi.name == "productive_time" and kpi.resource == "transport":
            assert kpi.value > 34 and kpi.value < 36

    for kpi in post_processor.WIP_KPIs:
        if kpi.name == "WIP" and kpi.product_type == "product1":
            assert kpi.value < 5.3 and kpi.value > 5.2

    for kpi in post_processor.aggregated_throughput_time_KPIs:
        if kpi.name == "throughput_time":
            assert kpi.value < 4.5 and kpi.value > 4.3
