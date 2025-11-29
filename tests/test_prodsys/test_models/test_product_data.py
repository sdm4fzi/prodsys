"""
Tests for product_data module.
"""

import pytest
from prodsys.models.product_data import ProductData
from prodsys.models.processes_data import ProductionProcessData, ProcessTypeEnum
from prodsys.models.time_model_data import FunctionTimeModelData
from prodsys.models.source_data import RoutingHeuristic
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
def sample_process(sample_time_model):
    """Create a sample process for testing."""
    return ProductionProcessData(
        ID="P1",
        description="Process 1",
        time_model_id="tm1",
        type=ProcessTypeEnum.ProductionProcesses,
    )


@pytest.fixture
def sample_transport_process(sample_transport_time_model):
    """Create a sample transport process for testing."""
    from prodsys.models.processes_data import TransportProcessData
    
    return TransportProcessData(
        ID="TP1",
        description="Transport Process 1",
        time_model_id="tm_transport",
        type=ProcessTypeEnum.TransportProcesses,
    )


@pytest.fixture
def sample_production_system(sample_time_model, sample_transport_time_model, sample_process, sample_transport_process):
    """Create a minimal production system for testing."""
    return ProductionSystemData(
        time_model_data=[sample_time_model, sample_transport_time_model],
        process_data=[sample_process, sample_transport_process],
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


class TestProductData:
    """Tests for ProductData."""

    def test_creation_with_sequential_processes(self):
        """Test creating ProductData with sequential processes (list)."""
        product = ProductData(
            ID="Product_1",
            description="Product 1",
            type="Product_1",
            processes=["P1", "P2", "P3"],
            transport_process="TP1",
        )
        assert product.ID == "Product_1"
        assert product.description == "Product 1"
        assert product.type == "Product_1"
        # Sequential list should be converted to adjacency matrix
        assert "P1" in product.processes
        assert product.processes["P1"] == ["P2"]
        assert product.processes["P2"] == ["P3"]
        assert product.processes["P3"] == []
        assert product.transport_process == "TP1"

    def test_creation_with_adjacency_matrix(self):
        """Test creating ProductData with adjacency matrix."""
        adjacency_matrix = {
            "P1": ["P2", "P3"],
            "P2": ["P3"],
            "P3": [],
        }
        product = ProductData(
            ID="Product_1",
            description="Product 1",
            type="Product_1",
            processes=adjacency_matrix,
            transport_process="TP1",
        )
        assert product.processes == adjacency_matrix

    def test_default_dependency_ids(self):
        """Test that dependency_ids defaults to empty list."""
        product = ProductData(
            ID="Product_1",
            description="Product 1",
            type="Product_1",
            processes={"P1": []},
            transport_process="TP1",
        )
        assert product.dependency_ids == []

    def test_with_dependency_ids(self):
        """Test creating ProductData with dependency IDs."""
        product = ProductData(
            ID="Product_1",
            description="Product 1",
            type="Product_1",
            processes={"P1": []},
            transport_process="TP1",
            dependency_ids=["dep1", "dep2"],
        )
        assert product.dependency_ids == ["dep1", "dep2"]

    def test_default_routing_heuristic(self):
        """Test that routing_heuristic defaults to None."""
        product = ProductData(
            ID="Product_1",
            description="Product 1",
            type="Product_1",
            processes={"P1": []},
            transport_process="TP1",
        )
        assert product.routing_heuristic is None

    def test_with_routing_heuristic(self):
        """Test creating ProductData with routing heuristic."""
        product = ProductData(
            ID="Product_1",
            description="Product 1",
            type="Product_1",
            processes={"P1": []},
            transport_process="TP1",
            routing_heuristic=RoutingHeuristic.shortest_queue,
        )
        assert product.routing_heuristic == RoutingHeuristic.shortest_queue

    def test_default_becomes_consumable(self):
        """Test that becomes_consumable defaults to False."""
        product = ProductData(
            ID="Product_1",
            description="Product 1",
            type="Product_1",
            processes={"P1": []},
            transport_process="TP1",
        )
        assert product.becomes_consumable is False

    def test_with_becomes_consumable(self):
        """Test creating ProductData with becomes_consumable=True."""
        product = ProductData(
            ID="Product_1",
            description="Product 1",
            type="Product_1",
            processes={"P1": []},
            transport_process="TP1",
            becomes_consumable=True,
        )
        assert product.becomes_consumable is True

    def test_type_synced_with_id(self):
        """Test that type is synced with ID if not provided."""
        product = ProductData(
            ID="Product_1",
            description="Product 1",
            processes={"P1": []},
            transport_process="TP1",
        )
        assert product.type == "Product_1"

    def test_id_synced_with_type(self):
        """Test that ID is synced with type if type provided."""
        product = ProductData(
            description="Product 1",
            type="Product_1",
            processes={"P1": []},
            transport_process="TP1",
        )
        assert product.ID == "Product_1"

    def test_hash(self, sample_production_system, sample_process, sample_transport_process):
        """Test hash method."""
        product1 = ProductData(
            ID="Product_1",
            description="Product 1",
            type="Product_1",
            processes={"P1": []},
            transport_process="TP1",
        )
        product2 = ProductData(
            ID="Product_2",
            description="Product 2",
            type="Product_2",
            processes={"P1": []},
            transport_process="TP1",
        )
        
        hash1 = product1.hash(sample_production_system)
        hash2 = product2.hash(sample_production_system)
        
        # Same processes and transport should produce same hash
        assert hash1 == hash2

    def test_inheritance_from_primitive_data(self):
        """Test that ProductData inherits from PrimitiveData."""
        product = ProductData(
            ID="Product_1",
            description="Product 1",
            type="Product_1",
            processes={"P1": []},
            transport_process="TP1",
        )
        from prodsys.models.primitives_data import PrimitiveData
        assert isinstance(product, PrimitiveData)
        assert hasattr(product, "type")
        assert hasattr(product, "transport_process")

    def test_sequential_to_adjacency_conversion(self):
        """Test that sequential list is correctly converted to adjacency matrix."""
        product = ProductData(
            ID="Product_1",
            description="Product 1",
            type="Product_1",
            processes=["P1", "P2", "P3"],
            transport_process="TP1",
        )
        assert product.processes["P1"] == ["P2"]
        assert product.processes["P2"] == ["P3"]
        assert product.processes["P3"] == []
        assert len(product.processes) == 3

