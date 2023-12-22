import pytest
from prodsys.adapters import JsonProductionSystemAdapter
import prodsys.express as psx
from prodsys import runner

# Define the path to your test configuration file. This should be similar to example_simulation.py.
@pytest.fixture
def simulation_adapter() -> JsonProductionSystemAdapter:
    # All time models
    tm_p1 = psx.FunctionTimeModel("normal", 1, 0.1, "tm_p1")
    tm_p2 = psx.FunctionTimeModel("normal", 2, 0.2, "tm_p2")
    tm_p3 = psx.SequentialTimeModel([1.6, 0.7, 1.4, 0.6], "tm_p3")
    tm_p4 = psx.FunctionTimeModel("lognormal", 1.5, 0.4, "tm_p4")
    tm_p5 = psx.FunctionTimeModel("exponential", 1, ID="tm_p5")


    tm_cp1 = psx.FunctionTimeModel("normal", 1, 0.1, "tm_cp1")
    tm_cp2 = psx.FunctionTimeModel("normal", 2, 0.5, "tm_cp2")
    tm_cp3 = psx.SequentialTimeModel([1.6, 0.7, 1.4, 0.6], "tm_cp3")

    tm_tp = psx.ManhattanDistanceTimeModel(120, 0.1, "tm_tp")


    tm_p1_p2 = psx.FunctionTimeModel("exponential", 0.4, ID="s1")
    tm_p2_p1 = psx.FunctionTimeModel("exponential", 0.6, ID="s2")

    tm_p4_p5 = psx.FunctionTimeModel("exponential", 0.3, ID="s3")
    tm_p5_p4 = psx.FunctionTimeModel("exponential", 0.5, ID="s4")

    tm_resource_breakdown = psx.FunctionTimeModel("exponential", 540, ID="tm_resource_breakdown")
    tm_resource_repair = psx.FunctionTimeModel("exponential", 60, ID="tm_resource_repair")
    tm_transport_breakdown = psx.FunctionTimeModel("exponential", 530, ID="tm_transport_breakdown")
    tm_transport_repair = psx.FunctionTimeModel("exponential", 45, ID="tm_transport_repair")


    tm_p1_process_breakdown = psx.FunctionTimeModel("exponential", 540, ID="tm_p1_process_breakdown")
    tm_p1_process_repair = psx.FunctionTimeModel("exponential", 30, ID="tm_p1_process_repair")


    tm_arrival_model_1 = psx.FunctionTimeModel("exponential", 5.2, ID="tm_arrival_model_1")
    tm_arrival_model_2 = psx.FunctionTimeModel("exponential", 4.3, ID="tm_arrival_model_2")
    tm_arrival_model_3 = psx.FunctionTimeModel("exponential", 4.2, ID="tm_arrival_model_3")
    tm_arrival_model_4 = psx.FunctionTimeModel("exponential", 8.6, ID="tm_arrival_model_4")

    # All processes
    p1 = psx.ProductionProcess(tm_p1, "p1")
    p2 = psx.ProductionProcess(tm_p2, "p2")
    p3 = psx.ProductionProcess(tm_p3, "p3")
    p4 = psx.ProductionProcess(tm_p4, "p4")
    p5 = psx.ProductionProcess(tm_p5, "p5")

    cp1 = psx.CapabilityProcess(tm_cp1, "p1", "cp1")
    cp2 = psx.CapabilityProcess(tm_cp2, "p2", "cp2")
    cp3 = psx.CapabilityProcess(tm_cp3, "p3", "cp3")

    tp = psx.TransportProcess(tm_tp, "tp")

    # All states
    setup_state_1 = psx.SetupState(tm_p1_p2, p1, p2, "setup_state_1")
    setup_state_2 = psx.SetupState(tm_p2_p1, p2, p1, "setup_state_2")
    setup_state_c1 = psx.SetupState(tm_p1_p2, cp1, cp2, "setup_state_c1")
    setup_state_c2 = psx.SetupState(tm_p2_p1, cp2, cp1, "setup_state_c2")

    setup_state_3 = psx.SetupState(tm_p4_p5, p4, p5, "setup_state_3")
    setup_state_4 = psx.SetupState(tm_p5_p4, p5, p4, "setup_state_4")


    breakdown_state_1 = psx.BreakDownState(tm_resource_breakdown, tm_resource_repair, "breakdown_state_1")
    breakdown_state_2 = psx.BreakDownState(tm_transport_breakdown, tm_transport_repair, "breakdown_state_2")
    breakdown_state_3 = psx.BreakDownState(tm_p1_process_breakdown, tm_p1_process_repair, "breakdown_state_3")



    # All resources
    machine_1 = psx.ProductionResource([p1, p2, cp1, cp2], [5,0], 1, states=[setup_state_1, setup_state_2, setup_state_c1, setup_state_c2, breakdown_state_1, breakdown_state_3], ID="machine_1")
    machine_2 = psx.ProductionResource([p1, p2, cp1, cp2], [7,0], 1, states=[setup_state_1, setup_state_2, setup_state_c1, setup_state_c2, breakdown_state_1, breakdown_state_3], ID="machine_2")

    machine_3 = psx.ProductionResource([p3, cp3], [5,2], 2, states=[breakdown_state_1], ID="machine_3")

    machine_4 = psx.ProductionResource([p4, p5], [7,2], 2, states=[setup_state_3, setup_state_4, breakdown_state_1], ID="machine_4")
    machine_5 = psx.ProductionResource([p4, p5], [5,4], 2, states=[setup_state_3, setup_state_4, breakdown_state_1], ID="machine_5")
    machine_6 = psx.ProductionResource([p4, p5], [7,4], 2, states=[setup_state_3, setup_state_4, breakdown_state_1], ID="machine_6")

    transport_1 = psx.TransportResource([tp], [0,0], 1, states=[breakdown_state_2], ID="transport_1")
    transport_2 = psx.TransportResource([tp], [0,0], 1, states=[breakdown_state_2], ID="transport_2")
    transport_3 = psx.TransportResource([tp], [0,0], 1, states=[breakdown_state_2], ID="transport_3")

    # All products
    product1 = psx.Product([p1, p2, p3, p4], tp, "product1")
    product2 = psx.Product([p3, p5, p4], tp, "product2")
    product3 = psx.Product([cp1, cp2, cp3], tp, "product3")
    product4 = psx.Product([p1, p3, p4, p3, p5], tp, "product4")


    sink1 = psx.Sink(product1, [10, 0], "sink1")
    sink2 = psx.Sink(product2, [10, 0], "sink2")
    sink3 = psx.Sink(product3, [10, 0], "sink3")
    sink4 = psx.Sink(product4, [10, 0], "sink4")


    source1 = psx.Source(product1, tm_arrival_model_1, [0, 0], ID="source_1")
    source2 = psx.Source(product2, tm_arrival_model_2, [0, 0], ID="source_2")
    source3 = psx.Source(product3, tm_arrival_model_3, [0, 0], "CapabilityRouter", ID="source_3")
    source4 = psx.Source(product4, tm_arrival_model_4, [0, 0], ID="source_4")

    system = psx.ProductionSystem([machine_1, machine_2, machine_3, machine_4, machine_5, machine_6, transport_1, transport_2, transport_3], [source1, source2, source3, source4], [sink1, sink2, sink3, sink4])
    adapter = system.to_model()
    return adapter

def test_initialize_simulation(simulation_adapter: JsonProductionSystemAdapter):
    runner_instance = runner.Runner(adapter=simulation_adapter)   
    runner_instance.initialize_simulation()

def test_run_simulation(simulation_adapter: JsonProductionSystemAdapter):
    runner_instance = runner.Runner(adapter=simulation_adapter)   
    runner_instance.initialize_simulation()
    runner_instance.run(2000)
    assert runner_instance.env.now == 2000
    post_processor = runner_instance.get_post_processor()
    for counter, kpi in enumerate(post_processor.throughput_and_output_KPIs):
        if kpi.name == "output":
            assert kpi.value > 1
    assert counter == 4 * 2 - 1

    productive_counter = 0
    for counter, kpi in enumerate(post_processor.machine_state_KPIS):
        if kpi.name == "productive_time":
            productive_counter += 1
            assert kpi.value > 1 and kpi.value < 99
    assert productive_counter == 9

    for counter, kpi in enumerate(post_processor.WIP_KPIs):
        if kpi.name == "WIP":
            assert kpi.value > 0.01 and kpi.value < 500

    assert counter == 4 + 1 - 1
