import pytest
from prodsys.models.production_system_data import ProductionSystemData
from prodsys import runner
from prodsys.models.dependency_data import DisassemblyDependencyData


@pytest.fixture
def simulation_adapter() -> ProductionSystemData:
    import prodsys
    from prodsys.models.production_system_data import (
    add_default_queues_to_production_system,
    )
    from prodsys.simulation.logger import EventLogger
    event_logger = EventLogger()
    from prodsys.util import post_processing
    from prodsys.models.port_data import PortInterfaceType
    from prodsys.models.primitives_data import StoredPrimitive

    welding_time_model = prodsys.time_model_data.FunctionTimeModelData(
    ID="time model 1",
    description="Time model 1 is create!",
    distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Exponential,
    location=.060,
    scale=0.0,
    )

    transport_time_model = prodsys.time_model_data.DistanceTimeModelData(
    ID="time model 2",
    description="Time model 2 is create!",
    speed=5000.0,
    reaction_time=0.0,
    )

    transport_process = prodsys.processes_data.TransportProcessData(
    ID="NormalTransport",
    description="Normal transport process",
    time_model_id=transport_time_model.ID,
    type=prodsys.processes_data.ProcessTypeEnum.TransportProcesses,
    )

    transport_resource = prodsys.resource_data.ResourceData(
    ID="Forklift1",
    description="Forklift 1 data description",
    capacity=1,
    location=[5.0, 0.0],
    controller=prodsys.resource_data.ControllerEnum.PipelineController,
    control_policy=prodsys.resource_data.TransportControlPolicy.FIFO,# vllt ändern
    process_ids=[transport_process.ID],   
    )

    arrival_time_model = prodsys.time_model_data.FunctionTimeModelData(
    ID="time model 3",
    description="Time model 3 is create!",
    type=prodsys.time_model_data.TimeModelEnum.FunctionTimeModel,
    distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Exponential,
    location=50,
    scale=0,
    )
    
    arrival_time_model1 = prodsys.time_model_data.FunctionTimeModelData(
    ID="time model 4",
    description="Time model 4 is create!",
    type=prodsys.time_model_data.TimeModelEnum.FunctionTimeModel,
    distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Exponential,
    location=10000000,
    scale=0,
    )

    source2 = prodsys.source_data.SourceData(
    ID="source 2",
    description="Source 1 data description",
    location=[0.0, 0.0],
    product_type="mutterprodukt",
    time_model_id="time model 3",
    routing_heuristic=prodsys.source_data.RoutingHeuristic.random,
    )
    
    source4 = prodsys.source_data.SourceData(
    ID="source 4",
    description="Source 3 data description",
    location=[0.0, 0.0],
    product_type="product 1",
    time_model_id="time model 4",
    routing_heuristic=prodsys.source_data.RoutingHeuristic.random,
    )

    sink = prodsys.sink_data.SinkData(
    ID="sink 1",
    description="Sink 1 data description",
    location=[20.0, 20.0],
    product_type="product 1",
    )

    sink2 = prodsys.sink_data.SinkData(
    ID="sink 2",
    description="Sink 1 data description",
    location=[20.0, 20.0],
    product_type="mutterprodukt",
    )
    sink3 = prodsys.sink_data.SinkData(
    ID="sink 3",
    description="Sink 3 data description",
    location=[20.0, 20.0],
    product_type="product 2",
    )

    production_process = prodsys.processes_data.ProductionProcessData(
    ID="production_process",
    description="production_process",
    time_model_id=welding_time_model.ID,
    type=prodsys.processes_data.ProcessTypeEnum.ProductionProcesses,
    )
    
    product = prodsys.product_data.ProductData(
    ID="product 1",
    description="Product 1 data description",
    type="product 1",
    processes=[production_process.ID],
    transport_process=transport_process.ID,
    routing_heuristic=prodsys.source_data.RoutingHeuristic.random, 
    )
    
    product2 = prodsys.product_data.ProductData(
    ID="product 2",
    description="Product 2 data description",
    type="product 2",
    processes=[production_process.ID],
    transport_process=transport_process.ID,
    routing_heuristic=prodsys.source_data.RoutingHeuristic.random, 
    )
    
    mutterprodukt = prodsys.product_data.ProductData(
    ID="mutterprodukt",
    description="Productsdsd 1 data description",
    type="mutterprodukt",
    processes=["disassembly_process"],
    transport_process=transport_process.ID,
    routing_heuristic=prodsys.source_data.RoutingHeuristic.random,
    )


        # product_disassembly_dict= {"mutterprodukt": [mutterprodukt,product, product2] },
    disassembly_dependency = prodsys.dependency_data.DisassemblyDependencyData(
        ID="disassembly_dependency_mutterprodukt",
        description="Disassembly dependency for mutterprodukt",
        required_entity=mutterprodukt.ID,
    )
    disassembly_dependency2 = prodsys.dependency_data.DisassemblyDependencyData(
        ID="disassembly_dependency_product",
        description="Disassembly dependency for product",
        required_entity=product.ID,
    )
    disassembly_dependency3 = prodsys.dependency_data.DisassemblyDependencyData(
        ID="disassembly_dependency_product2",
        description="Disassembly dependency for product2",
        required_entity=product2.ID,
    )

    
    disassembly_process = prodsys.processes_data.ProductionProcessData(
    ID="disassembly_process",
    description="disassembly_process",
    time_model_id=welding_time_model.ID,
    type=prodsys.processes_data.ProcessTypeEnum.ProductionProcesses,
    dependency_ids=[disassembly_dependency.ID, disassembly_dependency2.ID, disassembly_dependency3.ID],
    )

    disassemblymachine = prodsys.resource_data.ResourceData(
    ID="disassemblymachine 1",
    description="Machine 1 data description",
    capacity=2,
    location=[10.0, 10.0],
    controller=prodsys.resource_data.ControllerEnum.PipelineController,
    control_policy=prodsys.resource_data.ResourceControlPolicy.FIFO,
    process_ids=[disassembly_process.ID],
    )
    
    machine = prodsys.resource_data.ResourceData(
    ID="machine 2",
    description="Machine 2 data description",
    capacity=1,
    location=[15.0, 15.0],
    controller=prodsys.resource_data.ControllerEnum.PipelineController,
    control_policy=prodsys.resource_data.ResourceControlPolicy.FIFO,
    process_ids=[production_process.ID],
    )

    adapter = prodsys.production_system_data.ProductionSystemData(
    time_model_data=[welding_time_model, transport_time_model, arrival_time_model, arrival_time_model1],
    dependency_data=[disassembly_dependency, disassembly_dependency2, disassembly_dependency3],
    process_data=[transport_process,production_process, disassembly_process],
    resource_data=[machine, transport_resource, disassemblymachine],
    product_data=[product, mutterprodukt, product2],
    source_data=[ source2],
    sink_data=[sink, sink2, sink3],
    )

    add_default_queues_to_production_system(adapter, reset = False)
        
    return adapter


def test_initialize_simulation(simulation_adapter: ProductionSystemData):
    runner_instance = runner.Runner(production_system_data=simulation_adapter)
    runner_instance.initialize_simulation()


def test_hashing(simulation_adapter: ProductionSystemData):
    hash_str = simulation_adapter.hash()
    assert hash_str == "65388bc54ce7f43e053e5cb005937d8a"


def test_run_simulation(simulation_adapter: ProductionSystemData):
    runner_instance = runner.Runner(production_system_data=simulation_adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(2000)
    runner_instance.print_results()
    assert runner_instance.env.now == 2000
    post_processor = runner_instance.get_post_processor()
    for kpi in post_processor.machine_state_KPIS:
        if kpi.name == "productive_time" and kpi.resource == "Forklift1":
            assert kpi.value < 0.1 and kpi.value > 0.01

        if kpi.name == "productive_time" and kpi.resource == "disassemblymachine 1":
            assert  kpi.value < 1.0

    for kpi in post_processor.WIP_KPIs:
        if kpi.name == "WIP" and kpi.product_type == "product 1":
            assert kpi.value > 0 and kpi.value < 10          
    mutterproduct = 0.0 
    product1 = 0.0 
    product2 = 0.0         
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output":
            if kpi.product_type == "mutterprodukt":
                mutterproduct = kpi.value
            if kpi.product_type == "product 2":
                product2 = kpi.value 
            if kpi.product_type == "product 1":
               product1 = kpi.value
    assert mutterproduct == product1 and mutterproduct == product2
    assert product1 == product2
    

