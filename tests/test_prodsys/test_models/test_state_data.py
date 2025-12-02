"""
Tests for state_data module.
"""

import pytest
from prodsys.models.state_data import (
    StateData,
    BreakDownStateData,
    ProcessBreakDownStateData,
    ProductionStateData,
    TransportStateData,
    SetupStateData,
    ChargingStateData,
    StateTypeEnum,
)
from prodsys.models.processes_data import ProductionProcessData, ProcessTypeEnum
from prodsys.models.time_model_data import FunctionTimeModelData
from prodsys.models.production_system_data import ProductionSystemData
from prodsys.util.statistical_functions import FunctionTimeModelEnum


@pytest.fixture
def sample_time_model():
    """Create a sample time model for testing."""
    return FunctionTimeModelData(
        ID="tm1",
        description="Test time model",
        distribution_function=FunctionTimeModelEnum.Exponential,
        location=540.0,
        scale=0.0,
    )


@pytest.fixture
def sample_repair_time_model():
    """Create a sample repair time model for testing."""
    return FunctionTimeModelData(
        ID="tm_repair",
        description="Repair time model",
        distribution_function=FunctionTimeModelEnum.Exponential,
        location=60.0,
        scale=0.0,
    )


@pytest.fixture
def sample_process_time_model():
    """Create a sample process time model for testing."""
    return FunctionTimeModelData(
        ID="tm_process",
        description="Process time model",
        distribution_function=FunctionTimeModelEnum.Normal,
        location=20.0,
        scale=5.0,
    )


@pytest.fixture
def sample_process(sample_process_time_model):
    """Create a sample process for testing."""
    return ProductionProcessData(
        ID="P1",
        description="Process 1",
        time_model_id="tm_process",
        type=ProcessTypeEnum.ProductionProcesses,
    )


@pytest.fixture
def sample_production_system(sample_time_model, sample_repair_time_model, sample_process_time_model, sample_process):
    """Create a minimal production system for testing."""
    return ProductionSystemData(
        time_model_data=[sample_time_model, sample_repair_time_model, sample_process_time_model],
        process_data=[sample_process],
        resource_data=[],
        product_data=[],
        source_data=[],
        sink_data=[],
        state_data=[],
        port_data=[],
        primitive_data=[],
        dependency_data=[],
        node_data=[],
        scenario_data=None,
    )


class TestBreakDownStateData:
    """Tests for BreakDownStateData."""

    def test_creation_with_required_fields(self):
        """Test creating BreakDownStateData with required fields."""
        state = BreakDownStateData(
            ID="Breakdownstate_1",
            description="Breakdown state 1",
            time_model_id="tm1",
            type=StateTypeEnum.BreakDownState,
            repair_time_model_id="tm_repair",
        )
        assert state.ID == "Breakdownstate_1"
        assert state.description == "Breakdown state 1"
        assert state.time_model_id == "tm1"
        assert state.type == StateTypeEnum.BreakDownState
        assert state.repair_time_model_id == "tm_repair"

    def test_hash(self, sample_production_system, sample_time_model, sample_repair_time_model):
        """Test hash method."""
        state1 = BreakDownStateData(
            ID="Breakdownstate_1",
            description="Breakdown state 1",
            time_model_id="tm1",
            type=StateTypeEnum.BreakDownState,
            repair_time_model_id="tm_repair",
        )
        state2 = BreakDownStateData(
            ID="Breakdownstate_2",
            description="Breakdown state 2",
            time_model_id="tm1",
            type=StateTypeEnum.BreakDownState,
            repair_time_model_id="tm_repair",
        )
        
        hash1 = state1.hash(sample_production_system)
        hash2 = state2.hash(sample_production_system)
        
        # Same parameters should produce same hash
        assert hash1 == hash2


class TestProcessBreakDownStateData:
    """Tests for ProcessBreakDownStateData."""

    def test_creation_with_required_fields(self):
        """Test creating ProcessBreakDownStateData with required fields."""
        state = ProcessBreakDownStateData(
            ID="ProcessBreakDownState_1",
            description="Process Breakdown state 1",
            time_model_id="tm1",
            type=StateTypeEnum.ProcessBreakDownState,
            repair_time_model_id="tm_repair",
            process_id="P1",
        )
        assert state.ID == "ProcessBreakDownState_1"
        assert state.time_model_id == "tm1"
        assert state.type == StateTypeEnum.ProcessBreakDownState
        assert state.repair_time_model_id == "tm_repair"
        assert state.process_id == "P1"

    def test_hash(self, sample_production_system, sample_time_model, sample_repair_time_model, sample_process):
        """Test hash method."""
        state1 = ProcessBreakDownStateData(
            ID="ProcessBreakDownState_1",
            description="Process Breakdown state 1",
            time_model_id="tm1",
            type=StateTypeEnum.ProcessBreakDownState,
            repair_time_model_id="tm_repair",
            process_id="P1",
        )
        state2 = ProcessBreakDownStateData(
            ID="ProcessBreakDownState_2",
            description="Process Breakdown state 2",
            time_model_id="tm1",
            type=StateTypeEnum.ProcessBreakDownState,
            repair_time_model_id="tm_repair",
            process_id="P1",
        )
        
        hash1 = state1.hash(sample_production_system)
        hash2 = state2.hash(sample_production_system)
        
        # Same parameters should produce same hash
        assert hash1 == hash2


class TestProductionStateData:
    """Tests for ProductionStateData."""

    def test_creation_with_required_fields(self):
        """Test creating ProductionStateData with required fields."""
        state = ProductionStateData(
            ID="ProductionState_1",
            description="Production state 1",
            time_model_id="tm1",
            type=StateTypeEnum.ProductionState,
        )
        assert state.ID == "ProductionState_1"
        assert state.description == "Production state 1"
        assert state.time_model_id == "tm1"
        assert state.type == StateTypeEnum.ProductionState


class TestTransportStateData:
    """Tests for TransportStateData."""

    def test_creation_with_required_fields(self):
        """Test creating TransportStateData with required fields."""
        state = TransportStateData(
            ID="TransportState_1",
            description="Transport state 1",
            time_model_id="tm1",
            type=StateTypeEnum.TransportState,
        )
        assert state.ID == "TransportState_1"
        assert state.time_model_id == "tm1"
        assert state.type == StateTypeEnum.TransportState

    def test_default_loading_unloading_time_models(self):
        """Test that loading/unloading time models default to None."""
        state = TransportStateData(
            ID="TransportState_1",
            description="Transport state 1",
            time_model_id="tm1",
            type=StateTypeEnum.TransportState,
        )
        assert state.loading_time_model_id is None
        assert state.unloading_time_model_id is None

    def test_with_loading_and_unloading_time_models(self):
        """Test creating TransportStateData with loading/unloading time models."""
        state = TransportStateData(
            ID="TransportState_1",
            description="Transport state 1",
            time_model_id="tm1",
            type=StateTypeEnum.TransportState,
            loading_time_model_id="tm_load",
            unloading_time_model_id="tm_unload",
        )
        assert state.loading_time_model_id == "tm_load"
        assert state.unloading_time_model_id == "tm_unload"


class TestSetupStateData:
    """Tests for SetupStateData."""

    def test_creation_with_required_fields(self):
        """Test creating SetupStateData with required fields."""
        state = SetupStateData(
            ID="Setup_State_2",
            description="Setup state 2",
            time_model_id="tm1",
            type=StateTypeEnum.SetupState,
            origin_setup="P2",
            target_setup="P1",
        )
        assert state.ID == "Setup_State_2"
        assert state.time_model_id == "tm1"
        assert state.type == StateTypeEnum.SetupState
        assert state.origin_setup == "P2"
        assert state.target_setup == "P1"

    def test_hash(self, sample_production_system, sample_time_model, sample_process):
        """Test hash method."""
        state1 = SetupStateData(
            ID="Setup_State_1",
            description="Setup state 1",
            time_model_id="tm1",
            type=StateTypeEnum.SetupState,
            origin_setup="P2",
            target_setup="P1",
        )
        state2 = SetupStateData(
            ID="Setup_State_2",
            description="Setup state 2",
            time_model_id="tm1",
            type=StateTypeEnum.SetupState,
            origin_setup="P2",
            target_setup="P1",
        )
        
        hash1 = state1.hash(sample_production_system)
        hash2 = state2.hash(sample_production_system)
        
        # Same parameters should produce same hash
        assert hash1 == hash2


class TestChargingStateData:
    """Tests for ChargingStateData."""

    def test_creation_with_required_fields(self):
        """Test creating ChargingStateData with required fields."""
        state = ChargingStateData(
            ID="ChargingState_1",
            description="Charging state 1",
            time_model_id="tm1",
            type=StateTypeEnum.ChargingState,
            battery_time_model_id="tm_battery",
        )
        assert state.ID == "ChargingState_1"
        assert state.description == "Charging state 1"
        assert state.time_model_id == "tm1"
        assert state.type == StateTypeEnum.ChargingState
        assert state.battery_time_model_id == "tm_battery"

    def test_hash(self, sample_production_system, sample_time_model):
        """Test hash method."""
        # Add battery time model to production system
        battery_time_model = FunctionTimeModelData(
            ID="tm_battery",
            description="Battery time model",
            distribution_function=FunctionTimeModelEnum.Exponential,
            location=240.0,
            scale=0.0,
        )
        sample_production_system.time_model_data.append(battery_time_model)
        
        state1 = ChargingStateData(
            ID="ChargingState_1",
            description="Charging state 1",
            time_model_id="tm1",
            type=StateTypeEnum.ChargingState,
            battery_time_model_id="tm_battery",
        )
        state2 = ChargingStateData(
            ID="ChargingState_2",
            description="Charging state 2",
            time_model_id="tm1",
            type=StateTypeEnum.ChargingState,
            battery_time_model_id="tm_battery",
        )
        
        hash1 = state1.hash(sample_production_system)
        hash2 = state2.hash(sample_production_system)
        
        # Same parameters should produce same hash
        assert hash1 == hash2

