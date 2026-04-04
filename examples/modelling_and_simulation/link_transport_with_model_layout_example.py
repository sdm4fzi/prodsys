"""
Link-transport (AGV) simulation with model-driven layout planning.

This example is the model-driven equivalent of
``link_transport_with_xml_layout_input_example.py``.  Instead of supplying a
draw.io XML file, the floor-plan is described entirely inside the
``ProductionSystemData`` using the new ``layout_data`` field:

- ``LayoutAreaData``    – rectangular traversable areas.
- ``ObstacleData``      – physical obstacles (pillars, walls …) that block paths.
- ``ResourceFootprint`` – physical bounding-box of each machine so that the
  path planner leaves clearance around it.

The node/link network is generated automatically with
``generate_and_apply_network``.  No external file is required.

Coordinate system (units match the underlying planner, roughly centimetres):

        S1 (-150, -100)          K1 (150, 100)
        R1 (-100, -100)          R2 (  0, -50)
        TR1 (0, 50)   [AGV start]
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
        description="AGV travel time model",
        speed=60.0,
        reaction_time=0.033,
        metric="manhattan",
    )

    # ------------------------------------------------------------------
    # Processes – links left empty, generated automatically below.
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
        description="AGV transport process",
        time_model_id="md1",
        capability="TP1",
        type=prodsys.processes_data.ProcessTypeEnum.LinkTransportProcesses,
        links=[],
        can_move=True,
    )

    # ------------------------------------------------------------------
    # Resources
    # Footprint sizes (50×50) are chosen so that trajectory nodes land
    # well inside the floor area.  S1 is placed at a distinct location
    # that does NOT fall inside any machine's bounding box.
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
        description="AGV",
        capacity=1,
        location=[0, 50],
        controller=prodsys.resource_data.ControllerEnum.PipelineController,
        control_policy=prodsys.resource_data.TransportControlPolicy.SPT_transport,
        process_ids=["TP1"],
        can_move=True,
    )

    # ------------------------------------------------------------------
    # Product / Source / Sink
    # S1 at (-150, -100): left of R1's footprint [-125,-125]→[-75,-75]
    # K1 at (150, 100): well away from R2
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
    # Layout – model-driven, single floor area + one structural pillar.
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
                ID="Pillar_A",
                description="Centre-aisle structural pillar",
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
    # Products are picked up / dropped off at the machine boundary, so the
    # AGV navigates to the edge rather than the geometric centre.
    # ------------------------------------------------------------------
    node_link_generation.relocate_ports_to_footprint_boundary(production_system, side="right")

    # ------------------------------------------------------------------
    # Generate node/link network from the model – no XML file needed.
    # ------------------------------------------------------------------
    node_link_generation.generate_and_apply_network(
        production_system,
        style="grid",
        simple_connection=True,
    )

    # ------------------------------------------------------------------
    # Visualise with plot_layout
    # ------------------------------------------------------------------
    node_link_generation.plot_layout(
        production_system,
        title="AGV Layout – model-driven (area + obstacle + footprints)",
    )

    # ------------------------------------------------------------------
    # Simulate
    # ------------------------------------------------------------------
    runner = prodsys.runner.Runner(production_system_data=production_system)
    runner.initialize_simulation()
    runner.run(500)
    runner.print_results()


if __name__ == "__main__":
    main()
