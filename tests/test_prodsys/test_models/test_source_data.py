"""
Tests for source_data module.
"""

import pytest
from prodsys.models.source_data import SourceData, RoutingHeuristic
from prodsys.models.product_data import ProductData
from prodsys.models.processes_data import TransportProcessData, ProductionProcessData, ProcessTypeEnum
from prodsys.models.time_model_data import FunctionTimeModelData
from prodsys.models.port_data import QueueData
from prodsys.models.production_system_data import ProductionSystemData
from prodsys.util.statistical_functions import FunctionTimeModelEnum


@pytest.fixture
def sample_time_model():
    """Create a sample time model for testing."""
    return FunctionTimeModelData(
        ID="tm_arrival",
        description="Arrival time model",
        distribution_function=FunctionTimeModelEnum.Exponential,
        location=5.2,
        scale=0.0,
    )


@pytest.fixture
def sample_production_time_model():
    """Create a sample production time model for testing."""
    return FunctionTimeModelData(
        ID="tm_production",
        description="Production time model",
        distribution_function=FunctionTimeModelEnum.Normal,
        location=10.0,
        scale=2.0,
    )


@pytest.fixture
def sample_transport_time_model():
    """Create a sample transport time model for testing."""
    return FunctionTimeModelData(
        ID="tm_transport",
        description="Transport time model",
        distribution_function=FunctionTimeModelEnum.Normal,
        location=1.0,
        scale=0.1,
    )


@pytest.fixture
def sample_process(sample_production_time_model):
    """Create a sample production process for testing."""
    return ProductionProcessData(
        ID="P1",
        description="Process 1",
        time_model_id="tm_production",
        type=ProcessTypeEnum.ProductionProcesses,
    )


@pytest.fixture
def sample_transport_process(sample_transport_time_model):
    """Create a sample transport process for testing."""
    return TransportProcessData(
        ID="TP1",
        description="Transport Process 1",
        time_model_id="tm_transport",
        type=ProcessTypeEnum.TransportProcesses,
    )


@pytest.fixture
def sample_product(sample_transport_process):
    """Create a sample product for testing."""
    return ProductData(
        ID="Product_1",
        description="Product 1",
        product_type="Product_1",
        processes={"P1": []},
        transport_process="TP1",
    )


@pytest.fixture
def sample_queue():
    """Create a sample queue for testing."""
    return QueueData(
        ID="SourceQueue",
        description="Source Queue",
        capacity=10,
    )


@pytest.fixture
def sample_production_system(sample_time_model, sample_production_time_model, sample_transport_time_model, sample_process, sample_transport_process, sample_product, sample_queue):
    """Create a minimal production system for testing."""
    return ProductionSystemData(
        time_model_data=[sample_time_model, sample_production_time_model, sample_transport_time_model],
        process_data=[sample_process, sample_transport_process],
        resource_data=[],
        product_data=[sample_product],
        source_data=[],
        sink_data=[],
        state_data=[],
        port_data=[sample_queue],
        primitive_data=[],
        dependency_data=[],
        node_data=[],
        scenario_data=None,
    )


class TestSourceData:
    """Tests for SourceData."""

    def test_creation_with_required_fields(self):
        """Test creating SourceData with required fields."""
        source = SourceData(
            ID="S1",
            description="Source 1",
            location=[0.0, 0.0],
            product_type="Product_1",
            time_model_id="tm_arrival",
            routing_heuristic=RoutingHeuristic.shortest_queue,
        )
        assert source.ID == "S1"
        assert source.description == "Source 1"
        assert source.location == [0.0, 0.0]
        assert source.product_type == "Product_1"
        assert source.time_model_id == "tm_arrival"
        assert source.routing_heuristic == RoutingHeuristic.shortest_queue

    def test_default_ports(self):
        """Test that ports defaults to empty list."""
        source = SourceData(
            ID="S1",
            description="Source 1",
            location=[0.0, 0.0],
            product_type="Product_1",
            time_model_id="tm_arrival",
            routing_heuristic=RoutingHeuristic.shortest_queue,
        )
        assert source.ports is None

    def test_with_ports(self):
        """Test creating SourceData with ports."""
        source = SourceData(
            ID="S1",
            description="Source 1",
            location=[0.0, 0.0],
            product_type="Product_1",
            time_model_id="tm_arrival",
            routing_heuristic=RoutingHeuristic.shortest_queue,
            ports=["SourceQueue"],
        )
        assert source.ports == ["SourceQueue"]

    def test_different_routing_heuristics(self):
        """Test creating SourceData with different routing heuristics."""
        for heuristic in [RoutingHeuristic.random, RoutingHeuristic.shortest_queue, RoutingHeuristic.FIFO]:
            source = SourceData(
                ID="S1",
                description="Source 1",
                location=[0.0, 0.0],
                product_type="Product_1",
                time_model_id="tm_arrival",
                routing_heuristic=heuristic,
            )
            assert source.routing_heuristic == heuristic

    def test_hash(self, sample_production_system, sample_product, sample_time_model, sample_queue):
        """Test hash method."""
        source1 = SourceData(
            ID="S1",
            description="Source 1",
            location=[0.0, 0.0],
            product_type="Product_1",
            time_model_id="tm_arrival",
            routing_heuristic=RoutingHeuristic.shortest_queue,
            ports=["SourceQueue"],
        )
        source2 = SourceData(
            ID="S2",
            description="Source 2",
            location=[0.0, 0.0],
            product_type="Product_1",
            time_model_id="tm_arrival",
            routing_heuristic=RoutingHeuristic.shortest_queue,
            ports=["SourceQueue"],
        )
        
        hash1 = source1.hash(sample_production_system)
        hash2 = source2.hash(sample_production_system)
        
        # Same parameters should produce same hash
        assert hash1 == hash2

    def test_inheritance_from_locatable(self):
        """Test that SourceData inherits from Locatable."""
        source = SourceData(
            ID="S1",
            description="Source 1",
            location=[0.0, 0.0],
            product_type="Product_1",
            time_model_id="tm_arrival",
            routing_heuristic=RoutingHeuristic.shortest_queue,
        )
        from prodsys.models.core_asset import Locatable
        assert isinstance(source, Locatable)
        assert hasattr(source, "location")

