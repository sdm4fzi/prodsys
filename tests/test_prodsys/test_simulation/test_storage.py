import pytest
import prodsys
from prodsys.models.production_system_data import ProductionSystemData
import prodsys.express as psx
from prodsys import runner


@pytest.fixture
def storage_simulation_adapter() -> ProductionSystemData:
    t1 = psx.FunctionTimeModel("exponential", 0.8, 0, "t1")

    p1 = psx.ProductionProcess(t1, "p1")
    p2 = psx.ProductionProcess(t1, "p2")

    t3 = psx.FunctionTimeModel("normal", 0.1, 0.01, ID="t3")

    tp = psx.TransportProcess(t3, "tp")

    storage = psx.Store(
        ID="storage",
        location=[5, 1],
        input_location=[4, 1],
        output_location=[6, 1],
        capacity=10,
    )
    storage2 = psx.Store(ID="output_storage", location=[9, 1], capacity=5)

    machine = psx.ProductionResource(
        [p1],
        [5, 0],
        3,
        ID="machine",
        internal_queue_size=2,
        # FIXME: storages are buggy, no result is produced and transport is locked. Pending put increases...
        input_stores=[storage],
        output_stores=[storage],
    )

    machine2 = psx.ProductionResource(
        [p2],
        [9, 0],
        3,
        ID="machine2",
        internal_queue_size=2,
        output_stores=[storage, storage2],
    )

    transport = psx.TransportResource([tp], [0, 0], 1, ID="transport")

    product1 = psx.Product([p1, p2], tp, "product1")

    sink1 = psx.Sink(product1, [10, 0], "sink1")

    arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")

    source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")

    system = psx.ProductionSystem([machine, machine2, transport], [source1], [sink1])
    adapter = system.to_model()
    return adapter


def test_initialize_simulation(storage_simulation_adapter: ProductionSystemData):
    runner_instance = runner.Runner(adapter=storage_simulation_adapter)
    runner_instance.initialize_simulation()


def test_hashing(storage_simulation_adapter: ProductionSystemData):
    hash_str = storage_simulation_adapter.hash()
    assert hash_str == "747f8669f99074930561a959d72a9219"


def test_run_simulation(storage_simulation_adapter: ProductionSystemData):
    runner_instance = runner.Runner(adapter=storage_simulation_adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(2000)
    assert runner_instance.env.now == 2000
    post_processor = runner_instance.get_post_processor()
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output":
            assert kpi.product_type == "product1"
            assert kpi.value > 2075 and kpi.value < 2085
    for kpi in post_processor.machine_state_KPIS:
        if kpi.name == "productive_time" and kpi.resource == "machine":
            assert kpi.value < 58 and kpi.value > 57

        if kpi.name == "productive_time" and kpi.resource == "transport":
            assert kpi.value > 77 and kpi.value < 78

    for kpi in post_processor.WIP_KPIs:
        if kpi.name == "WIP" and kpi.product_type == "product1":
            assert kpi.value > 6.1 and kpi.value < 6.25

    for kpi in post_processor.aggregated_throughput_time_KPIs:
        if kpi.name == "throughput_time":
            assert kpi.value > 5.0 and kpi.value < 5.1
