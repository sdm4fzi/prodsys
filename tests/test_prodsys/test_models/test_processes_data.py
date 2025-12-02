"""
Tests for processes_data module.
"""

import pytest
from prodsys.models.processes_data import (
    ProcessData,
    ProductionProcessData,
    CapabilityProcessData,
    TransportProcessData,
    ReworkProcessData,
    CompoundProcessData,
    RequiredCapabilityProcessData,
    LinkTransportProcessData,
    ProcessModelData,
    LoadingProcessData,
    ProcessTypeEnum,
)
from prodsys.models.time_model_data import FunctionTimeModelData
from prodsys.models.production_system_data import ProductionSystemData
from prodsys.util.statistical_functions import FunctionTimeModelEnum


@pytest.fixture
def sample_time_model():
    """Create a sample time model for testing."""
    return FunctionTimeModelData(
        ID="tm1",
        description="Test time model",
        distribution_function=FunctionTimeModelEnum.Normal,
        location=20.0,
        scale=5.0,
    )


@pytest.fixture
def sample_production_system(sample_time_model):
    """Create a minimal production system for testing hash methods."""
    from prodsys.models.production_system_data import ProductionSystemData
    
    # Create a minimal adapter with time models
    return ProductionSystemData(
        time_model_data=[sample_time_model],
        process_data=[],
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


class TestProductionProcessData:
    """Tests for ProductionProcessData."""

    def test_creation_with_required_fields(self):
        """Test creating ProductionProcessData with required fields."""
        process = ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type=ProcessTypeEnum.ProductionProcesses,
        )
        assert process.ID == "P1"
        assert process.description == "Process 1"
        assert process.time_model_id == "tm1"
        assert process.type == ProcessTypeEnum.ProductionProcesses

    def test_default_failure_rate(self):
        """Test that failure_rate defaults to 0.0."""
        process = ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type=ProcessTypeEnum.ProductionProcesses,
        )
        assert process.failure_rate == 0.0

    def test_with_failure_rate(self):
        """Test creating ProductionProcessData with failure rate."""
        process = ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type=ProcessTypeEnum.ProductionProcesses,
            failure_rate=0.1,
        )
        assert process.failure_rate == 0.1

    def test_default_dependency_ids(self):
        """Test that dependency_ids defaults to empty list."""
        process = ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type=ProcessTypeEnum.ProductionProcesses,
        )
        assert process.dependency_ids == []

    def test_with_dependency_ids(self):
        """Test creating ProductionProcessData with dependency IDs."""
        process = ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type=ProcessTypeEnum.ProductionProcesses,
            dependency_ids=["dep1", "dep2"],
        )
        assert process.dependency_ids == ["dep1", "dep2"]

    def test_hash(self, sample_production_system, sample_time_model):
        """Test hash method."""
        process1 = ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="tm1",
            type=ProcessTypeEnum.ProductionProcesses,
            failure_rate=0.1,
        )
        process2 = ProductionProcessData(
            ID="P2",
            description="Process 2",
            time_model_id="tm1",
            type=ProcessTypeEnum.ProductionProcesses,
            failure_rate=0.1,
        )
        process3 = ProductionProcessData(
            ID="P3",
            description="Process 3",
            time_model_id="tm1",
            type=ProcessTypeEnum.ProductionProcesses,
            failure_rate=0.2,  # different failure rate
        )
        
        hash1 = process1.hash(sample_production_system)
        hash2 = process2.hash(sample_production_system)
        hash3 = process3.hash(sample_production_system)
        
        # Same parameters should produce same hash
        assert hash1 == hash2
        # Different failure rate should produce different hash
        assert hash1 != hash3


class TestCapabilityProcessData:
    """Tests for CapabilityProcessData."""

    def test_creation_with_capability(self):
        """Test creating CapabilityProcessData with capability."""
        process = CapabilityProcessData(
            ID="CP1",
            description="Capability Process 1",
            time_model_id="tm1",
            type=ProcessTypeEnum.CapabilityProcesses,
            capability="C1",
        )
        assert process.ID == "CP1"
        assert process.capability == "C1"
        assert process.type == ProcessTypeEnum.CapabilityProcesses

    def test_hash(self, sample_production_system, sample_time_model):
        """Test hash method considers capability."""
        process1 = CapabilityProcessData(
            ID="CP1",
            description="Capability Process 1",
            time_model_id="tm1",
            type=ProcessTypeEnum.CapabilityProcesses,
            capability="C1",
        )
        process2 = CapabilityProcessData(
            ID="CP2",
            description="Capability Process 2",
            time_model_id="tm1",
            type=ProcessTypeEnum.CapabilityProcesses,
            capability="C1",
        )
        process3 = CapabilityProcessData(
            ID="CP3",
            description="Capability Process 3",
            time_model_id="tm1",
            type=ProcessTypeEnum.CapabilityProcesses,
            capability="C2",  # different capability
        )
        
        hash1 = process1.hash(sample_production_system)
        hash2 = process2.hash(sample_production_system)
        hash3 = process3.hash(sample_production_system)
        
        # Same parameters should produce same hash
        assert hash1 == hash2
        # Different capability should produce different hash
        assert hash1 != hash3


class TestTransportProcessData:
    """Tests for TransportProcessData."""

    def test_creation_with_required_fields(self):
        """Test creating TransportProcessData with required fields."""
        process = TransportProcessData(
            ID="TP1",
            description="Transport Process 1",
            time_model_id="tm1",
            type=ProcessTypeEnum.TransportProcesses,
        )
        assert process.ID == "TP1"
        assert process.time_model_id == "tm1"
        assert process.type == ProcessTypeEnum.TransportProcesses

    def test_with_loading_and_unloading_time_models(self):
        """Test creating TransportProcessData with loading/unloading time models."""
        process = TransportProcessData(
            ID="TP1",
            description="Transport Process 1",
            time_model_id="tm1",
            type=ProcessTypeEnum.TransportProcesses,
            loading_time_model_id="tm_load",
            unloading_time_model_id="tm_unload",
        )
        assert process.loading_time_model_id == "tm_load"
        assert process.unloading_time_model_id == "tm_unload"


class TestReworkProcessData:
    """Tests for ReworkProcessData."""

    def test_creation_with_reworked_process_ids(self):
        """Test creating ReworkProcessData with reworked process IDs."""
        process = ReworkProcessData(
            ID="RP1",
            description="Rework Process 1",
            time_model_id="tm1",
            type=ProcessTypeEnum.ReworkProcesses,
            reworked_process_ids=["P1", "P2"],
            blocking=True,
        )
        assert process.ID == "RP1"
        assert process.reworked_process_ids == ["P1", "P2"]
        assert process.blocking is True

    def test_non_blocking_rework(self):
        """Test creating non-blocking ReworkProcessData."""
        process = ReworkProcessData(
            ID="RP1",
            description="Rework Process 1",
            time_model_id="tm1",
            type=ProcessTypeEnum.ReworkProcesses,
            reworked_process_ids=["P1"],
            blocking=False,
        )
        assert process.blocking is False


class TestCompoundProcessData:
    """Tests for CompoundProcessData."""

    def test_creation_with_process_ids(self):
        """Test creating CompoundProcessData with process IDs."""
        process = CompoundProcessData(
            ID="CP1",
            description="Compound Process 1",
            process_ids=["P1", "P2"],
            type=ProcessTypeEnum.CompoundProcesses,
        )
        assert process.ID == "CP1"
        assert process.process_ids == ["P1", "P2"]
        assert process.type == ProcessTypeEnum.CompoundProcesses


class TestRequiredCapabilityProcessData:
    """Tests for RequiredCapabilityProcessData."""

    def test_creation_with_capability(self):
        """Test creating RequiredCapabilityProcessData with capability."""
        process = RequiredCapabilityProcessData(
            ID="RCP1",
            description="Required Capability Process 1",
            type=ProcessTypeEnum.RequiredCapabilityProcesses,
            capability="C1",
        )
        assert process.ID == "RCP1"
        assert process.capability == "C1"
        assert process.type == ProcessTypeEnum.RequiredCapabilityProcesses


class TestLinkTransportProcessData:
    """Tests for LinkTransportProcessData."""

    def test_creation_with_links(self):
        """Test creating LinkTransportProcessData with links."""
        process = LinkTransportProcessData(
            ID="LTP1",
            description="Link Transport Process 1",
            time_model_id="tm1",
            type=ProcessTypeEnum.LinkTransportProcesses,
            links=[["Resource1", "Node2"], ["Node2", "Resource1"]],
        )
        assert process.ID == "LTP1"
        assert process.links == [["Resource1", "Node2"], ["Node2", "Resource1"]]

    def test_default_capability(self):
        """Test that capability defaults to empty string."""
        process = LinkTransportProcessData(
            ID="LTP1",
            description="Link Transport Process 1",
            time_model_id="tm1",
            type=ProcessTypeEnum.LinkTransportProcesses,
            links=[["Resource1", "Node2"]],
        )
        assert process.capability == ""

    def test_with_capability(self):
        """Test creating LinkTransportProcessData with capability."""
        process = LinkTransportProcessData(
            ID="LTP1",
            description="Link Transport Process 1",
            time_model_id="tm1",
            type=ProcessTypeEnum.LinkTransportProcesses,
            links=[["Resource1", "Node2"]],
            capability="automated_transport",
        )
        assert process.capability == "automated_transport"


class TestProcessModelData:
    """Tests for ProcessModelData."""

    def test_creation_with_adjacency_matrix(self):
        """Test creating ProcessModelData with adjacency matrix."""
        process_model = ProcessModelData(
            ID="PM1",
            description="Process Model 1",
            type=ProcessTypeEnum.ProcessModels,
            adjacency_matrix={"P1": ["P2"], "P2": ["P3"], "P3": []},
        )
        assert process_model.ID == "PM1"
        assert process_model.adjacency_matrix == {"P1": ["P2"], "P2": ["P3"], "P3": []}

    def test_process_ids_property(self):
        """Test that process_ids property returns keys from adjacency_matrix."""
        process_model = ProcessModelData(
            ID="PM1",
            description="Process Model 1",
            type=ProcessTypeEnum.ProcessModels,
            adjacency_matrix={"P1": ["P2"], "P2": ["P3"], "P3": []},
        )
        assert set(process_model.process_ids) == {"P1", "P2", "P3"}

    def test_default_dependency_ids(self):
        """Test that dependency_ids defaults to empty list."""
        process_model = ProcessModelData(
            ID="PM1",
            description="Process Model 1",
            type=ProcessTypeEnum.ProcessModels,
            adjacency_matrix={"P1": []},
        )
        assert process_model.dependency_ids == []


class TestLoadingProcessData:
    """Tests for LoadingProcessData."""

    def test_creation_with_dependency_type(self):
        """Test creating LoadingProcessData with dependency type."""
        process = LoadingProcessData(
            ID="LP1",
            description="Loading Process 1",
            time_model_id="tm1",
            type=ProcessTypeEnum.LoadingProcesses,
            dependency_type="before",
        )
        assert process.ID == "LP1"
        assert process.dependency_type == "before"

    def test_default_can_be_chained(self):
        """Test that can_be_chained defaults to True."""
        process = LoadingProcessData(
            ID="LP1",
            description="Loading Process 1",
            time_model_id="tm1",
            type=ProcessTypeEnum.LoadingProcesses,
            dependency_type="before",
        )
        assert process.can_be_chained is True

    def test_different_dependency_types(self):
        """Test creating LoadingProcessData with different dependency types."""
        for dep_type in ["before", "after", "parallel"]:
            process = LoadingProcessData(
                ID="LP1",
                description="Loading Process 1",
                time_model_id="tm1",
                type=ProcessTypeEnum.LoadingProcesses,
                dependency_type=dep_type,
            )
            assert process.dependency_type == dep_type

