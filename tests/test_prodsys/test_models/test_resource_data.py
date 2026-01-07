"""
Tests for resource_data module.
"""

import pytest
from prodsys.models.resource_data import (
    ResourceData,
    SystemResourceData,
    ResourceType,
    ControllerEnum,
    ResourceControlPolicy,
    TransportControlPolicy,
)
from prodsys.models.processes_data import ProductionProcessData, ProcessTypeEnum
from prodsys.models.time_model_data import FunctionTimeModelData
from prodsys.models.port_data import QueueData
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
def sample_process(sample_time_model):
    """Create a sample process for testing."""
    return ProductionProcessData(
        ID="P1",
        description="Process 1",
        time_model_id="tm1",
        type=ProcessTypeEnum.ProductionProcesses,
    )


@pytest.fixture
def sample_queue():
    """Create a sample queue for testing."""
    return QueueData(
        ID="Q1",
        description="Queue 1",
        capacity=10,
    )


@pytest.fixture
def sample_production_system(sample_time_model, sample_process, sample_queue):
    """Create a minimal production system for testing."""
    return ProductionSystemData(
        time_model_data=[sample_time_model],
        process_data=[sample_process],
        resource_data=[],
        product_data=[],
        source_data=[],
        sink_data=[],
        state_data=[],
        port_data=[sample_queue],
        primitive_data=[],
        dependency_data=[],
        node_data=[],
        scenario_data=None,
    )


class TestResourceData:
    """Tests for ResourceData."""

    def test_creation_with_required_fields(self):
        """Test creating ResourceData with required fields."""
        resource = ResourceData(
            ID="R1",
            description="Resource 1",
            capacity=1,
            location=[10.0, 10.0],
            controller=ControllerEnum.PipelineController,
            control_policy=ResourceControlPolicy.FIFO,
            process_ids=["P1"],
        )
        assert resource.ID == "R1"
        assert resource.description == "Resource 1"
        assert resource.capacity == 1
        assert resource.location == [10.0, 10.0]
        assert resource.controller == ControllerEnum.PipelineController
        assert resource.control_policy == ResourceControlPolicy.FIFO
        assert resource.process_ids == ["P1"]

    def test_default_values(self):
        """Test default values for ResourceData."""
        resource = ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            control_policy=ResourceControlPolicy.FIFO,
            process_ids=["P1"],
        )
        assert resource.capacity == 1
        assert resource.process_capacities == [1]  # Should match process_ids length
        assert resource.state_ids == []
        assert resource.controller == ControllerEnum.PipelineController
        assert resource.ports is None
        assert resource.buffers is None
        assert resource.can_move is None
        assert resource.dependency_ids == []
        assert resource.resource_type == ResourceType.RESOURCE

    def test_process_capacities_auto_generated(self):
        """Test that process_capacities are auto-generated from capacity."""
        resource = ResourceData(
            ID="R1",
            description="Resource 1",
            capacity=2,
            location=[10.0, 10.0],
            control_policy=ResourceControlPolicy.FIFO,
            process_ids=["P1", "P2"],
        )
        assert resource.process_capacities == [2, 2]

    def test_process_capacities_explicit(self):
        """Test providing explicit process_capacities."""
        resource = ResourceData(
            ID="R1",
            description="Resource 1",
            capacity=2,
            location=[10.0, 10.0],
            control_policy=ResourceControlPolicy.FIFO,
            process_ids=["P1", "P2"],
            process_capacities=[2, 1],
        )
        assert resource.process_capacities == [2, 1]

    def test_with_state_ids(self):
        """Test creating ResourceData with state IDs."""
        resource = ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            control_policy=ResourceControlPolicy.FIFO,
            process_ids=["P1"],
            state_ids=["State1", "State2"],
        )
        assert resource.state_ids == ["State1", "State2"]

    def test_with_ports(self):
        """Test creating ResourceData with ports."""
        resource = ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            control_policy=ResourceControlPolicy.FIFO,
            process_ids=["P1"],
            ports=["Q1", "Q2"],
        )
        assert resource.ports == ["Q1", "Q2"]

    def test_with_dependency_ids(self):
        """Test creating ResourceData with dependency IDs."""
        resource = ResourceData(
            ID="R1",
            description="Resource 1",
            location=[10.0, 10.0],
            control_policy=ResourceControlPolicy.FIFO,
            process_ids=["P1"],
            dependency_ids=["dep1", "dep2"],
        )
        assert resource.dependency_ids == ["dep1", "dep2"]

    def test_hash(self, sample_production_system, sample_process, sample_queue):
        """Test hash method."""
        resource1 = ResourceData(
            ID="R1",
            description="Resource 1",
            capacity=1,
            location=[10.0, 10.0],
            controller=ControllerEnum.PipelineController,
            control_policy=ResourceControlPolicy.FIFO,
            process_ids=["P1"],
            ports=["Q1"],
        )
        resource2 = ResourceData(
            ID="R2",
            description="Resource 2",
            capacity=1,
            location=[10.0, 10.0],
            controller=ControllerEnum.PipelineController,
            control_policy=ResourceControlPolicy.FIFO,
            process_ids=["P1"],
            ports=["Q1"],
        )
        
        hash1 = resource1.hash(sample_production_system)
        hash2 = resource2.hash(sample_production_system)
        
        # Same parameters should produce same hash
        assert hash1 == hash2

    def test_different_control_policies(self):
        """Test creating ResourceData with different control policies."""
        for policy in [ResourceControlPolicy.FIFO, ResourceControlPolicy.LIFO, ResourceControlPolicy.SPT]:
            resource = ResourceData(
                ID="R1",
                description="Resource 1",
                location=[10.0, 10.0],
                control_policy=policy,
                process_ids=["P1"],
            )
            assert resource.control_policy == policy

    def test_transport_control_policy(self):
        """Test creating ResourceData with transport control policy."""
        resource = ResourceData(
            ID="TR1",
            description="Transport Resource 1",
            location=[10.0, 10.0],
            control_policy=TransportControlPolicy.FIFO,
            process_ids=["TP1"],
        )
        assert resource.control_policy == TransportControlPolicy.FIFO

    def test_validation_process_capacities_length(self):
        """Test validation that process_capacities longer than process_ids still raises error."""
        with pytest.raises(Exception):  # Should raise ValidationError
            ResourceData(
                ID="R1",
                description="Resource 1",
                capacity=2,
                location=[10.0, 10.0],
                control_policy=ResourceControlPolicy.FIFO,
                process_ids=["P1", "P2"],
                process_capacities=[2, 1, 1],  # Longer than process_ids
            )

    def test_validation_process_capacities_max(self):
        """Test validation that process_capacities cannot exceed capacity."""
        with pytest.raises(Exception):  # Should raise ValidationError
            ResourceData(
                ID="R1",
                description="Resource 1",
                capacity=2,
                location=[10.0, 10.0],
                control_policy=ResourceControlPolicy.FIFO,
                process_ids=["P1"],
                process_capacities=[3],  # Exceeds capacity
            )

    def test_process_capacities_partial_specification(self):
        """Test that partially specified process_capacities are filled with capacity."""
        resource = ResourceData(
            ID="R1",
            description="Resource 1",
            capacity=3,
            location=[10.0, 10.0],
            control_policy=ResourceControlPolicy.FIFO,
            process_ids=["P1", "P2", "P3"],
            process_capacities=[2],  # Only one value, should fill rest with capacity
        )
        assert resource.process_capacities == [2, 3, 3]

    def test_process_capacities_with_none_values(self):
        """Test that None values in process_capacities are replaced with capacity."""
        resource = ResourceData(
            ID="R1",
            description="Resource 1",
            capacity=3,
            location=[10.0, 10.0],
            control_policy=ResourceControlPolicy.FIFO,
            process_ids=["P1", "P2", "P3"],
            process_capacities=[2, None, 1],  # None should be replaced with capacity
        )
        assert resource.process_capacities == [2, 3, 1]

    def test_process_capacities_partial_with_none(self):
        """Test partial specification with None values."""
        resource = ResourceData(
            ID="R1",
            description="Resource 1",
            capacity=4,
            location=[10.0, 10.0],
            control_policy=ResourceControlPolicy.FIFO,
            process_ids=["P1", "P2", "P3", "P4"],
            process_capacities=[2, None],  # Partial with None, should fill rest
        )
        assert resource.process_capacities == [2, 4, 4, 4]

    def test_process_capacities_all_none(self):
        """Test that all None values are replaced with capacity."""
        resource = ResourceData(
            ID="R1",
            description="Resource 1",
            capacity=5,
            location=[10.0, 10.0],
            control_policy=ResourceControlPolicy.FIFO,
            process_ids=["P1", "P2"],
            process_capacities=[None, None],  # All None should be replaced
        )
        assert resource.process_capacities == [5, 5]

    def test_process_capacities_empty_list(self):
        """Test that empty list is filled with capacity."""
        resource = ResourceData(
            ID="R1",
            description="Resource 1",
            capacity=3,
            location=[10.0, 10.0],
            control_policy=ResourceControlPolicy.FIFO,
            process_ids=["P1", "P2", "P3"],
            process_capacities=[],  # Empty list should be filled
        )
        assert resource.process_capacities == [3, 3, 3]


class TestSystemResourceData:
    """Tests for SystemResourceData."""

    def test_creation_with_subresources(self):
        """Test creating SystemResourceData with subresources."""
        system_resource = SystemResourceData(
            ID="SR1",
            description="System Resource 1",
            capacity=1,
            location=[20.0, 20.0],
            controller=ControllerEnum.PipelineController,
            control_policy=ResourceControlPolicy.FIFO,
            process_ids=["P1"],
            subresource_ids=["R1", "R2", "R3"],
        )
        assert system_resource.ID == "SR1"
        assert system_resource.subresource_ids == ["R1", "R2", "R3"]
        assert system_resource.resource_type == ResourceType.SYSTEM

    def test_inheritance_from_resource_data(self):
        """Test that SystemResourceData inherits from ResourceData."""
        system_resource = SystemResourceData(
            ID="SR1",
            description="System Resource 1",
            capacity=1,
            location=[20.0, 20.0],
            controller=ControllerEnum.PipelineController,
            control_policy=ResourceControlPolicy.FIFO,
            process_ids=["P1"],
            subresource_ids=["R1"],
        )
        assert isinstance(system_resource, ResourceData)
        assert hasattr(system_resource, "process_ids")
        assert hasattr(system_resource, "capacity")

    def test_with_system_ports(self):
        """Test creating SystemResourceData with system ports."""
        system_resource = SystemResourceData(
            ID="SR1",
            description="System Resource 1",
            capacity=1,
            location=[20.0, 20.0],
            controller=ControllerEnum.PipelineController,
            control_policy=ResourceControlPolicy.FIFO,
            process_ids=["P1"],
            subresource_ids=["R1"],
            system_ports=["SQ1", "SQ2"],
        )
        assert system_resource.system_ports == ["SQ1", "SQ2"]

    def test_with_internal_routing_matrix(self):
        """Test creating SystemResourceData with internal routing matrix."""
        routing_matrix = {
            "R1": ["R2"],
            "R2": ["R3"],
            "R3": [],
        }
        system_resource = SystemResourceData(
            ID="SR1",
            description="System Resource 1",
            capacity=1,
            location=[20.0, 20.0],
            controller=ControllerEnum.PipelineController,
            control_policy=ResourceControlPolicy.FIFO,
            process_ids=["P1"],
            subresource_ids=["R1", "R2", "R3"],
            internal_routing_matrix=routing_matrix,
        )
        assert system_resource.internal_routing_matrix == routing_matrix

