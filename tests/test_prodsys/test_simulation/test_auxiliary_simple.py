import pytest
import prodsys
from prodsys.adapters import JsonProductionSystemAdapter
import prodsys.express as psx
from prodsys import runner


@pytest.fixture
def simulation_adapter() -> JsonProductionSystemAdapter:
    t1 = psx.FunctionTimeModel("exponential", 0.8, 0, "t1")

    p1 = psx.ProductionProcess(t1, "p1")

    # t3 = psx.FunctionTimeModel("constant", 0.1, ID="t3")
    t3 = psx.DistanceTimeModel(60, 0.05, "manhattan", ID="t3")

    tp = psx.TransportProcess(t3, "tp")

    machine = psx.ProductionResource([p1], [5, 0], 1, ID="machine")

    transport = psx.TransportResource([tp], [3, 0], 1, ID="transport")
    transport2 = psx.TransportResource([tp], [4, 0], 1, ID="transport2")

    storage1 = psx.Store(ID="storage1", location=[6, 0], capacity=30)
    storage2 = psx.Store(ID="storage2", location=[11, 0], capacity=20)

    auxiliary1 = psx.Auxiliary(
        ID="auxiliary1",
        transport_process=tp,
        storages=[storage1, storage2],
        quantity_in_storages=[5, 20],
        relevant_processes=[],
        relevant_transport_processes=[tp],
    )

    product1 = psx.Product(
        processes=[p1], transport_process=tp, ID="product1", auxiliaries=[auxiliary1]
    )

    sink1 = psx.Sink(product1, [10, 0], "sink1")

    arrival_model_1 = psx.FunctionTimeModel("constant", 0.9, ID="arrival_model_1")

    source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")

    system = psx.ProductionSystem([machine, transport, transport2], [source1], [sink1])

    system.validate()
    adapter = system.to_model()
    return adapter


def test_initialize_simulation(simulation_adapter: JsonProductionSystemAdapter):
    runner_instance = runner.Runner(adapter=simulation_adapter)
    runner_instance.initialize_simulation()


def test_hashing(simulation_adapter: JsonProductionSystemAdapter):
    hash_str = simulation_adapter.hash()
    assert hash_str == "859e772fb8398b4804e66a92b2df5dd8"


def test_run_simulation(simulation_adapter: JsonProductionSystemAdapter):
    runner_instance = runner.Runner(adapter=simulation_adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(1000)
    assert runner_instance.env.now == 1000
    runner_instance.print_results()
    post_processor = runner_instance.get_post_processor()
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output":
            assert kpi.product_type == "product1"
            assert kpi.value > 1100 and kpi.value < 1120
    for kpi in post_processor.machine_state_KPIS:
        if kpi.name == "productive_time" and kpi.resource == "machine":
            assert kpi.value < 90 and kpi.value > 88

        if kpi.name == "productive_time" and kpi.resource == "transport":
            assert kpi.value > 53 and kpi.value < 55
        if kpi.name == "productive_time" and kpi.resource == "transport2":
            assert kpi.value > 53 and kpi.value < 55

    for kpi in post_processor.WIP_KPIs:
        if kpi.name == "WIP" and kpi.product_type == "product1":
            assert kpi.value < 5.7 and kpi.value > 5.6

    for kpi in post_processor.auxiliary_WIP_KPIs:
        if kpi.name == "AUXILIARY_WIP" and kpi.product_type == "auxiliary1":
            assert kpi.value < 6.2 and kpi.value > 6.1

    for kpi in post_processor.aggregated_throughput_time_KPIs:
        if kpi.name == "throughput_time":
            assert kpi.value < 5.1 and kpi.value > 5.0
