"""
Tests for port_data module.
"""

import pytest
from prodsys.models.port_data import (
    QueueData,
    StoreData,
    PortInterfaceType,
    PortType,
)


class TestQueueData:
    """Tests for QueueData."""

    def test_creation_with_capacity(self):
        """Test creating QueueData with capacity."""
        queue = QueueData(
            ID="Q1",
            description="Queue 1",
            capacity=10,
        )
        assert queue.ID == "Q1"
        assert queue.description == "Queue 1"
        assert queue.capacity == 10
        assert queue.port_type == PortType.QUEUE
        assert queue.interface_type == PortInterfaceType.INPUT_OUTPUT

    def test_infinite_capacity(self):
        """Test creating QueueData with infinite capacity (0)."""
        queue = QueueData(
            ID="Q1",
            description="Infinite Queue",
            capacity=0,
        )
        assert queue.capacity == 0

    def test_default_values(self):
        """Test default values for QueueData."""
        queue = QueueData(
            ID="Q1",
            description="Queue 1",
        )
        assert queue.capacity == 0.0
        assert queue.location is None
        assert queue.interface_type == PortInterfaceType.INPUT_OUTPUT
        assert queue.port_type == PortType.QUEUE
        assert queue.dependency_ids == []

    def test_with_location(self):
        """Test creating QueueData with location."""
        queue = QueueData(
            ID="Q1",
            description="Queue 1",
            capacity=10,
            location=[5.0, 10.0],
        )
        assert queue.location == [5.0, 10.0]

    def test_with_dependency_ids(self):
        """Test creating QueueData with dependency IDs."""
        queue = QueueData(
            ID="Q1",
            description="Queue 1",
            capacity=10,
            dependency_ids=["dep1", "dep2"],
        )
        assert queue.dependency_ids == ["dep1", "dep2"]

    def test_hash(self):
        """Test hash method considers capacity."""
        queue1 = QueueData(
            ID="Q1",
            description="Queue 1",
            capacity=10,
        )
        queue2 = QueueData(
            ID="Q2",
            description="Queue 2",
            capacity=10,
        )
        queue3 = QueueData(
            ID="Q3",
            description="Queue 3",
            capacity=20,
        )
        
        # Same capacity should produce same hash
        assert queue1.hash() == queue2.hash()
        # Different capacity should produce different hash
        assert queue1.hash() != queue3.hash()

    def test_different_interface_types(self):
        """Test creating QueueData with different interface types."""
        queue_input = QueueData(
            ID="Q1",
            description="Input Queue",
            interface_type=PortInterfaceType.INPUT,
        )
        queue_output = QueueData(
            ID="Q2",
            description="Output Queue",
            interface_type=PortInterfaceType.OUTPUT,
        )
        queue_io = QueueData(
            ID="Q3",
            description="Input/Output Queue",
            interface_type=PortInterfaceType.INPUT_OUTPUT,
        )
        
        assert queue_input.interface_type == PortInterfaceType.INPUT
        assert queue_output.interface_type == PortInterfaceType.OUTPUT
        assert queue_io.interface_type == PortInterfaceType.INPUT_OUTPUT


class TestStoreData:
    """Tests for StoreData."""

    def test_creation_with_location(self):
        """Test creating StoreData with location."""
        store = StoreData(
            ID="ST1",
            description="Store 1",
            capacity=10,
            location=[10.0, 0.0],
        )
        assert store.ID == "ST1"
        assert store.description == "Store 1"
        assert store.capacity == 10
        assert store.location == [10.0, 0.0]
        assert store.port_type == PortType.STORE
        assert store.interface_type == PortInterfaceType.INPUT_OUTPUT

    def test_with_port_locations(self):
        """Test creating StoreData with port locations."""
        store = StoreData(
            ID="ST1",
            description="Store 1",
            capacity=0,
            location=[10.0, 0.0],
            port_locations=[[11.0, 0.0], [12.0, 0.0]],
        )
        assert store.port_locations == [[11.0, 0.0], [12.0, 0.0]]

    def test_inheritance_from_queue(self):
        """Test that StoreData inherits from QueueData."""
        store = StoreData(
            ID="ST1",
            description="Store 1",
            capacity=10,
            location=[10.0, 0.0],
        )
        assert isinstance(store, QueueData)
        assert store.port_type == PortType.STORE

    def test_hash(self):
        """Test hash method considers capacity, location, and port locations."""
        store1 = StoreData(
            ID="ST1",
            description="Store 1",
            capacity=10,
            location=[10.0, 0.0],
            port_locations=[[11.0, 0.0], [12.0, 0.0]],
        )
        store2 = StoreData(
            ID="ST2",
            description="Store 2",
            capacity=10,
            location=[10.0, 0.0],
            port_locations=[[11.0, 0.0], [12.0, 0.0]],
        )
        store3 = StoreData(
            ID="ST3",
            description="Store 3",
            capacity=10,
            location=[10.0, 0.0],
            port_locations=[[11.0, 0.0], [13.0, 0.0]],  # different port location
        )
        
        # Same parameters should produce same hash
        assert store1.hash() == store2.hash()
        # Different port locations should produce different hash
        assert store1.hash() != store3.hash()

    def test_hash_without_port_locations(self):
        """Test hash when port_locations is None."""
        store1 = StoreData(
            ID="ST1",
            description="Store 1",
            capacity=10,
            location=[10.0, 0.0],
        )
        store2 = StoreData(
            ID="ST2",
            description="Store 2",
            capacity=10,
            location=[10.0, 0.0],
        )
        
        # Same parameters should produce same hash
        assert store1.hash() == store2.hash()

    def test_default_port_locations(self):
        """Test that port_locations defaults to None."""
        store = StoreData(
            ID="ST1",
            description="Store 1",
            capacity=10,
            location=[10.0, 0.0],
        )
        assert store.port_locations is None

