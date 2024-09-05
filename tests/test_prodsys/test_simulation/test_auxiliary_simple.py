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

    machine = psx.ProductionResource([p1], [5,0], 1, ID="machine")

    transport = psx.TransportResource([tp], [3,0], 1, ID="transport")
    transport2 = psx.TransportResource([tp], [4,0], 1, ID="transport2")

    storage1 = psx.Queue(ID="storage1", location=[5,0], capacity=30)
    storage2 = psx.Queue(ID="storage2", location=[10,0], capacity=20)

    auxiliary1 = psx.Auxiliary(ID="auxiliary1", transport_process=tp, 
                            storages=[storage1,storage2], 
                            initial_quantity_in_stores=[5,20], 
                            relevant_processes=[], 
                            relevant_transport_processes=[tp])

    product1 = psx.Product(processes= [p1], transport_process= tp, ID = "product1", auxiliaries= [auxiliary1])

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
    assert hash_str == "10b5a0cfbf6397ef9368a3bd5681648c"

def test_run_simulation(simulation_adapter: JsonProductionSystemAdapter):
    runner_instance = runner.Runner(adapter=simulation_adapter)   
    runner_instance.initialize_simulation()
    runner_instance.run(1000)
    assert runner_instance.env.now == 1000
    post_processor = runner_instance.get_post_processor()
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output":
            assert kpi.product_type == "product1"
            assert kpi.value > 920 and kpi.value < 960
    for kpi in post_processor.machine_state_KPIS:
        if kpi.name == "productive_time" and kpi.resource == "machine":
            assert kpi.value < 92 and kpi.value > 84

        if kpi.name == "productive_time" and kpi.resource == "transport":
            assert kpi.value > 40 and kpi.value < 50
        if kpi.name == "productive_time" and kpi.resource == "transport2":
            assert kpi.value > 40 and kpi.value < 50
        
    for kpi in post_processor.WIP_KPIs:
        if kpi.name == "WIP" and kpi.product_type == "product1":
            assert kpi.value < 1.9 and kpi.value > 1.7

    for kpi in post_processor.auxiliary_WIP_KPIs:
        if kpi.name == "AUXILIARY_WIP" and kpi.product_type == "auxiliary1":
            assert kpi.value < 2.4 and kpi.value > 2.1

    for kpi in post_processor.aggregated_throughput_time_KPIs:
        if kpi.name == "throughput_time":
            assert kpi.value < 1.7 and kpi.value > 1.6