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

    t3 = psx.FunctionTimeModel("normal", 0.05, 0.01, ID="t3")

    tp = psx.TransportProcess(t3, "tp")

    machine = psx.Resource(
        [p1],
        [5, 0],
        3,
        ID="machine",
        internal_queue_size=20,
    )

    machine2 = psx.Resource(
        [p2],
        [9, 0],
        3,
        ID="machine2",
        internal_queue_size=20,
    )
    storage1 = psx.Store(ID="storage1", location=[6, 0], capacity=20)
    storage2 = psx.Store(ID="storage2", location=[11, 0], capacity=30)
    machine.buffers = [storage1]
    machine2.buffers = [storage2]

    transport = psx.Resource([tp], [0, 0], 1, ID="transport")

    product1 = psx.Product([p1, p2], tp, "product1")

    sink1 = psx.Sink(product1, [10, 0], "sink1")

    arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")

    source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")

    system = psx.ProductionSystem([machine, machine2, transport], [source1], [sink1])
    adapter = system.to_model()
    return adapter


def test_initialize_simulation(storage_simulation_adapter: ProductionSystemData):
    runner_instance = runner.Runner(production_system_data=storage_simulation_adapter)
    runner_instance.initialize_simulation()


def test_hashing(storage_simulation_adapter: ProductionSystemData):
    hash_str = storage_simulation_adapter.hash()
    assert hash_str == "d6512bd8b31e1ceed97e5e828ebaab1e"


def test_run_simulation(storage_simulation_adapter: ProductionSystemData):
    runner_instance = runner.Runner(production_system_data=storage_simulation_adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(2000)
    runner_instance.print_results()
    assert runner_instance.env.now == 2000
    post_processor = runner_instance.get_post_processor()
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output":
            assert kpi.product_type == "product1"
            assert kpi.value > 2020 and kpi.value < 2060
    for kpi in post_processor.machine_state_KPIS:
        if kpi.name == "productive_time" and kpi.resource == "machine":
            assert kpi.value < 40 and kpi.value > 35

        if kpi.name == "productive_time" and kpi.resource == "transport":
            assert kpi.value > 40 and kpi.value < 50

    for kpi in post_processor.WIP_KPIs:
        if kpi.name == "WIP" and kpi.product_type == "product1":
            assert kpi.value > 3.5 and kpi.value < 4.5

    for kpi in post_processor.aggregated_throughput_time_KPIs:
        if kpi.name == "throughput_time":
            assert kpi.value > 3.0 and kpi.value < 4.0
