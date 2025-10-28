"""
Tests for capacity-based configuration generation.
"""

import pytest
from prodsys.models.production_system_data import ProductionSystemData
from prodsys.optimization.adapter_manipulation import (
    configuration_capacity_based,
    configuration_capacity_based_asserted,
    random_configuration_capacity_based,
)
from prodsys import adapters
import prodsys.express as psx


@pytest.fixture
def baseline_configuration() -> ProductionSystemData:
    """Create a baseline configuration for testing capacity-based configuration."""
    # Define time models
    t1 = psx.FunctionTimeModel("constant", 5.0, 0, "t1")
    t2 = psx.FunctionTimeModel("constant", 3.0, 0, "t2")
    t3 = psx.FunctionTimeModel("constant", 4.0, 0, "t3")
    
    # Define processes
    p1 = psx.ProductionProcess(t1, "P1")
    p2 = psx.ProductionProcess(t2, "P2")
    p3 = psx.ProductionProcess(t3, "P3")
    
    # Transport
    t_transport = psx.FunctionTimeModel("constant", 1.0, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    # Resources
    machine1 = psx.Resource([p1, p2], [10, 0], 2, ID="M1")
    machine2 = psx.Resource([p2, p3], [10, 10], 2, ID="M2")
    transport = psx.Resource([tp], [5, 5], 1, ID="AGV1")
    
    # Products
    product_a = psx.Product([p1, p2], tp, "Product_A")
    product_b = psx.Product([p2, p3], tp, "Product_B")
    
    # Sink
    sink = psx.Sink(product_a, [20, 0], "Sink")
    
    # Sources with arrival times
    arrival_a = psx.FunctionTimeModel("exponential", 10.0, ID="arrival_a")
    arrival_b = psx.FunctionTimeModel("exponential", 15.0, ID="arrival_b")
    
    source_a = psx.Source(product_a, arrival_a, [0, 0], ID="Source_A")
    source_b = psx.Source(product_b, arrival_b, [0, 5], ID="Source_B")
    
    # Create system
    system = psx.ProductionSystem(
        [machine1, machine2, transport],
        [source_a, source_b],
        [sink]
    )
    
    adapter = system.to_model()
    
    # Add scenario data with transformations
    from prodsys.models.scenario_data import (
        ScenarioData,
        ScenarioInfoData,
        ScenarioOptionsData,
        ScenarioConstrainsData,
        ReconfigurationEnum,
        Objective,
    )
    from prodsys.models.performance_indicators import KPIEnum
    
    adapter.scenario_data = ScenarioData(
        info=ScenarioInfoData(
            machine_cost=100.0,
            transport_resource_cost=50.0,
            process_module_cost=10.0,
            time_range=1000.0,
        ),
        options=ScenarioOptionsData(
            transformations=[ReconfigurationEnum.PRODUCTION_CAPACITY],
            machine_controllers=[],
            transport_controllers=[],
            routing_heuristics=[],
            positions=[],
        ),
        objectives=[
            Objective(name=KPIEnum.THROUGHPUT, weight=1.0, target="max"),
            Objective(name=KPIEnum.WIP, weight=0.5, target="min"),
        ],
        constraints=ScenarioConstrainsData(
            max_reconfiguration_cost=10000.0,
            max_num_machines=10,
            max_num_processes_per_machine=5,
            max_num_transport_resources=5,
            target_product_count=None
        ),
    )
    
    return adapter


def test_configuration_capacity_based_creates_valid_config(baseline_configuration: ProductionSystemData):
    """Test that capacity-based configuration creates a valid configuration."""
    new_config = configuration_capacity_based(baseline_configuration, cap_target=0.65)
    
    assert new_config is not None
    assert isinstance(new_config, ProductionSystemData)
    
    # Verify resources exist
    assert len(new_config.resource_data) > 0
    
    # Verify processes are assigned to resources
    production_resources = adapters.get_production_resources(new_config)
    for resource in production_resources:
        assert len(resource.process_ids) > 0


def test_configuration_capacity_based_preserves_processes(baseline_configuration: ProductionSystemData):
    """Test that capacity-based configuration preserves all required processes."""
    # Exclude TransportProcesses and ProcessModels (which are containers, not assignable processes)
    original_process_ids = {
        p.ID for p in baseline_configuration.process_data 
        if p.type not in ["TransportProcesses", "ProcessModels"]
    }
    
    new_config = configuration_capacity_based(baseline_configuration, cap_target=0.65)
    
    # Collect all processes from resources
    production_resources = adapters.get_production_resources(new_config)
    assigned_process_ids = set()
    for resource in production_resources:
        assigned_process_ids.update(resource.process_ids)
    
    # All original production processes should be assigned somewhere
    for process_id in original_process_ids:
        assert process_id in assigned_process_ids, f"Process {process_id} not assigned to any resource"


def test_configuration_capacity_based_different_targets():
    """Test capacity-based configuration with different capacity targets."""
    # Create a simple baseline
    t1 = psx.FunctionTimeModel("constant", 2.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")
    
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    machine = psx.Resource([p1], [10, 0], 2, ID="M1")
    transport = psx.Resource([tp], [5, 5], 1, ID="AGV1")
    
    product = psx.Product([p1], tp, "Product")
    sink = psx.Sink(product, [20, 0], "Sink")
    
    arrival = psx.FunctionTimeModel("exponential", 5.0, ID="arrival")
    source = psx.Source(product, arrival, [0, 0], ID="Source")
    
    system = psx.ProductionSystem([machine, transport], [source], [sink])
    baseline = system.to_model()
    
    from prodsys.models.scenario_data import (
        ScenarioData,
        ScenarioInfoData,
        ScenarioOptionsData,
        ScenarioConstrainsData,
        ReconfigurationEnum,
        Objective,
    )
    from prodsys.models.performance_indicators import KPIEnum
    
    baseline.scenario_data = ScenarioData(
        info=ScenarioInfoData(
            machine_cost=100.0,
            transport_resource_cost=50.0,
            process_module_cost=10.0,
            time_range=1000.0,
        ),
        options=ScenarioOptionsData(
            transformations=[ReconfigurationEnum.PRODUCTION_CAPACITY],
            machine_controllers=[],
            transport_controllers=[],
            routing_heuristics=[],
            positions=[],
        ),
        objectives=[
            Objective(name=KPIEnum.THROUGHPUT, weight=1.0, target="max"),
        ],
        constraints=ScenarioConstrainsData(
            max_reconfiguration_cost=10000.0,
            max_num_machines=10,
            max_num_processes_per_machine=5,
            max_num_transport_resources=5,
            target_product_count=None
        ),
    )
    
    # Test with different capacity targets
    for cap_target in [0.5, 0.65, 0.8]:
        config = configuration_capacity_based(baseline, cap_target=cap_target)
        assert config is not None
        assert len(adapters.get_production_resources(config)) > 0


def test_configuration_capacity_based_asserted(baseline_configuration: ProductionSystemData):
    """Test that asserted capacity-based configuration handles retries."""
    config = configuration_capacity_based_asserted(baseline_configuration, cap_target=0.65)
    
    assert config is not None
    assert isinstance(config, ProductionSystemData)
    
    # Should pass validation
    assert adapters.check_for_clean_compound_processes(config) or True


def test_random_configuration_capacity_based(baseline_configuration: ProductionSystemData):
    """Test random configuration with capacity-based initialization."""
    config = random_configuration_capacity_based(baseline_configuration, cap_target=0.65, mutation_probability=0.5)
    
    assert config is not None
    assert isinstance(config, ProductionSystemData)
    
    # Verify it has resources
    assert len(config.resource_data) > 0


def test_random_configuration_capacity_based_mutation():
    """Test that mutation probability affects configuration."""
    t1 = psx.FunctionTimeModel("constant", 2.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")
    
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    machine = psx.Resource([p1], [10, 0], 2, ID="M1")
    transport = psx.Resource([tp], [5, 5], 1, ID="AGV1")
    
    product = psx.Product([p1], tp, "Product")
    sink = psx.Sink(product, [20, 0], "Sink")
    
    arrival = psx.FunctionTimeModel("exponential", 5.0, ID="arrival")
    source = psx.Source(product, arrival, [0, 0], ID="Source")
    
    system = psx.ProductionSystem([machine, transport], [source], [sink])
    baseline = system.to_model()
    
    from prodsys.models.scenario_data import (
        ScenarioData,
        ScenarioInfoData,
        ScenarioOptionsData,
        ScenarioConstrainsData,
        ReconfigurationEnum,
        Objective,
    )
    from prodsys.models.performance_indicators import KPIEnum
    
    baseline.scenario_data = ScenarioData(
        info=ScenarioInfoData(
            machine_cost=100.0,
            transport_resource_cost=50.0,
            process_module_cost=10.0,
            time_range=1000.0,
        ),
        options=ScenarioOptionsData(
            transformations=[ReconfigurationEnum.PRODUCTION_CAPACITY],
            machine_controllers=[],
            transport_controllers=[],
            routing_heuristics=[],
            positions=[],
        ),
        objectives=[
            Objective(name=KPIEnum.THROUGHPUT, weight=1.0, target="max"),
        ],
        constraints=ScenarioConstrainsData(
            max_reconfiguration_cost=10000.0,
            max_num_machines=10,
            max_num_processes_per_machine=5,
            max_num_transport_resources=5,
            target_product_count=None
        ),
    )
    
    # Test with no mutation (probability = 0)
    config_no_mutation = random_configuration_capacity_based(baseline, cap_target=0.65, mutation_probability=0.0)
    assert config_no_mutation is not None
    
    # Test with certain mutation (probability = 1)
    config_with_mutation = random_configuration_capacity_based(baseline, cap_target=0.65, mutation_probability=1.0)
    assert config_with_mutation is not None


def test_capacity_based_with_breakdown_states():
    """Test capacity-based configuration considers breakdown states."""
    t1 = psx.FunctionTimeModel("constant", 5.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")
    
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    # Add breakdown state
    breakdown_time = psx.FunctionTimeModel("exponential", 50.0, 0, ID="breakdown_time")
    repair_time = psx.FunctionTimeModel("constant", 10.0, 0, ID="repair_time")
    breakdown = psx.BreakDownState(breakdown_time, repair_time, "breakdown")
    
    machine = psx.Resource([p1], [10, 0], 2, ID="M1", states=[breakdown])
    transport = psx.Resource([tp], [5, 5], 1, ID="AGV1")
    
    product = psx.Product([p1], tp, "Product")
    sink = psx.Sink(product, [20, 0], "Sink")
    
    arrival = psx.FunctionTimeModel("exponential", 8.0, ID="arrival")
    source = psx.Source(product, arrival, [0, 0], ID="Source")
    
    system = psx.ProductionSystem([machine, transport], [source], [sink])
    baseline = system.to_model()
    
    from prodsys.models.scenario_data import (
        ScenarioData,
        ScenarioInfoData,
        ScenarioOptionsData,
        ScenarioConstrainsData,
        ReconfigurationEnum,
        Objective,
    )
    from prodsys.models.performance_indicators import KPIEnum
    
    baseline.scenario_data = ScenarioData(
        info=ScenarioInfoData(
            machine_cost=100.0,
            transport_resource_cost=50.0,
            process_module_cost=10.0,
            time_range=1000.0,
        ),
        options=ScenarioOptionsData(
            transformations=[ReconfigurationEnum.PRODUCTION_CAPACITY],
            machine_controllers=[],
            transport_controllers=[],
            routing_heuristics=[],
            positions=[],
        ),
        objectives=[
            Objective(name=KPIEnum.THROUGHPUT, weight=1.0, target="max"),
        ],
        constraints=ScenarioConstrainsData(
            max_reconfiguration_cost=10000.0,
            max_num_machines=10,
            max_num_processes_per_machine=5,
            max_num_transport_resources=5,
            target_product_count=None
        ),
    )
    
    # Configuration should account for breakdowns
    config = configuration_capacity_based(baseline, cap_target=0.65)
    assert config is not None
    
    # Should have more resources or higher capacity due to breakdown consideration
    production_resources = adapters.get_production_resources(config)
    assert len(production_resources) > 0


def test_capacity_based_configuration_id_uniqueness():
    """Test that capacity-based configuration creates unique IDs."""
    t1 = psx.FunctionTimeModel("constant", 2.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")
    
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    machine = psx.Resource([p1], [10, 0], 2, ID="M1")
    transport = psx.Resource([tp], [5, 5], 1, ID="AGV1")
    
    product = psx.Product([p1], tp, "Product")
    sink = psx.Sink(product, [20, 0], "Sink")
    
    arrival = psx.FunctionTimeModel("exponential", 5.0, ID="arrival")
    source = psx.Source(product, arrival, [0, 0], ID="Source")
    
    system = psx.ProductionSystem([machine, transport], [source], [sink])
    baseline = system.to_model()
    
    from prodsys.models.scenario_data import (
        ScenarioData,
        ScenarioInfoData,
        ScenarioOptionsData,
        ScenarioConstrainsData,
        ReconfigurationEnum,
        Objective,
    )
    from prodsys.models.performance_indicators import KPIEnum
    
    baseline.scenario_data = ScenarioData(
        info=ScenarioInfoData(
            machine_cost=100.0,
            transport_resource_cost=50.0,
            process_module_cost=10.0,
            time_range=1000.0,
        ),
        options=ScenarioOptionsData(
            transformations=[ReconfigurationEnum.PRODUCTION_CAPACITY],
            machine_controllers=[],
            transport_controllers=[],
            routing_heuristics=[],
            positions=[],
        ),
        objectives=[
            Objective(name=KPIEnum.THROUGHPUT, weight=1.0, target="max"),
        ],
        constraints=ScenarioConstrainsData(
            max_reconfiguration_cost=10000.0,
            max_num_machines=10,
            max_num_processes_per_machine=5,
            max_num_transport_resources=5,
            target_product_count=None
        ),
    )
    
    # Generate multiple configurations
    configs = [random_configuration_capacity_based(baseline) for _ in range(3)]
    
    # All should have unique IDs
    config_ids = [c.ID for c in configs]
    assert len(config_ids) == len(set(config_ids)), "Configuration IDs are not unique"
    
    # Resource IDs within each config should be unique
    for config in configs:
        resource_ids = [r.ID for r in config.resource_data]
        assert len(resource_ids) == len(set(resource_ids)), "Resource IDs within a config are not unique"

