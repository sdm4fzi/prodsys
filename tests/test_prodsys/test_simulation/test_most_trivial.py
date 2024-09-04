import pytest
from prodsys.adapters import JsonProductionSystemAdapter
import prodsys.express as psx
from prodsys import runner

@pytest.fixture
def simulation_adapter() -> JsonProductionSystemAdapter:
    t1 = psx.FunctionTimeModel("exponential", 0.8, 0, "t1")

    p1 = psx.ProductionProcess(t1, "p1")

    t3 = psx.FunctionTimeModel("constant", 0.1, ID="t3")

    tp = psx.TransportProcess(t3, "tp")

    machine = psx.ProductionResource([p1], [5,0], 1, ID="machine")

    transport = psx.TransportResource([tp], [0,0], 1, ID="transport")

    product1 = psx.Product([p1], tp, "product1")

    sink1 = psx.Sink(product1, [10, 0], "sink1")


    arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")


    source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_2")



    system = psx.ProductionSystem([machine, transport], [source1], [sink1])
    adapter = system.to_model()
    return adapter

def test_initialize_simulation(simulation_adapter: JsonProductionSystemAdapter):
    runner_instance = runner.Runner(adapter=simulation_adapter)   
    runner_instance.initialize_simulation()

def test_hashing(simulation_adapter: JsonProductionSystemAdapter):
    hash_str = simulation_adapter.hash()
    assert hash_str == "934de9573541ea7fcceffda10653ab74"

def test_run_simulation(simulation_adapter: JsonProductionSystemAdapter):
    runner_instance = runner.Runner(adapter=simulation_adapter)   
    runner_instance.initialize_simulation()
    runner_instance.run(2000)
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
            assert kpi.value < 1.7 and kpi.value > 1.5

    for kpi in post_processor.aggregated_throughput_time_KPIs:
        if kpi.name == "throughput_time":
            assert kpi.value < 1.4 and kpi.value > 1.2