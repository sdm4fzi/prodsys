import pytest
from prodsys.models.production_system_data import ProductionSystemData
import prodsys.express as psx
from prodsys import runner


@pytest.fixture
def charging_simulation_adapter() -> ProductionSystemData:
    t1 = psx.FunctionTimeModel("normal", 0.8, 0.1, "t1")
    t2 = psx.FunctionTimeModel("normal", 1.6, 0.2, "t2")

    p1 = psx.ProductionProcess(t1, "p1")
    p2 = psx.ProductionProcess(t2, "p2")

    t3 = psx.DistanceTimeModel(speed=180, reaction_time=0.1, ID="t3")

    tp = psx.TransportProcess(t3, "tp")

    s1 = psx.FunctionTimeModel("exponential", 0.5, ID="s1")
    setup_state_1 = psx.SetupState(s1, p1, p2, "S1")
    setup_state_2 = psx.SetupState(s1, p2, p1, "S2")

    charging_time_model = psx.FunctionTimeModel(
        "constant", 60, ID="charging_time_model"
    )
    battery_time_model = psx.FunctionTimeModel("constant", 180, ID="battery_time_model")
    charging_state = psx.ChargingState(
        time_model=charging_time_model,
        battery_time_model=battery_time_model,
        ID="charging_state",
    )

    machine = psx.Resource(
        [p1, p2], [5, 0], 2, states=[setup_state_1, setup_state_2], ID="machine"
    )
    machine2 = psx.Resource(
        [p1, p2], [7, 0], 2, states=[setup_state_1, setup_state_2], ID="machine2"
    )

    transport = psx.Resource([tp], [0, 0], 1, states=[charging_state], ID="transport")

    product1 = psx.Product([p1], tp, "product1")
    product2 = psx.Product([p2], tp, "product2")

    sink1 = psx.Sink(product1, [10, 0], "sink1")
    sink2 = psx.Sink(product2, [10, 0], "sink2")

    arrival_model_1 = psx.FunctionTimeModel("exponential", 2, ID="arrival_model_1")
    arrival_model_2 = psx.FunctionTimeModel("exponential", 3, ID="arrival_model_2")

    source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")
    source2 = psx.Source(product2, arrival_model_2, [0, 0], ID="source_2")

    system = psx.ProductionSystem(
        [machine, machine2, transport], [source1, source2], [sink1, sink2]
    )
    adapter = system.to_model()
    return adapter


def test_initialize_simulation(
    charging_simulation_adapter: ProductionSystemData,
):
    runner_instance = runner.Runner(production_system_data=charging_simulation_adapter)
    runner_instance.initialize_simulation()


def test_hashing(charging_simulation_adapter: ProductionSystemData):
    hash_str = charging_simulation_adapter.hash()
    assert hash_str == "b0b7eabaeb1889831b74784f28f77bc1"


def test_run_simulation(charging_simulation_adapter: ProductionSystemData):
    runner_instance = runner.Runner(production_system_data=charging_simulation_adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(4000)
    runner_instance.print_results()
    assert runner_instance.env.now == 4000
    post_processor = runner_instance.get_post_processor()
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output" and kpi.product_type == "product1":
            assert kpi.value > 2100 and kpi.value < 2140
    for kpi in post_processor.machine_state_KPIS:
        if kpi.name == "productive_time" and kpi.resource == "machine":
            assert kpi.value < 42 and kpi.value > 39

        if kpi.name == "charging_time" and kpi.resource == "transport":
            assert kpi.value < 11 and kpi.value > 10

    for kpi in post_processor.WIP_KPIs:
        if kpi.name == "WIP" and kpi.product_type == "product1":
            assert kpi.value < 8.5 and kpi.value > 7.5

    for kpi in post_processor.aggregated_throughput_time_KPIs:
        if kpi.name == "throughput_time" and kpi.product_type == "product1":
            assert kpi.value < 12.5 and kpi.value > 11.5
