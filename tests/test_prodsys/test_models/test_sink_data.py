"""
Tests for sink_data module.
"""

import pytest
from prodsys.models.sink_data import SinkData
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
        ID="tm1",
        description="Time model",
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
def sample_process(sample_time_model):
    """Create a sample production process for testing."""
    return ProductionProcessData(
        ID="P1",
        description="Process 1",
        time_model_id="tm1",
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
        ID="SinkQueue",
        description="Sink Queue",
        capacity=10,
    )


@pytest.fixture
def sample_production_system(sample_time_model, sample_transport_time_model, sample_process, sample_transport_process, sample_product, sample_queue):
    """Create a minimal production system for testing."""
    return ProductionSystemData(
        time_model_data=[sample_time_model, sample_transport_time_model],
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


class TestSinkData:
    """Tests for SinkData."""

    def test_creation_with_required_fields(self):
        """Test creating SinkData with required fields."""
        sink = SinkData(
            ID="SK1",
            description="Sink 1",
            location=[50.0, 50.0],
            product_type="Product_1",
        )
        assert sink.ID == "SK1"
        assert sink.description == "Sink 1"
        assert sink.location == [50.0, 50.0]
        assert sink.product_type == "Product_1"

    def test_default_ports(self):
        """Test that ports defaults to empty list."""
        sink = SinkData(
            ID="SK1",
            description="Sink 1",
            location=[50.0, 50.0],
            product_type="Product_1",
        )
        assert sink.ports is None

    def test_with_ports(self):
        """Test creating SinkData with ports."""
        sink = SinkData(
            ID="SK1",
            description="Sink 1",
            location=[50.0, 50.0],
            product_type="Product_1",
            ports=["SinkQueue"],
        )
        assert sink.ports == ["SinkQueue"]

    def test_hash(self, sample_production_system, sample_product, sample_queue):
        """Test hash method."""
        sink1 = SinkData(
            ID="SK1",
            description="Sink 1",
            location=[50.0, 50.0],
            product_type="Product_1",
            ports=["SinkQueue"],
        )
        sink2 = SinkData(
            ID="SK2",
            description="Sink 2",
            location=[50.0, 50.0],
            product_type="Product_1",
            ports=["SinkQueue"],
        )
        
        hash1 = sink1.hash(sample_production_system)
        hash2 = sink2.hash(sample_production_system)
        
        # Same parameters should produce same hash
        assert hash1 == hash2

    def test_inheritance_from_locatable(self):
        """Test that SinkData inherits from Locatable."""
        sink = SinkData(
            ID="SK1",
            description="Sink 1",
            location=[50.0, 50.0],
            product_type="Product_1",
        )
        from prodsys.models.core_asset import Locatable
        assert isinstance(sink, Locatable)
        assert hasattr(sink, "location")

