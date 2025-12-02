"""
Tests for primitives_data module.
"""

import pytest
from prodsys.models.primitives_data import PrimitiveData, StoredPrimitive
from prodsys.models.production_system_data import ProductionSystemData


class TestPrimitiveData:
    """Tests for PrimitiveData."""

    def test_creation_with_required_fields(self):
        """Test creating PrimitiveData with required fields."""
        primitive = PrimitiveData(
            ID="primitive1",
            description="Primitive 1",
            type="workpiece_carrier",
            transport_process="TP1",
        )
        assert primitive.ID == "primitive1"
        assert primitive.description == "Primitive 1"
        assert primitive.type == "workpiece_carrier"
        assert primitive.transport_process == "TP1"

    def test_inheritance_from_core_asset(self):
        """Test that PrimitiveData inherits from CoreAsset."""
        primitive = PrimitiveData(
            ID="primitive1",
            description="Primitive 1",
            type="workpiece_carrier",
            transport_process="TP1",
        )
        assert hasattr(primitive, "ID")
        assert hasattr(primitive, "description")


class TestStoredPrimitive:
    """Tests for StoredPrimitive."""

    @pytest.fixture
    def mock_adapter(self):
        """Create a mock adapter for testing hash method."""
        # Note: For hash tests, we'll need a real adapter with proper data
        # This is a placeholder that shows the structure needed
        return None

    def test_creation_with_storages(self):
        """Test creating StoredPrimitive with storages."""
        stored_primitive = StoredPrimitive(
            ID="stored_primitive1",
            description="Stored Primitive 1",
            type="workpiece_carrier",
            transport_process="TP1",
            storages=["Storage1", "Storage2"],
            quantity_in_storages=[2, 3],
        )
        assert stored_primitive.ID == "stored_primitive1"
        assert stored_primitive.description == "Stored Primitive 1"
        assert stored_primitive.type == "workpiece_carrier"
        assert stored_primitive.transport_process == "TP1"
        assert stored_primitive.storages == ["Storage1", "Storage2"]
        assert stored_primitive.quantity_in_storages == [2, 3]

    def test_default_quantity_in_storages(self):
        """Test that quantity_in_storages defaults to empty list."""
        stored_primitive = StoredPrimitive(
            ID="stored_primitive1",
            description="Stored Primitive 1",
            type="workpiece_carrier",
            transport_process="TP1",
            storages=["Storage1"],
        )
        assert stored_primitive.quantity_in_storages == []

    def test_inheritance_from_primitive_data(self):
        """Test that StoredPrimitive inherits from PrimitiveData."""
        stored_primitive = StoredPrimitive(
            ID="stored_primitive1",
            description="Stored Primitive 1",
            type="workpiece_carrier",
            transport_process="TP1",
            storages=["Storage1"],
        )
        assert isinstance(stored_primitive, PrimitiveData)
        assert hasattr(stored_primitive, "type")
        assert hasattr(stored_primitive, "transport_process")
        assert hasattr(stored_primitive, "storages")

    def test_empty_storages_list(self):
        """Test creating StoredPrimitive with empty storages list."""
        stored_primitive = StoredPrimitive(
            ID="stored_primitive1",
            description="Stored Primitive 1",
            type="workpiece_carrier",
            transport_process="TP1",
            storages=[],
        )
        assert stored_primitive.storages == []

