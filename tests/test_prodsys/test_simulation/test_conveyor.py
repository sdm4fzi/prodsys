import pytest
from prodsys.models.production_system_data import ProductionSystemData, add_default_queues_to_production_system
from prodsys import runner
from prodsys.util.node_link_generation import node_link_generation
import prodsys
from prodsys.models.scenario_data import ReconfigurationEnum
from prodsys.models.performance_indicators import KPIEnum
from prodsys.optimization.adapter_manipulation import add_transformation_operation
from prodsys.optimization.evolutionary_algorithm import EvolutionaryAlgorithmHyperparameters
from prodsys.optimization.optimizer import FileSystemSaveOptimizer, InMemoryOptimizer
from prodsys.util.node_link_generation import node_link_generation

@pytest.fixture
def simulation_adapter() -> ProductionSystemData:
    hyper_parameters = EvolutionaryAlgorithmHyperparameters(
        seed=0,
        number_of_generations=64,
        population_size=16,
        mutation_rate=0.4,
        crossover_rate=0.2,
        number_of_seeds=2,
        number_of_processes=1
    )

    def new_transformation(adapter: ProductionSystemData) -> bool:
        print("Mutation function called.")

    add_transformation_operation(
        transformation=ReconfigurationEnum.PRODUCTION_CAPACITY,
        operation=new_transformation,
    )

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
    CTP = prodsys.processes_data.LinkTransportProcessData( #empty links, to be generated
        ID="ConveyorProcess_1",
        description="Transport Process 1",
        time_model_id="md1",
        capability="TP1",
        type=prodsys.processes_data.ProcessTypeEnum.LinkTransportProcesses,
        links=[],
        can_move=False,
    )
    TP1 = prodsys.processes_data.RequiredCapabilityProcessData(
        ID="TP1",
        description="Required Capability Process 1",
        capability="TP1",
        type=prodsys.processes_data.ProcessTypeEnum.RequiredCapabilityProcesses,
    )


    # Resource
    R1 = prodsys.resource_data.ResourceData( #resource with two ports
        ID="R1",
        description="Resource 1",
        capacity=2,
        location=[0.0, 0.0],
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
        process_ids=["ConveyorProcess_1"],
        can_move=False,
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

    Opt = prodsys.scenario_data.ScenarioOptionsData(
        transformations=[
            ReconfigurationEnum.TRANSPORT_CAPACITY#,
            #ReconfigurationEnum.LAYOUT
        ],
        machine_controllers=[
            prodsys.resource_data.ResourceControlPolicy.FIFO,
            prodsys.resource_data.ResourceControlPolicy.SPT
        ],
        transport_controllers=[
            prodsys.resource_data.TransportControlPolicy.SPT_transport,
            prodsys.resource_data.TransportControlPolicy.FIFO
        ],
        routing_heuristics=[
            prodsys.source_data.RoutingHeuristic.random,
            prodsys.source_data.RoutingHeuristic.shortest_queue,
            prodsys.source_data.RoutingHeuristic.FIFO
        ],
        positions=[
            [50.0, 50.0],
            [110, 110],
            [90.0, 90.0],
            [-50.0, -50.0],
            [50.0, 50.0],
            [0,50],
            [0,-50],
            [50.0, 0],
            [100,100],
            [-100,-100],
            [0,0],
            [10,10],
            [-10,-10],
        ]
    )
    #scenario
    Info = prodsys.scenario_data.ScenarioInfoData(
        machine_cost=10,
        transport_resource_cost=5,
        time_range=1000,
        process_module_cost=2,
    )

    objectives = prodsys.scenario_data.Objective(
        name=KPIEnum.THROUGHPUT,
        weight=1.0
    )
    constraints = prodsys.scenario_data.ScenarioConstrainsData(
        max_reconfiguration_cost = 10,
        max_num_machines=50,
        max_num_processes_per_machine=20,
        max_num_transport_resources=5,
        target_product_count={"Product_1": 200}
    )
    scenario = prodsys.scenario_data.ScenarioData(options=Opt, info=Info, objectives=[objectives], constraints=constraints)
    
    # Assemble the production system
    production_system_instance = ProductionSystemData(
        time_model_data=[ftmp1, ftmp2, ftm1, md1],
        process_data=[P1, P2, CTP, TP1],
        #port_data=[Port0, Port1],
        resource_data=[R1, TR1, R2],
        product_data=[Product_1],
        source_data=[S1],
        sink_data=[K1],
        scenario_data=scenario,
        valid_configuration=True,
        node_data=[]
    )
    add_default_queues_to_production_system(production_system_instance, reset=False)
    node_link_generation.generate_and_apply_network(production_system_instance, simple_connection=True, visualize=False)
    
    return production_system_instance


def test_initialize_simulation(simulation_adapter: ProductionSystemData):
    runner_instance = runner.Runner(production_system_data=simulation_adapter)
    runner_instance.initialize_simulation()


def test_hashing(simulation_adapter: ProductionSystemData):
    hash_str = simulation_adapter.hash()
    assert hash_str == "e2125706d6d4d4a47c81c1f7fc71bcfd"


def test_run_simulation(simulation_adapter: ProductionSystemData):
    runner_instance = runner.Runner(production_system_data=simulation_adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(500)
    assert runner_instance.env.now == 500
    post_processor = runner_instance.get_post_processor()
    for kpi in post_processor.df_aggregated_output:
        assert kpi > 1

    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output":
            if kpi.product_type == "Product_1":
                assert 45 < kpi.value < 80