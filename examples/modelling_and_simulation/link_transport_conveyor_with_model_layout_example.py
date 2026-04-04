"""
Link-transport (conveyor) simulation with model-driven layout planning.

This example is the model-driven equivalent of
``link_transport_conveyor_with_xml_layout_input_example.py``.  The floor-plan
is described entirely inside ``ProductionSystemData`` via ``layout_data`` –
no external XML file is required.

Features demonstrated:

- ``LayoutAreaData``    – rectangular traversable area.
- ``ObstacleData``      – a structural column that blocks path planning.
- ``ResourceFootprint`` – physical bounding-box of each machine.

Coordinate system (units roughly centimetres):

        S1 (-150, -100)          K1 (150, 100)
        R1 (-100, -100)          R2 (  0, -50)
        TR1 (0, 50)   [conveyor carrier start]
        Pillar (-50, -50)
"""

import prodsys
from prodsys.models.production_system_data import (
    ProductionSystemData,
    add_default_queues_to_production_system,
)
from prodsys.models.layout_data import LayoutData, LayoutAreaData, ObstacleData, ResourceFootprint
from prodsys.util.node_link_generation import node_link_generation


def main():
    # ------------------------------------------------------------------
    # Time models
    # ------------------------------------------------------------------
    ftmp1 = prodsys.time_model_data.FunctionTimeModelData(
        ID="ftmp1",
        description="process 1 time model",
        distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Normal,
        location=0.833,
        scale=0.0833,
    )
    ftmp2 = prodsys.time_model_data.FunctionTimeModelData(
        ID="ftmp2",
        description="process 2 time model",
        distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Normal,
        location=4.167,
        scale=0.4167,
    )
    ftm1 = prodsys.time_model_data.FunctionTimeModelData(
        ID="ftm1",
        description="inter-arrival time model",
        distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Exponential,
        location=10.05,
        scale=0.0,
    )
    md1 = prodsys.time_model_data.DistanceTimeModelData(
        ID="md1",
        description="Conveyor travel time model",
        speed=60.0,
        reaction_time=0.033,
        metric="manhattan",
    )

    # ------------------------------------------------------------------
    # Processes – can_move=False → fixed-path (conveyor) link transport.
    # ------------------------------------------------------------------
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
    TP1 = prodsys.processes_data.LinkTransportProcessData(
        ID="TP1",
        description="Conveyor transport process",
        time_model_id="md1",
        capability="TP1",
        type=prodsys.processes_data.ProcessTypeEnum.LinkTransportProcesses,
        links=[],
        can_move=False,
    )

    # ------------------------------------------------------------------
    # Resources
    # ------------------------------------------------------------------
    R1 = prodsys.resource_data.ResourceData(
        ID="R1",
        description="Machine 1",
        capacity=2,
        location=[-100, -100],
        controller=prodsys.resource_data.ControllerEnum.PipelineController,
        control_policy=prodsys.resource_data.ResourceControlPolicy.FIFO,
        process_ids=["P1", "P2"],
        footprint=ResourceFootprint(width=50.0, height=50.0),
    )
    R2 = prodsys.resource_data.ResourceData(
        ID="R2",
        description="Machine 2",
        capacity=2,
        location=[0, -50],
        controller=prodsys.resource_data.ControllerEnum.PipelineController,
        control_policy=prodsys.resource_data.ResourceControlPolicy.FIFO,
        process_ids=["P1", "P2"],
        footprint=ResourceFootprint(width=50.0, height=50.0),
    )
    TR1 = prodsys.resource_data.ResourceData(
        ID="TR1",
        description="Conveyor carrier",
        capacity=1,
        location=[0, 50],
        controller=prodsys.resource_data.ControllerEnum.PipelineController,
        control_policy=prodsys.resource_data.TransportControlPolicy.SPT_transport,
        process_ids=["TP1"],
        can_move=False,
    )

    # ------------------------------------------------------------------
    # Product / Source / Sink
    # ------------------------------------------------------------------
    Product_1 = prodsys.product_data.ProductData(
        ID="Product_1",
        description="",
        type="Product_1",
        processes=["P1", "P2"],
        transport_process="TP1",
    )
    S1 = prodsys.source_data.SourceData(
        ID="S1",
        description="Source 1",
        location=[-150.0, -100.0],
        product_type="Product_1",
        time_model_id="ftm1",
        routing_heuristic=prodsys.source_data.RoutingHeuristic.shortest_queue,
    )
    K1 = prodsys.sink_data.SinkData(
        ID="K1",
        description="Sink 1",
        location=[150.0, 100.0],
        product_type="Product_1",
    )

    # ------------------------------------------------------------------
    # Layout – model-driven, single floor area + one structural column.
    # ------------------------------------------------------------------
    layout = LayoutData(
        areas=[
            LayoutAreaData(
                ID="production_floor",
                description="Main production bay",
                x_min=-200.0,
                y_min=-175.0,
                x_max=200.0,
                y_max=150.0,
            ),
        ],
        obstacles=[
            ObstacleData(
                ID="Column_A",
                description="Structural column in the centre aisle",
                location=[-50.0, -50.0],
                width=30.0,
                height=30.0,
            ),
        ],
    )

    # ------------------------------------------------------------------
    # Assemble production system
    # ------------------------------------------------------------------
    production_system = ProductionSystemData(
        time_model_data=[ftmp1, ftmp2, ftm1, md1],
        process_data=[P1, P2, TP1],
        resource_data=[R1, R2, TR1],
        product_data=[Product_1],
        source_data=[S1],
        sink_data=[K1],
        layout_data=layout,
        node_data=[],
    )
    add_default_queues_to_production_system(production_system, reset=False)

    # ------------------------------------------------------------------
    # Relocate machine ports from centre to the right-hand footprint edge.
    # Products are loaded / unloaded at the machine boundary, so the conveyor
    # carrier navigates to the edge rather than the geometric centre.
    # ------------------------------------------------------------------
    node_link_generation.relocate_ports_to_footprint_boundary(production_system, side="right")

    # ------------------------------------------------------------------
    # Generate conveyor network from the model – no XML file needed.
    # ------------------------------------------------------------------
    node_link_generation.generate_and_apply_network(
        production_system,
        style="grid",
        simple_connection=True,
    )

    # ------------------------------------------------------------------
    # Validate the generated layout
    # All three checks are exposed as public functions in node_link_generation
    # so they can be reused in tests and other examples.
    # ------------------------------------------------------------------
    print("\nRunning layout validations …")
    node_link_generation.validate_ports_on_footprint_boundary(production_system)
    node_link_generation.validate_all_ports_connected(production_system)
    node_link_generation.validate_no_links_cross_footprints(production_system)
    print("All layout validations passed.\n")

    # ------------------------------------------------------------------
    # Visualise with plot_layout
    # ------------------------------------------------------------------
    node_link_generation.plot_layout(
        production_system,
        title="Conveyor Layout – model-driven (area + obstacle + footprints)",
    )

    # ------------------------------------------------------------------
    # Simulate
    # ------------------------------------------------------------------
    production_system.write("examples/modelling_and_simulation/simulation_example_data/link_transport_conveyor_with_model_layout_example.json")
    runner = prodsys.runner.Runner(production_system_data=production_system)
    runner.initialize_simulation()
    runner.run(500)
    runner.print_results()


if __name__ == "__main__":
    main()
