import prodsys
import os
from prodsys.models.production_system_data import ProductionSystemData, add_default_queues_to_production_system
from prodsys.util.node_link_generation import node_link_generation


def main():

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

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(BASE_DIR, "simulation_example_data", "FreeSpace.drawio.xml")
    node_link_generation.generate_and_apply_network(production_system_instance, path, visualize=True, style="random", simple_connection=False)
    prodsys.set_logging("DEBUG")
    runner = prodsys.runner.Runner(production_system_data=production_system_instance)
    runner.initialize_simulation()
    runner.run(500)
    runner.print_results()
    #runner.plot_results()
    #runner.save_results_as_csv() 

if __name__ == "__main__":
    main()
