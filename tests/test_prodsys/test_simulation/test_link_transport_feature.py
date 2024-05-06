import pytest
from prodsys.adapters import JsonProductionSystemAdapter
import prodsys.express as psx
from prodsys import runner
from prodsys.simulation import sim


# Define the path to your test configuration file. This should be similar to example_simulation.py.
@pytest.fixture
def simulation_adapter() -> JsonProductionSystemAdapter:
    time_model_agv = psx.DistanceTimeModel(
        speed=90, reaction_time=0.2, ID="time_model_x"
    )

    time_model_machine1 = psx.FunctionTimeModel(
        distribution_function="constant", location=3, ID="time_model_ap23"
    )
    time_model_machine2 = psx.FunctionTimeModel(
        distribution_function="constant", location=3, ID="time_model_ap23"
    )
    time_model_machine3 = psx.FunctionTimeModel(
        distribution_function="constant", location=6, ID="time_model_ap23"
    )
    time_model_machine4 = psx.FunctionTimeModel(
        distribution_function="constant", location=6, ID="time_model_ap23"
    )
    time_model_machine5 = psx.FunctionTimeModel(
        distribution_function="constant", location=6, ID="time_model_ap23"
    )
    time_model_machine6 = psx.FunctionTimeModel(
        distribution_function="constant", location=3, ID="time_model_ap23"
    )
    timer_model_interarrival_time = psx.FunctionTimeModel(
        distribution_function="constant", location=6, ID="time_model_source01"
    )
    timer_model_interarrival_time2 = psx.FunctionTimeModel(
        distribution_function="constant", location=6, ID="time_model_source02"
    )

    node1 = psx.Node(location=[0, 20], ID="node1")
    node2 = psx.Node(location=[50, 20], ID="node2")
    node3 = psx.Node(location=[100, 20], ID="node3")
    node4 = psx.Node(location=[100, 80], ID="node4")
    node5 = psx.Node(location=[50, 80], ID="node5")
    node6 = psx.Node(location=[0, 80], ID="node6")



    rcp01 = psx.RequiredCapabilityProcess(time_model=time_model_agv, capability="euro_palette_transport", ID="rtp01")
    productionprocess01 = psx.ProductionProcess(time_model=time_model_machine1, ID="pp01")
    productionprocess02 = psx.ProductionProcess(time_model=time_model_machine2, ID="pp02")
    productionprocess03 = psx.ProductionProcess(time_model=time_model_machine3, ID="pp03")
    productionprocess04 = psx.ProductionProcess(time_model=time_model_machine4, ID="pp04")
    productionprocess05 = psx.ProductionProcess(time_model=time_model_machine5, ID="pp05")
    productionprocess06 = psx.ProductionProcess(time_model=time_model_machine6, ID="pp06")


    machine01 = psx.ProductionResource(
        ID="resource01",
        processes=[productionprocess01],
        location=[0, 0],
    )
    machine02 = psx.ProductionResource(
        ID="resource02",
        processes=[productionprocess02],
        location=[50, 0],
    )
    machine03 = psx.ProductionResource(
        ID="resource03",
        processes=[productionprocess03],
        location=[100, 0],
    )
    machine04 = psx.ProductionResource(
        ID="resource04",
        processes=[productionprocess04],
        location=[100, 100],
    )
    machine05 = psx.ProductionResource(
        ID="resource05",
        processes=[productionprocess05],
        location=[50, 100],
    )
    machine06 = psx.ProductionResource(
        ID="resource06",
        processes=[productionprocess06],
        location=[0, 100],
    )

    product01 = psx.Product(
        processes=[
            productionprocess01,
            productionprocess02,
            productionprocess03,
            productionprocess04,
            productionprocess05,
            productionprocess06,
        ],
        transport_process=rcp01,
        ID="product01",
    )

    product02 = psx.Product(
            processes=[
                    productionprocess01,
                    productionprocess02,
                    productionprocess03,
                    productionprocess04,
                    productionprocess06,
            ],
            transport_process = rcp01,
            ID="product02",
    )

    source01 = psx.Source(
        product=product01,
        ID="source01",
        time_model=timer_model_interarrival_time,
        location=[-10, 0],
    )

    source02 = psx.Source(
        product=product02,
        ID="source02",
        time_model=timer_model_interarrival_time2,
        location=[-10, 0],
    )
    sink01 = psx.Sink(product=product01, ID="sink01", location=[-10, 100])
    sink02 = psx.Sink(product=product02, ID="sink02", location=[-10, 100])

    ltp01_links = [
        [source01, machine01],
        [source02, machine01],
        [machine01, node1],
        [node1, node2],
        [node2, machine02],
        [node2, node3],
        [node3, machine03],
    ]

    ltp01 = psx.LinkTransportProcess(time_model=time_model_agv, capability="euro_palette_transport", ID="ltp01", links=ltp01_links)

    ltp02_links = [
        [node3, machine03],
        [node3, node4],
        [node4, machine04],
        [node4, node5],
        [node5, machine05],
        [node5, node6],
        [node6, machine06],
        [machine06, sink01],
        [machine06, sink02],
    ]

    ltp02 = psx.LinkTransportProcess(time_model=time_model_agv, capability= "euro_palette_transport", ID="ltp02", links=ltp02_links)

    agv01 = psx.TransportResource(
        location=[50, 20],
        ID="agv01",
        processes=[ltp01],
    )

    agv02 = psx.TransportResource(
        location=[50, 20],
        ID="agv02",
        processes=[ltp01],
    )

    agv03 = psx.TransportResource(
        location=[50, 20],
        ID="agv03",
        processes=[ltp01],
    )

    agv04 = psx.TransportResource(
        location=[50, 80],
        ID="agv04",
        processes=[ltp02],
    )

    agv05 = psx.TransportResource(
        location=[50, 80],
        ID="agv05",
        processes=[ltp02],
    )

    agv06 = psx.TransportResource(
        location=[50, 80],
        ID="agv06",
        processes=[ltp02],
    )

    productionsystem = psx.ProductionSystem(
        resources=[
            agv01,
            agv02,
            agv03,
            agv04,
            agv05,
            agv06,
            machine01,
            machine02,
            machine03,
            machine04,
            machine05,
            machine06,
        ],
        sources=[source01, source02],
        sinks=[sink01, sink02],
        ID="productionsystem01",
    )

    adapter = productionsystem.to_model()
    return adapter

def test_validate_simulation(simulation_adapter: JsonProductionSystemAdapter):
    simulation_adapter.validate_configuration()


def test_initialize_simulation(simulation_adapter: JsonProductionSystemAdapter):
    runner_instance = runner.Runner(adapter=simulation_adapter)   
    runner_instance.initialize_simulation()

def test_run_simulation(simulation_adapter: JsonProductionSystemAdapter):
    runner_instance = runner.Runner(adapter=simulation_adapter)   
    runner_instance.initialize_simulation()
    runner_instance.run(480)
    assert runner_instance.env.now == 480
    post_processor = runner_instance.get_post_processor()
    for counter, kpi in enumerate(post_processor.throughput_and_output_KPIs):
        if kpi.name == "output":
            assert kpi.value > 1
    assert counter == 2 * 2 - 1

    productive_counter = 0
    for counter, kpi in enumerate(post_processor.machine_state_KPIS):
        if kpi.name == "productive_time":
            productive_counter += 1
            assert kpi.value > 1 and kpi.value < 99
    assert productive_counter == 12

    for counter, kpi in enumerate(post_processor.WIP_KPIs):
        if kpi.name == "WIP":
            assert kpi.value > 0.01 and kpi.value < 500

    assert counter == 2 + 1 - 1
