import pytest
from prodsys.models.production_system_data import ProductionSystemData
import prodsys.express as psx
from prodsys import runner


@pytest.fixture
def simulation_adapter() -> ProductionSystemData:
    t1 = psx.FunctionTimeModel("exponential", 0.8, 0, "t1")
    t2 = psx.FunctionTimeModel("exponential", 1.2, 0, "t2")

    p1 = psx.ProductionProcess(t1, "p1")
    p2 = psx.ProductionProcess(t2, "p2")

    # t3 = psx.FunctionTimeModel("constant", 0.1, ID="t3")
    t3 = psx.DistanceTimeModel(60, 0.05, "manhattan", ID="t3")

    tp = psx.TransportProcess(t3, "tp")
    tp_primitive = psx.TransportProcess(t3, "tp_primitive")

    machine = psx.Resource([p1], [5, 0], 1, ID="machine")
    machine2 = psx.Resource([p2], [5, 5], 2, ID="machine2")

    transport = psx.Resource([tp], [3, 0], 1, ID="transport")
    transport2 = psx.Resource([tp], [3, 0], 1, ID="transport2")
    transport_primitive = psx.Resource([tp_primitive], [4, 0], 1, ID="transport_primitive")

    storage1 = psx.Store(ID="storage1", location=[6, 0], capacity=30)
    storage2 = psx.Store(ID="storage2", location=[11, 0], capacity=20)

    primitive1 = psx.Primitive(
        ID="primitive1",
        transport_process=tp_primitive,
        storages=[storage1],
        quantity_in_storages=[10],
    )

    primitive2 = psx.Primitive(
        ID="primitive2",
        transport_process=tp_primitive,
        storages=[storage2],
        quantity_in_storages=[20],
    )

    primitive_dependency_1 = psx.PrimitiveDependency(
        ID="primitive_dependency_1",
        required_primitive=primitive1,
    )
    primitive_dependency_2 = psx.PrimitiveDependency(
        ID="primitive_dependency_2",
        required_primitive=primitive2,
    )

    product1 = psx.Product(
        process=[p1, p2],
        transport_process=tp,
        ID="product1",
        dependencies=[primitive_dependency_1],
    )
    product2 = psx.Product(
        process=[p2, p1],
        transport_process=tp,
        ID="product2",
        dependencies=[primitive_dependency_2],
    )

    sink1 = psx.Sink(product1, [10, 0], "sink1")
    sink2 = psx.Sink(product2, [10, 0], "sink2")

    arrival_model_1 = psx.FunctionTimeModel("constant", 2.6, ID="arrival_model_1")
    arrival_model_2 = psx.FunctionTimeModel("constant", 1.3, ID="arrival_model_2")

    source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")
    source2 = psx.Source(product2, arrival_model_2, [0, 0], ID="source_2")

    system = psx.ProductionSystem(
        [machine, machine2, transport, transport2, transport_primitive],
        [source1, source2],
        [sink1, sink2],
        [primitive1, primitive2],
    )
    system.validate()
    adapter = system.to_model()
    return adapter


def test_initialize_simulation(simulation_adapter: ProductionSystemData):
    runner_instance = runner.Runner(production_system_data=simulation_adapter)
    runner_instance.initialize_simulation()


def test_hashing(simulation_adapter: ProductionSystemData):
    hash_str = simulation_adapter.hash()
    assert hash_str == "cb95ca8efab786ff2822fdb46456627e"


def test_run_simulation(simulation_adapter: ProductionSystemData):
    runner_instance = runner.Runner(production_system_data=simulation_adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(1000)
    assert runner_instance.env.now == 1000
    runner_instance.print_results()
    post_processor = runner_instance.get_post_processor()
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output" and kpi.product_type == "product1":
            assert kpi.value > 370 and kpi.value < 390
        if kpi.name == "output" and kpi.product_type == "product2":
            assert kpi.value > 740 and kpi.value < 770
    for kpi in post_processor.machine_state_KPIS:
        if kpi.name == "productive_time" and kpi.resource == "machine":
            assert kpi.value < 94 and kpi.value > 91

        if kpi.name == "productive_time" and kpi.resource == "transport":
            assert kpi.value > 48 and kpi.value < 55
        if kpi.name == "productive_time" and kpi.resource == "transport2":
            assert kpi.value > 48 and kpi.value < 55
        if kpi.name == "productive_time" and kpi.resource == "transport_primitive":
            assert kpi.value > 63 and kpi.value < 67

    for kpi in post_processor.WIP_KPIs:
        if kpi.name == "WIP" and kpi.product_type == "product1":
            assert kpi.value < 7.5 and kpi.value > 5.8
        if kpi.name == "WIP" and kpi.product_type == "product2":
            assert kpi.value < 14 and kpi.value > 12

    for kpi in post_processor.primitive_WIP_KPIs:
        if kpi.name == "primitive_WIP" and kpi.product_type == "primitive1":
            assert kpi.value < 7.5 and kpi.value > 5.8
        if kpi.name == "primitive_WIP" and kpi.product_type == "primitive2":
            assert kpi.value < 14 and kpi.value > 12

    for kpi in post_processor.aggregated_throughput_time_KPIs:
        if kpi.name == "throughput_time" and kpi.product_type == "product1":
            assert kpi.value < 18.5 and kpi.value > 16.5
        if kpi.name == "throughput_time" and kpi.product_type == "product2":
            assert kpi.value < 17.5 and kpi.value > 14.5
