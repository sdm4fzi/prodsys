import pytest
from prodsys.models.production_system_data import ProductionSystemData
import prodsys.express as psx
from prodsys import runner


@pytest.fixture
def simulation_adapter() -> ProductionSystemData:
    """
    Test system with lot dependencies (batch processing) and workpiece carriers.
    
    This test validates:
    - LotDependency with carriers (batching transport with carriers)
    - LotDependency without carriers (batching production)
    - PrimitiveDependency (workpiece carriers)
    - Integration of multiple dependency types
    """
    t1 = psx.FunctionTimeModel("constant", 1.8, 0, "t1")

    p1 = psx.ProductionProcess(t1, "p1")

    t3 = psx.DistanceTimeModel(speed=50, reaction_time=0.01, ID="t3")

    carrier_tp = psx.TransportProcess(t3, "carrier_tp")

    work_piece_carrier_storage = psx.Queue(ID="work_piece_carrier_storage", location=[0, 0], capacity=2)

    work_piece_carriers = psx.Primitive(
        ID="work_piece_carriers",
        transport_process=carrier_tp,
        storages=[work_piece_carrier_storage],
        quantity_in_storages=[2],
    )

    lot_dependency_with_carrier = psx.LotDependency(
        min_lot_size=1,
        max_lot_size=4,
        ID="lot_dependency_with_carrier",
    )
    work_piece_carrier_dependency = psx.ToolDependency(
        required_entity=work_piece_carriers
    )

    lot_dependency_without_carrier = psx.LotDependency(
        min_lot_size=2,
        max_lot_size=3,
        ID="lot_dependency_without_carrier",
    )

    machine = psx.Resource(
        [p1],
        [5, 0],
        capacity=5,
        ID="machine",
        dependencies=[lot_dependency_without_carrier],
    )

    tp = psx.TransportProcess(t3, "tp", dependencies=[lot_dependency_with_carrier, work_piece_carrier_dependency])

    transport = psx.Resource([tp], [0, 0], 4, ID="transport")
    carrier_transport = psx.Resource([carrier_tp], [0, 0], 1, ID="carrier_transport")

    product1 = psx.Product([p1], tp, "product1")

    sink1 = psx.Sink(product1, [10, 0], "sink1")

    arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")

    source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")

    system = psx.ProductionSystem([machine, transport, carrier_transport], [source1], [sink1], [work_piece_carriers])
    system.validate()
    adapter = system.to_model()
    return adapter


def test_initialize_simulation(simulation_adapter: ProductionSystemData):
    """Test that the batch controller simulation can be initialized."""
    runner_instance = runner.Runner(production_system_data=simulation_adapter)
    runner_instance.initialize_simulation()


def test_hashing(simulation_adapter: ProductionSystemData):
    """Test that the batch controller system produces a consistent hash."""
    hash_str = simulation_adapter.hash()
    assert hash_str == "055c6e5c35951f8af92c0bfc425fd3d5"


def test_run_simulation(simulation_adapter: ProductionSystemData):
    """
    Test that the batch controller simulation runs successfully with lot dependencies.
    
    This validates:
    - Products are correctly batched in lots according to lot dependencies
    - Workpiece carriers are properly managed (bound/released)
    - Both transport with carriers and production batching work together
    - System completes simulation without errors
    """
    runner_instance = runner.Runner(production_system_data=simulation_adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(1000)
    assert runner_instance.env.now == 1000
    runner_instance.print_results()
    
    post_processor = runner_instance.get_post_processor()
    
    # Check throughput - should be around 1000 products
    for kpi in post_processor.throughput_and_output_KPIs:
        if kpi.name == "output":
            assert kpi.product_type == "product1"
            assert kpi.value > 950 and kpi.value < 1050
    
    # Check machine utilization - with batching (lot size 2-3), utilization is lower
    for kpi in post_processor.machine_state_KPIS:
        if kpi.name == "productive_time" and kpi.resource == "machine":
            assert kpi.value < 55 and kpi.value > 45
        
        # Transport should have moderate utilization
        if kpi.name == "productive_time" and kpi.resource == "transport":
            assert kpi.value < 25 and kpi.value > 15
        
        # Carrier transport should have moderate utilization
        if kpi.name == "productive_time" and kpi.resource == "carrier_transport":
            assert kpi.value < 35 and kpi.value > 25
    
    # Check WIP - batching can increase WIP slightly
    for kpi in post_processor.WIP_KPIs:
        if kpi.name == "WIP" and kpi.product_type == "product1":
            assert kpi.value < 9 and kpi.value > 8
    
    # Check primitive WIP for workpiece carriers
    for kpi in post_processor.primitive_WIP_KPIs:
        if kpi.name == "primitive_WIP" and kpi.product_type == "work_piece_carriers":
            assert kpi.value < 2.0 and kpi.value > 1
    
    # Check throughput time - should be reasonable with batching
    for kpi in post_processor.aggregated_throughput_time_KPIs:
        if kpi.name == "throughput_time":
            assert kpi.value < 9.0 and kpi.value > 7.0

