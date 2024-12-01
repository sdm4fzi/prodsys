import pytest
import prodsys
from prodsys.adapters import JsonProductionSystemAdapter
import prodsys.express as psx
from prodsys import runner


@pytest.fixture
def simulation_adapter() -> JsonProductionSystemAdapter:
    t1 = psx.FunctionTimeModel("exponential", 0.8, 0, "t1")
    t2 = psx.FunctionTimeModel("exponential", 1.2, 0, "t2")

    p1 = psx.ProductionProcess(t1, "p1")
    p2 = psx.ProductionProcess(t2, "p2")

    # t3 = psx.FunctionTimeModel("constant", 0.1, ID="t3")
    t3 = psx.DistanceTimeModel(60, 0.05, "manhattan", ID="t3")

    tp = psx.TransportProcess(t3, "tp")
    tp_aux = psx.TransportProcess(t3, "tp_aux")

    machine = psx.ProductionResource([p1], [5, 0], 1, ID="machine")
    machine2 = psx.ProductionResource([p2], [5, 5], 2, ID="machine2")

    transport = psx.TransportResource([tp], [3, 0], 1, ID="transport")
    transport2 = psx.TransportResource([tp], [3, 0], 1, ID="transport2")
    transport_aux = psx.TransportResource([tp_aux], [4, 0], 1, ID="transport_aux")

    storage1 = psx.Store(ID="storage1", location=[6, 0], capacity=30)
    storage2 = psx.Store(ID="storage2", location=[11, 0], capacity=20)

    auxiliary1 = psx.Auxiliary(
        ID="auxiliary1",
        transport_process=tp_aux,
        storages=[storage1],
        quantity_in_storages=[10],
        relevant_processes=[],
        relevant_transport_processes=[tp],
    )

    auxiliary2 = psx.Auxiliary(
        ID="auxiliary2",
        transport_process=tp_aux,
        storages=[storage2],
        quantity_in_storages=[20],
        relevant_processes=[],
        relevant_transport_processes=[tp],
    )

    product1 = psx.Product(
        processes=[p1, p2],
        transport_process=tp,
        ID="product1",
        auxiliaries=[auxiliary1],
    )
    product2 = psx.Product(
        processes=[p2, p1],
        transport_process=tp,
        ID="product2",
        auxiliaries=[auxiliary2],
    )

    sink1 = psx.Sink(product1, [10, 0], "sink1")
    sink2 = psx.Sink(product2, [10, 0], "sink2")

    arrival_model_1 = psx.FunctionTimeModel("constant", 2.6, ID="arrival_model_1")
    arrival_model_2 = psx.FunctionTimeModel("constant", 1.3, ID="arrival_model_2")

    source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")
    source2 = psx.Source(product2, arrival_model_2, [0, 0], ID="source_2")

    system = psx.ProductionSystem(
        [machine, machine2, transport, transport2, transport_aux],
        [source1, source2],
        [sink1, sink2],
    )
    system.validate()
    adapter = system.to_model()
    return adapter


def test_initialize_simulation(simulation_adapter: JsonProductionSystemAdapter):
    runner_instance = runner.Runner(adapter=simulation_adapter)
    runner_instance.initialize_simulation()


def test_hashing(simulation_adapter: JsonProductionSystemAdapter):
    hash_str = simulation_adapter.hash()
    assert hash_str == "b9cdb150b8a3260f71382fcb059d0481"


def test_run_simulation(simulation_adapter: JsonProductionSystemAdapter):
    runner_instance = runner.Runner(adapter=simulation_adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(1000)
    assert runner_instance.env.now == 1000
    post_processor = runner_instance.get_post_processor()
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output" and kpi.product_type == "product1":
            assert kpi.value > 320 and kpi.value < 330
        if kpi.name == "output" and kpi.product_type == "product2":
            assert kpi.value > 640 and kpi.value < 660
    for kpi in post_processor.machine_state_KPIS:
        if kpi.name == "productive_time" and kpi.resource == "machine":
            assert kpi.value < 94 and kpi.value > 88

        if kpi.name == "productive_time" and kpi.resource == "transport":
            assert kpi.value > 48 and kpi.value < 53
        if kpi.name == "productive_time" and kpi.resource == "transport2":
            assert kpi.value > 46 and kpi.value < 52
        if kpi.name == "productive_time" and kpi.resource == "transport_aux":
            assert kpi.value > 55 and kpi.value < 65

    for kpi in post_processor.WIP_KPIs:
        if kpi.name == "WIP" and kpi.product_type == "product1":
            assert kpi.value < 1.8 and kpi.value > 1.3
        if kpi.name == "WIP" and kpi.product_type == "product2":
            assert kpi.value < 3.2 and kpi.value > 2.7

    for kpi in post_processor.auxiliary_WIP_KPIs:
        if kpi.name == "AUXILIARY_WIP" and kpi.product_type == "auxiliary1":
            assert kpi.value < 2.1 and kpi.value > 1.75
        if kpi.name == "AUXILIARY_WIP" and kpi.product_type == "auxiliary2":
            assert kpi.value < 3.6 and kpi.value > 3.3

    for kpi in post_processor.aggregated_throughput_time_KPIs:
        if kpi.name == "throughput_time" and kpi.product_type == "product1":
            assert kpi.value < 4.2 and kpi.value > 3.7
        if kpi.name == "throughput_time" and kpi.product_type == "product2":
            assert kpi.value < 4.2 and kpi.value > 3.7
