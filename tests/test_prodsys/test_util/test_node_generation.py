import os
import pytest
from prodsys.models.production_system_data import ProductionSystemData, add_default_queues_to_production_system
import prodsys.express as psx
from prodsys import runner
from prodsys.util.node_link_generation import node_link_generation
from prodsys.models import resource_data
import prodsys
from prodsys.util.util import set_seed


@pytest.fixture
def simulation_adapter() -> ProductionSystemData:
    # all time models
    time_model_agv = psx.DistanceTimeModel(speed=360, reaction_time=0, ID="time_model_x")
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

    # All processes
    ltp01 = psx.LinkTransportProcess(time_model=time_model_agv, ID="ltp01")
    productionprocess01 = psx.ProductionProcess(time_model=time_model_machine1, ID="pp01")
    productionprocess02 = psx.ProductionProcess(time_model=time_model_machine2, ID="pp02")
    productionprocess03 = psx.ProductionProcess(time_model=time_model_machine3, ID="pp03")

    # All resources
    machine01 = psx.Resource(
        ID="resource01",
        processes=[productionprocess01],
        location=[100, 100],
    )
    machine02 = psx.Resource(
        ID="resource02",
        processes=[productionprocess02],
        location=[200, 10],
    )
    machine03 = psx.Resource(
        ID="resource03",
        processes=[productionprocess03],
        location=[100, 200],
    )

    agv01 = psx.Resource(
        location=[0, 0],
        ID="agv01",
        processes=[ltp01],
        control_policy=resource_data.TransportControlPolicy.FIFO
    )

    # All products
    product01 = psx.Product(
        process=[
            productionprocess01,
            productionprocess02,
            productionprocess03,
        ],
        transport_process=ltp01,
        ID="product01",
    )

    product02 = psx.Product(
        process=[
            productionprocess03,
            productionprocess02,
            productionprocess01,
        ],
        transport_process=ltp01,
        ID="product02",
    )

    source01 = psx.Source(
        product=product01,
        ID="source01",
        time_model=timer_model_interarrival_time,
        location=[0, 0],
    )
    source02 = psx.Source(
        product=product02,
        ID="source02",
        time_model=timer_model_interarrival_time2,
        location=[0, 0],
    )

    sink01 = psx.Sink(product=product01, ID="sink01", location=[200, 205])
    sink02 = psx.Sink(product=product02, ID="sink02", location=[200, 205])

    # Add production system
    productionsystem = psx.ProductionSystem(
        resources=[
            agv01,
            machine01,
            machine02,
            machine03,
        ],
        sources=[source01, source02],
        sinks=[sink01, sink02],
        ID="productionsystem01",
    )

    adapter = productionsystem.to_model()
    # Set seed to ensure deterministic behavior and avoid test pollution
    adapter.seed = 0
    # Ensure seed is set before network generation (which may use random state)
    set_seed(adapter.seed)
    node_link_generation.generate_and_apply_network(adapter)

    return adapter


def test_initialize_simulation(simulation_adapter: ProductionSystemData):
    runner_instance = runner.Runner(production_system_data=simulation_adapter)
    runner_instance.initialize_simulation()


def test_hashing(simulation_adapter: ProductionSystemData):
    hash_str = simulation_adapter.hash()
    assert hash_str == "ddeeaeb715319754daa6eddab0f938fb"


def test_run_simulation(simulation_adapter: ProductionSystemData):
    # Explicitly set seed before running simulation to ensure deterministic behavior
    # This prevents test pollution from random state changes in previous tests
    set_seed(simulation_adapter.seed)
    runner_instance = runner.Runner(production_system_data=simulation_adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(1000)
    runner_instance.print_results()
    assert runner_instance.env.now == 1000
    post_processor = runner_instance.get_post_processor()
    for kpi in post_processor.df_aggregated_output:
        assert kpi > 1

    product01 = 0.0 
    product02 = 0.0         
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output":
            if kpi.product_type == "product02":
                product02 = kpi.value 
            if kpi.product_type == "product01":
                product01 = kpi.value
    assert product01 > 1
    assert product02 > 1

def test_run_simulation_with_xml_layout(simulation_adapter: ProductionSystemData):
    # Time models
    ftmp1 = prodsys.time_model_data.FunctionTimeModelData(
        ID="ftmp1",
        description="function time model process 1",
        distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Normal,
        location=0.833,
        scale=0.0833
    )
    ftmp2 = prodsys.time_model_data.FunctionTimeModelData(
        ID="ftmp2",
        description="function time model process 2",
        distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Normal,
        location=4.167,
        scale=0.4167
    )
    ftm1 = prodsys.time_model_data.FunctionTimeModelData(
        ID="ftm1",
        description="function time model product 1",
        distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Exponential,
        location=10.05,
        scale=0.0
    )
    md1 = prodsys.time_model_data.DistanceTimeModelData(
        ID="md1",
        description="manhattan time model 1",
        speed=60.0,
        reaction_time=0.033,
        metric="manhattan",
    )

    # Processes
    P1 = prodsys.processes_data.ProductionProcessData(
        ID="P1",
        description="Process 1",
        time_model_id="ftmp1",
        type=prodsys.processes_data.ProcessTypeEnum.ProductionProcesses,
    )
    P2 = prodsys.processes_data.ProductionProcessData(
        ID="P2",
        description="Process 2",
        time_model_id="ftmp2",
        type=prodsys.processes_data.ProcessTypeEnum.ProductionProcesses,
    )
    TP1 = prodsys.processes_data.LinkTransportProcessData( #empty links, to be generated
        ID="TP1",
        description="Transport Process 1",
        time_model_id="md1",
        capability="TP1",
        type=prodsys.processes_data.ProcessTypeEnum.LinkTransportProcesses,
        links=[],
        can_move=True
    )

    # Resource
    R1 = prodsys.resource_data.ResourceData( #resource with two ports
        ID="R1",
        description="Resource 1",
        capacity=2,
        location=[-100, -100],
        controller=prodsys.resource_data.ControllerEnum.PipelineController,
        control_policy=prodsys.resource_data.ResourceControlPolicy.FIFO,
        process_ids=["P1", "P2"],
        #ports=[Port0.ID, Port1.ID], 
    )
    R2 = prodsys.resource_data.ResourceData( #resource without ports: standart port are generated below
        ID="R2",
        description="Resource 1_1",
        capacity=2,
        location=[0, -50.0],
        controller=prodsys.resource_data.ControllerEnum.PipelineController,
        control_policy=prodsys.resource_data.ResourceControlPolicy.FIFO,
        process_ids=["P1", "P2"],
    )
    #Transport Resource like AGV
    TR1 = prodsys.resource_data.ResourceData(
        ID="TR1",
        description="Transport Resource 1",
        capacity=1,
        location=[0, 50],
        controller=prodsys.resource_data.ControllerEnum.PipelineController,
        control_policy=prodsys.resource_data.TransportControlPolicy.SPT_transport,
        process_ids=["TP1"],
        can_move=True,
    )

    # Product
    Product_1 = prodsys.product_data.ProductData(
        ID="Product_1",
        description="",
        type="Product_1",
        processes=["P1"],
        transport_process="TP1",
    )

    # Source
    S1 = prodsys.source_data.SourceData(
        ID="S1",
        description="Source 1",
        location=[-100.0, -100.0],
        product_type="Product_1",
        time_model_id="ftm1",
        routing_heuristic=prodsys.source_data.RoutingHeuristic.shortest_queue
    )

    # Sink
    K1 = prodsys.sink_data.SinkData(
        ID="K1",
        description="Sink 1",
        location=[100.0, 100.0],
        product_type="Product_1",
    )

    
    # Assemble the production system
    production_system_instance = ProductionSystemData(
        time_model_data=[ftmp1, ftmp2, ftm1, md1],
        process_data=[P1, P2, TP1],
        #port_data=[Port0, Port1],
        resource_data=[R1, TR1, R2],
        product_data=[Product_1],
        source_data=[S1],
        sink_data=[K1],
        valid_configuration=True,
        node_data=[]
    )
    add_default_queues_to_production_system(production_system_instance, reset=False)
    adapter = production_system_instance
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join( "examples", "modelling_and_simulation", "simulation_example_data", "FreeSpace.drawio.xml")
    node_link_generation.generate_and_apply_network(adapter=adapter, xml_path=path, visualize=False, simple_connection=True)
    runner_instance = runner.Runner(production_system_data=adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(500)
    runner_instance.print_results()
    assert runner_instance.env.now == 500
    post_processor = runner_instance.get_post_processor()
    for kpi in post_processor.df_aggregated_output:
        assert kpi > 1

    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output":
            if kpi.product_type == "Product_1":
                assert 5 < kpi.value < 80