"""
Tests for schedule-based and CONWIP production control features.
"""

import json
import pytest
from prodsys.models.production_system_data import ProductionSystemData
from prodsys.models.performance_data import Event
from prodsys import runner
import prodsys.express as psx
from pydantic import ValidationError


@pytest.fixture
def basic_system() -> ProductionSystemData:
    """Create a basic production system for testing."""
    t1 = psx.FunctionTimeModel("constant", 5.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")
    
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    resource = psx.Resource([p1], [10, 0], 1, ID="R1")
    transport = psx.Resource([tp], [5, 0], 1, ID="AGV1")
    
    product = psx.Product([p1], tp, "Product_A")
    
    sink = psx.Sink(product, [20, 0], "Sink")
    
    arrival_model = psx.FunctionTimeModel("constant", 10.0, ID="arrival_model")
    source = psx.Source(product, arrival_model, [0, 0], ID="Source")
    
    system = psx.ProductionSystem([resource, transport], [source], [sink])
    return system.to_model()


@pytest.fixture
def system_with_valid_schedule(basic_system: ProductionSystemData) -> ProductionSystemData:
    """Create a system with a valid schedule."""
    schedule = [
        Event(
            time=0.0,
            resource="R1",
            state="P1",
            state_type="Production",
            activity="start state",
            product="Product_A_1",
            expected_end_time=5.0,
            process="P1"
        ),
        Event(
            time=10.0,
            resource="R1",
            state="P1",
            state_type="Production",
            activity="start state",
            product="Product_A_2",
            expected_end_time=15.0,
            process="P1"
        ),
        Event(
            time=20.0,
            resource="R1",
            state="P1",
            state_type="Production",
            activity="start state",
            product="Product_A_3",
            expected_end_time=25.0,
            process="P1"
        ),
    ]
    basic_system.schedule = schedule
    return basic_system


def test_schedule_validation_valid(system_with_valid_schedule: ProductionSystemData):
    """Test that a valid schedule passes validation."""
    assert system_with_valid_schedule.schedule is not None
    assert len(system_with_valid_schedule.schedule) == 3
    
    # Verify all events are "start state" events (as filtered by validator)
    for event in system_with_valid_schedule.schedule:
        assert event.activity == "start state"


def test_schedule_validation_invalid_resource():
    """Test that schedule validation fails for invalid resource."""
    t1 = psx.FunctionTimeModel("constant", 5.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")
    
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    resource = psx.Resource([p1], [10, 0], 1, ID="R1")
    transport = psx.Resource([tp], [5, 0], 1, ID="AGV1")
    
    product = psx.Product([p1], tp, "Product_A")
    
    sink = psx.Sink(product, [20, 0], "Sink")
    arrival_model = psx.FunctionTimeModel("constant", 10.0, ID="arrival_model")
    source = psx.Source(product, arrival_model, [0, 0], ID="Source")
    
    system = psx.ProductionSystem([resource, transport], [source], [sink])
    adapter = system.to_model()
    
    # Create schedule with invalid resource ID
    invalid_schedule = [
        Event(
            time=0.0,
            resource="INVALID_RESOURCE",  # This resource doesn't exist
            state="P1",
            state_type="Production",
            activity="start state",
            product="Product_A_1",
            expected_end_time=5.0,
            process="P1"
        ),
    ]
    
    with pytest.raises(ValidationError) as exc_info:
        adapter.schedule = invalid_schedule
        ProductionSystemData.model_validate(adapter)
    
    assert "resources" in str(exc_info.value).lower()


def test_schedule_validation_invalid_process():
    """Test that schedule validation fails for invalid process."""
    t1 = psx.FunctionTimeModel("constant", 5.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")
    
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    resource = psx.Resource([p1], [10, 0], 1, ID="R1")
    transport = psx.Resource([tp], [5, 0], 1, ID="AGV1")
    
    product = psx.Product([p1], tp, "Product_A")
    
    sink = psx.Sink(product, [20, 0], "Sink")
    arrival_model = psx.FunctionTimeModel("constant", 10.0, ID="arrival_model")
    source = psx.Source(product, arrival_model, [0, 0], ID="Source")
    
    system = psx.ProductionSystem([resource, transport], [source], [sink])
    adapter = system.to_model()
    
    # Create schedule with invalid process ID
    invalid_schedule = [
        Event(
            time=0.0,
            resource="R1",
            state="INVALID_PROCESS",  # This process doesn't exist
            state_type="Production",
            activity="start state",
            product="Product_A_1",
            expected_end_time=5.0,
            process="INVALID_PROCESS"
        ),
    ]
    
    with pytest.raises(ValidationError) as exc_info:
        adapter.schedule = invalid_schedule
        ProductionSystemData.model_validate(adapter)
    
    assert "processes" in str(exc_info.value).lower()


def test_schedule_validation_invalid_product():
    """Test that schedule validation fails for invalid product."""
    t1 = psx.FunctionTimeModel("constant", 5.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")
    
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    resource = psx.Resource([p1], [10, 0], 1, ID="R1")
    transport = psx.Resource([tp], [5, 0], 1, ID="AGV1")
    
    product = psx.Product([p1], tp, "Product_A")
    
    sink = psx.Sink(product, [20, 0], "Sink")
    arrival_model = psx.FunctionTimeModel("constant", 10.0, ID="arrival_model")
    source = psx.Source(product, arrival_model, [0, 0], ID="Source")
    
    system = psx.ProductionSystem([resource, transport], [source], [sink])
    adapter = system.to_model()
    
    # Create schedule with invalid product ID (without _index suffix)
    invalid_schedule = [
        Event(
            time=0.0,
            resource="R1",
            state="P1",
            state_type="Production",
            activity="start state",
            product="INVALID_PRODUCT_1",  # This product doesn't exist
            expected_end_time=5.0,
            process="P1"
        ),
    ]
    
    with pytest.raises(ValidationError) as exc_info:
        adapter.schedule = invalid_schedule
        ProductionSystemData.model_validate(adapter)
    
    assert "products" in str(exc_info.value).lower()


def test_schedule_filters_non_start_events():
    """Test that only 'start state' events are kept in the schedule."""
    t1 = psx.FunctionTimeModel("constant", 5.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")
    
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    resource = psx.Resource([p1], [10, 0], 1, ID="R1")
    transport = psx.Resource([tp], [5, 0], 1, ID="AGV1")
    
    product = psx.Product([p1], tp, "Product_A")
    
    sink = psx.Sink(product, [20, 0], "Sink")
    arrival_model = psx.FunctionTimeModel("constant", 10.0, ID="arrival_model")
    source = psx.Source(product, arrival_model, [0, 0], ID="Source")
    
    system = psx.ProductionSystem([resource, transport], [source], [sink])
    adapter = system.to_model()
    
    # Create schedule with mixed activities
    schedule = [
        Event(
            time=0.0,
            resource="R1",
            state="P1",
            state_type="Production",
            activity="start state",
            product="Product_A_1",
            expected_end_time=5.0,
            process="P1"
        ),
        Event(
            time=5.0,
            resource="R1",
            state="P1",
            state_type="Production",
            activity="end state",  # This should be filtered out
            product="Product_A_1",
            process="P1"
        ),
        Event(
            time=10.0,
            resource="R1",
            state="P1",
            state_type="Production",
            activity="start state",
            product="Product_A_2",
            expected_end_time=15.0,
            process="P1"
        ),
    ]
    
    adapter.schedule = schedule
    validated_adapter = ProductionSystemData.model_validate(adapter)
    
    # Only "start state" events should remain
    assert len(validated_adapter.schedule) == 2
    for event in validated_adapter.schedule:
        assert event.activity == "start state"


def test_conwip_configuration():
    """Test CONWIP configuration."""
    t1 = psx.FunctionTimeModel("constant", 5.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")
    
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    resource = psx.Resource([p1], [10, 0], 1, ID="R1")
    transport = psx.Resource([tp], [5, 0], 1, ID="AGV1")
    
    product = psx.Product([p1], tp, "Product_A")
    
    sink = psx.Sink(product, [20, 0], "Sink")
    arrival_model = psx.FunctionTimeModel("constant", 1.0, ID="arrival_model")
    source = psx.Source(product, arrival_model, [0, 0], ID="Source")
    
    system = psx.ProductionSystem([resource, transport], [source], [sink])
    adapter = system.to_model()
    
    # Set CONWIP number
    adapter.conwip_number = 3
    
    assert adapter.conwip_number == 3


def test_schedule_simulation(system_with_valid_schedule: ProductionSystemData):
    """Test that simulation runs with a schedule."""
    runner_instance = runner.Runner(production_system_data=system_with_valid_schedule)
    runner_instance.initialize_simulation()
    runner_instance.run(100)
    
    assert runner_instance.env.now == 100
    
    # Get performance data
    performance = runner_instance.get_performance_data()
    assert performance.event_log is not None
    assert len(performance.event_log) > 0


def test_conwip_simulation():
    """Test that simulation runs with CONWIP control."""
    t1 = psx.FunctionTimeModel("constant", 5.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")
    
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    resource = psx.Resource([p1], [10, 0], 1, ID="R1")
    transport = psx.Resource([tp], [5, 0], 1, ID="AGV1")
    
    product = psx.Product([p1], tp, "Product_A")
    
    sink = psx.Sink(product, [20, 0], "Sink")
    arrival_model = psx.FunctionTimeModel("constant", 1.0, ID="arrival_model")
    source = psx.Source(product, arrival_model, [0, 0], ID="Source")
    
    system = psx.ProductionSystem([resource, transport], [source], [sink])
    adapter = system.to_model()
    adapter.conwip_number = 3
    
    runner_instance = runner.Runner(production_system_data=adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(100)
    
    assert runner_instance.env.now == 100
    
    # Get performance data
    performance = runner_instance.get_performance_data()
    assert performance.event_log is not None
    assert len(performance.event_log) > 0


def test_schedule_from_json_file():
    """Test loading a configuration with schedule from JSON file."""
    config_data = json.load(open("examples/modelling_and_simulation/simulation_example_data/schedule_example.json"))
    config = ProductionSystemData.model_validate(config_data)
    
    assert config.schedule is not None
    assert len(config.schedule) == 4
    
    # Verify schedule structure
    for event in config.schedule:
        assert event.activity == "start state"
        assert event.resource in ["R1", "R2"]
        assert event.process in ["P1", "P2"]


def test_conwip_from_json_file():
    """Test loading a configuration with CONWIP from JSON file."""
    config_data = json.load(open("examples/modelling_and_simulation/simulation_example_data/conwip_example.json"))
    config = ProductionSystemData.model_validate(
        config_data
    )
    
    assert config.conwip_number == 5
    assert config.schedule is None


def test_schedule_and_conwip_mutual_exclusion():
    """Test that schedule and CONWIP can coexist (they're independent features)."""
    t1 = psx.FunctionTimeModel("constant", 5.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")
    
    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")
    
    resource = psx.Resource([p1], [10, 0], 1, ID="R1")
    transport = psx.Resource([tp], [5, 0], 1, ID="AGV1")
    
    product = psx.Product([p1], tp, "Product_A")
    
    sink = psx.Sink(product, [20, 0], "Sink")
    arrival_model = psx.FunctionTimeModel("constant", 10.0, ID="arrival_model")
    source = psx.Source(product, arrival_model, [0, 0], ID="Source")
    
    system = psx.ProductionSystem([resource, transport], [source], [sink])
    adapter = system.to_model()
    
    # Set both schedule and CONWIP (they're independent features)
    schedule = [
        Event(
            time=0.0,
            resource="R1",
            state="P1",
            state_type="Production",
            activity="start state",
            product="Product_A_1",
            expected_end_time=5.0,
            process="P1"
        ),
    ]
    adapter.schedule = schedule
    adapter.conwip_number = 3
    
    # Both should be set
    assert adapter.schedule is not None
    assert adapter.conwip_number == 3
    
    # Simulation should run
    runner_instance = runner.Runner(production_system_data=adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(50)
    assert runner_instance.env.now == 50

