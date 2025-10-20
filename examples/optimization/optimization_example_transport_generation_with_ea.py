import datetime
import prodsys
from prodsys.models.production_system_data import ProductionSystemData, add_default_queues_to_production_system
from prodsys.models.scenario_data import ReconfigurationEnum
from prodsys.models.performance_indicators import KPIEnum
from prodsys.optimization.adapter_manipulation import add_transformation_operation
from prodsys.optimization.evolutionary_algorithm import (
    EvolutionaryAlgorithmHyperparameters,
)
from prodsys.optimization.optimizer import FileSystemSaveOptimizer, InMemoryOptimizer
prodsys.set_logging("DEBUG")

def main():
    hyper_parameters = EvolutionaryAlgorithmHyperparameters(
        seed=0,
        number_of_generations=10,
        population_size=2,
        mutation_rate=0.15,
        crossover_rate=0.1,
        number_of_seeds=2,
        number_of_processes=4,
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
    ftmp3 = prodsys.time_model_data.FunctionTimeModelData(
        ID="ftmp3",
        description="function time model process 3",
        distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Normal,
        location=0.667,
        scale=0.0667
    )
    ftmp4 = prodsys.time_model_data.FunctionTimeModelData(
        ID="ftmp4",
        description="function time model process 4",
        distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Normal,
        location=3.0,
        scale=0.3
    )
    ftm1 = prodsys.time_model_data.FunctionTimeModelData(
        ID="ftm1",
        description="function time model product 1",
        distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Exponential,
        location=4.05,
        scale=0.0
    )
    ftm2 = prodsys.time_model_data.FunctionTimeModelData(
        ID="ftm2",
        description="function time model product 2",
        distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Exponential,
        location=5.0,
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
    P3 = prodsys.processes_data.ProductionProcessData(
        ID="P3",
        description="Process 3",
        time_model_id="ftmp3",
        type=prodsys.processes_data.ProcessTypeEnum.ProductionProcesses,
    )
    P4 = prodsys.processes_data.ProductionProcessData(
        ID="P4",
        description="Process 4",
        time_model_id="ftmp4",
        type=prodsys.processes_data.ProcessTypeEnum.ProductionProcesses,
    )
    TP1 = prodsys.processes_data.TransportProcessData(
        ID="TP1",
        description="Transport Process 1",
        time_model_id="md1",
        type=prodsys.processes_data.ProcessTypeEnum.TransportProcesses,
    )

    # Port / Queue
    ST1 = prodsys.port_data.QueueData(
        ID="ST1",
        description="Store Q1",
        capacity=0,
        location=[90.0, 90.0],
        port_locations=[[90, 90], [100, 100]],
    )

    # Resource
    R1 = prodsys.resource_data.ResourceData(
        ID="R1",
        description="Resource 1",
        capacity=2,
        location=[0.0, 0.0],
        controller=prodsys.resource_data.ControllerEnum.PipelineController,
        control_policy=prodsys.resource_data.ResourceControlPolicy.FIFO,
        process_ids=["P1", "P2"],
    )
    TR1 = prodsys.resource_data.ResourceData(
        ID="TR1",
        description="Transport Resource 1",
        capacity=1,
        location=[10.0, 10.0],
        controller=prodsys.resource_data.ControllerEnum.PipelineController,
        control_policy=prodsys.resource_data.TransportControlPolicy.SPT_transport,
        process_ids=["TP1"],
    )
    TR2 = prodsys.resource_data.ResourceData(
        ID="TR2",
        description="Transport Resource 2",
        capacity=1,
        location=[10.0, 10.0],
        controller=prodsys.resource_data.ControllerEnum.PipelineController,
        control_policy=prodsys.resource_data.TransportControlPolicy.SPT_transport,
        process_ids=["TP1"],
    )


    # Product
    Product_1 = prodsys.product_data.ProductData(
        ID="Product_1",
        description="Product with sequential process",
        type="Product_1",
        processes=["P1"],
        transport_process="TP1",
    )

    # Source
    S1 = prodsys.source_data.SourceData(
        ID="S1",
        description="Source 1",
        location=[0.0, 0.0],
        product_type="Product_1",
        time_model_id="ftm1",
        routing_heuristic=prodsys.source_data.RoutingHeuristic.shortest_queue
    )

    # Sink
    K1 = prodsys.sink_data.SinkData(
        ID="K1",
        description="Sink 1",
        location=[110.0, 110.0],
        product_type="Product_1",
    )

    Opt = prodsys.scenario_data.ScenarioOptionsData(
        transformations=[
            ReconfigurationEnum.PRODUCTION_CAPACITY,
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
            [0.0, 0.0],
            [50.0, 50.0],
            [100.0, 100.0]
        ]
    )
    #scenario
    Info = prodsys.scenario_data.ScenarioInfoData(
        machine_cost=100,
        transport_resource_cost=50,
        time_range=10000
    )

    objectives = prodsys.scenario_data.Objective(
        name=KPIEnum.THROUGHPUT,
        weight=1.0
    )
    constraints = prodsys.scenario_data.ScenarioConstrainsData(
        max_reconfiguration_cost = 10000000000000000000000000,
        max_num_machines=5,
        max_num_processes_per_machine=2,
        max_num_transport_resources=5,
        target_product_count={"Product_1": 200}
    )
    scenario = prodsys.scenario_data.ScenarioData(options=Opt, info=Info, objectives=[objectives], constraints=constraints)

    # Assemble the production system
    production_system_instance = prodsys.production_system_data.ProductionSystemData(
        time_model_data=[ftmp1, ftmp2, ftmp3, ftmp4, ftm1, ftm2, md1],
        process_data=[P1, P2, P3, P4, TP1],
        port_data=[ST1],
        resource_data=[R1, TR1],
        product_data=[Product_1],
        source_data=[S1],
        sink_data=[K1],
        scenario_data=scenario #, Info, objectives
    )

    add_default_queues_to_production_system(production_system_instance)
    production_system_instance.validate_configuration()
    
    runner = prodsys.runner.Runner(production_system_data=production_system_instance)
    runner.initialize_simulation()
    runner.run(100)
    runner.print_results()
    #runner.plot_results()




    optimizer = FileSystemSaveOptimizer(
        adapter=production_system_instance,
        hyperparameters=hyper_parameters,
        save_folder=f"data/{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}",
        full_save=True,
        # initial_solutions=[base_configuration]
    )
    # optimizer = InMemoryOptimizer(
    #     adapter=base_configuration,
    #     hyperparameters=hyper_parameters,
    # )

    
    optimizer.optimize()


if __name__ == "__main__":
    main()
