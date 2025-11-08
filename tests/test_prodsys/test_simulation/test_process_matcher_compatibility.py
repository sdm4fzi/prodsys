"""
Unit tests for ProcessMatcher compatibility table methods.

This module contains comprehensive tests for the modularized compatibility table
precomputation methods in ProcessMatcher.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Tuple

import prodsys.express as psx
from prodsys.models.production_system_data import ProductionSystemData
from prodsys.simulation.process_matcher import ProcessMatcher, ResourceCompatibilityKey, TransportCompatibilityKey
from prodsys.simulation import process, request, resources
from prodsys.simulation.entities import product
from prodsys.models.source_data import RoutingHeuristic


class TestProcessMatcherCompatibility:
    """Test class for ProcessMatcher compatibility table methods."""

    @pytest.fixture
    def most_trivial_system(self) -> ProductionSystemData:
        """Create a most trivial production system for testing."""
        t1 = psx.FunctionTimeModel("constant", 0.8, 0, "t1")
        p1 = psx.ProductionProcess(t1, "p1")
        t3 = psx.FunctionTimeModel("normal", 0.1, 0.01, ID="t3")
        tp = psx.TransportProcess(t3, "tp")
        
        machine = psx.Resource([p1], [5, 0], 1, ID="machine")
        transport = psx.Resource([tp], [0, 0], 1, ID="transport")
        
        product1 = psx.Product([p1], tp, "product1")
        sink1 = psx.Sink(product1, [10, 0], "sink1")
        arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")
        source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")
        
        system = psx.ProductionSystem([machine, transport], [source1], [sink1])
        return system.to_model()

    @pytest.fixture
    def primitive_complex_system(self) -> ProductionSystemData:
        """Create a primitive complex production system for testing."""
        t1 = psx.FunctionTimeModel("exponential", 0.8, 0, "t1")
        t2 = psx.FunctionTimeModel("exponential", 1.2, 0, "t2")
        p1 = psx.ProductionProcess(t1, "p1")
        p2 = psx.ProductionProcess(t2, "p2")
        
        t3 = psx.DistanceTimeModel(60, 0.05, "manhattan", ID="t3")
        tp = psx.TransportProcess(t3, "tp")
        tp_prim = psx.TransportProcess(t3, "tp_primitive")
        
        machine = psx.Resource([p1], [5, 0], 1, ID="machine")
        machine2 = psx.Resource([p2], [5, 5], 2, ID="machine2")
        transport = psx.Resource([tp], [3, 0], 1, ID="transport")
        transport2 = psx.Resource([tp], [3, 0], 1, ID="transport2")
        transport_prim = psx.Resource([tp_prim], [4, 0], 1, ID="transport_primitive")
        
        storage1 = psx.Store(ID="storage1", location=[6, 0], capacity=30)
        storage2 = psx.Store(ID="storage2", location=[11, 0], capacity=20)
        
        primitive1 = psx.Primitive(
            ID="primitive1",
            transport_process=tp_prim,
            storages=[storage1],
            quantity_in_storages=[10],
        )
        
        primitive2 = psx.Primitive(
            ID="primitive2",
            transport_process=tp_prim,
            storages=[storage2],
            quantity_in_storages=[20],
        )
        
        primitive_dependency_1 = psx.PrimitiveDependency(
            ID="primitive_dependency_1",
            required_primitive=primitive1,
        )
        primitive_dependency_2 = psx.PrimitiveDependency(
            ID="primitive_dependency_2",
            required_primitive=primitive2,
        )
        
        product1 = psx.Product(
            processes=[p1, p2],
            transport_process=tp,
            ID="product1",
            dependencies=[primitive_dependency_1],
        )
        product2 = psx.Product(
            processes=[p2, p1],
            transport_process=tp,
            ID="product2",
            dependencies=[primitive_dependency_2],
        )
        
        sink1 = psx.Sink(product1, [10, 0], "sink1")
        sink2 = psx.Sink(product2, [10, 0], "sink2")
        
        arrival_model_1 = psx.FunctionTimeModel("constant", 0.9, ID="arrival_model_1")
        arrival_model_2 = psx.FunctionTimeModel("constant", 1.1, ID="arrival_model_2")
        
        source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")
        source2 = psx.Source(product2, arrival_model_2, [0, 0], ID="source_2")
        
        system = psx.ProductionSystem(
            [machine, machine2, transport, transport2, transport_prim], 
            [source1, source2], 
            [sink1, sink2], 
            [primitive1, primitive2]
        )
        return system.to_model()

    @pytest.fixture
    def link_transport_with_capabilities_system(self) -> ProductionSystemData:
        """Create a link transport system with capabilities for testing."""
        time_model_agv = psx.DistanceTimeModel(
            speed=90, reaction_time=0.2, ID="time_model_x"
        )
        time_model_machine1 = psx.FunctionTimeModel(
            distribution_function="constant", location=3, ID="time_model_ap23"
        )
        
        node1 = psx.Node(location=[0, 20], ID="node1")
        node2 = psx.Node(location=[50, 20], ID="node2")
        node3 = psx.Node(location=[100, 20], ID="node3")
        
        rcp01 = psx.RequiredCapabilityProcess(
            time_model=time_model_agv, capability="euro_palette_transport", ID="rtp01"
        )
        productionprocess01 = psx.ProductionProcess(
            time_model=time_model_machine1, ID="pp01"
        )
        
        machine01 = psx.Resource(
            ID="resource01",
            processes=[productionprocess01],
            location=[0, 0],
        )
        
        product01 = psx.Product(
            processes=[productionprocess01],
            transport_process=rcp01,
            ID="product01",
        )
        
        source01 = psx.Source(
            product=product01,
            ID="source01",
            time_model=psx.FunctionTimeModel("constant", 6, ID="tm_source01"),
            location=[-10, 0],
        )
        sink01 = psx.Sink(product=product01, ID="sink01", location=[-10, 100])
        
        ltp01_links = [
            [source01, machine01],
            [machine01, node1],
            [node1, node2],
            [node2, node3],
        ]
        
        ltp01 = psx.LinkTransportProcess(
            time_model=time_model_agv,
            capability="euro_palette_transport",
            ID="ltp01",
            links=ltp01_links,
        )
        
        agv01 = psx.Resource(
            location=[50, 20],
            ID="agv01",
            processes=[ltp01],
        )
        
        productionsystem = psx.ProductionSystem(
            resources=[agv01, machine01],
            sources=[source01],
            sinks=[sink01],
            ID="productionsystem01",
        )
        return productionsystem.to_model()

    @pytest.fixture
    def link_transport_without_capabilities_system(self) -> ProductionSystemData:
        """Create a link transport system without capabilities for testing."""
        time_model_agv = psx.DistanceTimeModel(
            speed=360, reaction_time=0, ID="time_model_x"
        )
        time_model_machine1 = psx.FunctionTimeModel(
            distribution_function="constant", location=3, ID="time_model_ap23"
        )
        
        node1 = psx.Node(location=[10, 0], ID="node1")
        node2 = psx.Node(location=[0, 15], ID="node2")
        
        ltp01 = psx.LinkTransportProcess(time_model=time_model_agv, ID="ltp01")
        productionprocess01 = psx.ProductionProcess(
            time_model=time_model_machine1, ID="pp01"
        )
        
        machine01 = psx.Resource(
            ID="resource01",
            processes=[productionprocess01],
            location=[10, 10],
        )
        
        agv01 = psx.Resource(
            location=[0, 0],
            ID="agv01",
            processes=[ltp01],
        )
        
        product01 = psx.Product(
            processes=[productionprocess01],
            transport_process=ltp01,
            ID="product01",
        )
        
        source01 = psx.Source(
            product=product01,
            ID="source01",
            time_model=psx.FunctionTimeModel("constant", 6, ID="tm_source01"),
            location=[0, 0],
        )
        sink01 = psx.Sink(product=product01, ID="sink01", location=[20, 25])
        
        # Update processes
        links = [
            [source01, node1],
            [node1, machine01],
            [machine01, node2],
            [node2, sink01],
        ]
        ltp01.set_links(links)
        
        productionsystem = psx.ProductionSystem(
            resources=[agv01, machine01],
            sources=[source01],
            sinks=[sink01],
            ID="productionsystem01",
        )
        return productionsystem.to_model()

    @pytest.fixture
    def process_matcher_most_trivial(self, most_trivial_system):
        """Create a ProcessMatcher instance for most trivial system."""
        from prodsys import runner
        runner_instance = runner.Runner(production_system_data=most_trivial_system)
        runner_instance.initialize_simulation()
        return runner_instance.product_factory.router.request_handler.process_matcher

    @pytest.fixture
    def process_matcher_primitive_complex(self, primitive_complex_system):
        """Create a ProcessMatcher instance for primitive complex system."""
        from prodsys import runner
        runner_instance = runner.Runner(production_system_data=primitive_complex_system)
        runner_instance.initialize_simulation()
        return runner_instance.product_factory.router.request_handler.process_matcher

    @pytest.fixture
    def process_matcher_link_transport_with_capabilities(self, link_transport_with_capabilities_system):
        """Create a ProcessMatcher instance for link transport with capabilities system."""
        from prodsys import runner
        runner_instance = runner.Runner(production_system_data=link_transport_with_capabilities_system)
        runner_instance.initialize_simulation()
        return runner_instance.product_factory.router.request_handler.process_matcher

    @pytest.fixture
    def process_matcher_link_transport_without_capabilities(self, link_transport_without_capabilities_system):
        """Create a ProcessMatcher instance for link transport without capabilities system."""
        from prodsys import runner
        runner_instance = runner.Runner(production_system_data=link_transport_without_capabilities_system)
        runner_instance.initialize_simulation()
        return runner_instance.product_factory.router.request_handler.process_matcher

    def test_create_dummy_products(self, process_matcher_most_trivial):
        """Test _create_dummy_products method."""
        dummy_products = process_matcher_most_trivial._create_dummy_products()
        
        assert isinstance(dummy_products, dict)
        assert len(dummy_products) == 1  # One product type in most trivial system
        assert "product1" in dummy_products
        assert isinstance(dummy_products["product1"], product.Product)

    def test_precompute_production_compatibility_most_trivial(self, process_matcher_most_trivial):
        """Test production compatibility precomputation for most trivial system."""
        # Clear existing compatibility tables
        process_matcher_most_trivial.production_compatibility = {}
        
        dummy_products = process_matcher_most_trivial._create_dummy_products()
        process_matcher_most_trivial._precompute_production_compatibility(dummy_products)
        
        # Check that production compatibility table is populated
        assert len(process_matcher_most_trivial.production_compatibility) > 0
        
        # Check for specific process signatures
        production_keys = list(process_matcher_most_trivial.production_compatibility.keys())
        assert any("ProductionProcess:p1" in str(key) for key in production_keys)

    def test_precompute_production_compatibility_primitive_complex(self, process_matcher_primitive_complex):
        """Test production compatibility precomputation for primitive complex system."""
        # Clear existing compatibility tables
        process_matcher_primitive_complex.production_compatibility = {}
        
        dummy_products = process_matcher_primitive_complex._create_dummy_products()
        process_matcher_primitive_complex._precompute_production_compatibility(dummy_products)
        
        # Check that production compatibility table is populated
        assert len(process_matcher_primitive_complex.production_compatibility) > 0
        
        # Check for specific process signatures
        production_keys = list(process_matcher_primitive_complex.production_compatibility.keys())
        assert any("ProductionProcess:p1" in str(key) for key in production_keys)
        assert any("ProductionProcess:p2" in str(key) for key in production_keys)

    def test_precompute_transport_compatibility_most_trivial(self, process_matcher_most_trivial):
        """Test transport compatibility precomputation for most trivial system."""
        # Clear existing compatibility tables
        process_matcher_most_trivial.transport_compatibility = {}
        process_matcher_most_trivial.reachability_cache = {}
        process_matcher_most_trivial.route_cache = {}
        
        dummy_products = process_matcher_most_trivial._create_dummy_products()
        process_matcher_most_trivial._precompute_transport_compatibility(dummy_products)
        
        # Check that transport compatibility table is populated
        assert len(process_matcher_most_trivial.transport_compatibility) > 0
        assert len(process_matcher_most_trivial.reachability_cache) > 0

    def test_precompute_transport_compatibility_link_transport_with_capabilities(self, process_matcher_link_transport_with_capabilities):
        """Test transport compatibility precomputation for link transport with capabilities system."""
        # Clear existing compatibility tables
        process_matcher_link_transport_with_capabilities.transport_compatibility = {}
        process_matcher_link_transport_with_capabilities.reachability_cache = {}
        process_matcher_link_transport_with_capabilities.route_cache = {}
        
        dummy_products = process_matcher_link_transport_with_capabilities._create_dummy_products()
        process_matcher_link_transport_with_capabilities._precompute_transport_compatibility(dummy_products)
        
        # Check that transport compatibility table is populated
        assert len(process_matcher_link_transport_with_capabilities.transport_compatibility) > 0
        assert len(process_matcher_link_transport_with_capabilities.reachability_cache) > 0
        
        # Verify route cache has entries
        assert len(process_matcher_link_transport_with_capabilities.route_cache) > 0, \
            "Route cache should contain route entries"
        
        # Verify that nodes are included in reachability cache
        all_locations = process_matcher_link_transport_with_capabilities._get_all_locations()
        location_ids = [loc.data.ID for loc in all_locations]
        
        # Check that nodes are included in locations
        assert 'node1' in location_ids, "node1 should be included in all_locations"
        assert 'node2' in location_ids, "node2 should be included in all_locations"
        assert 'node3' in location_ids, "node3 should be included in all_locations"
        
        expected_node_connections = [
            ('source01_default_output_queue', 'source01_default_output_queue'), ('source01_default_output_queue', 'resource01_default_input_queue'), ('source01_default_output_queue', 'node3'), ('source01_default_output_queue', 'node1'), ('source01_default_output_queue', 'node2'), ('resource01_default_input_queue', 'source01_default_output_queue'), ('resource01_default_input_queue', 'resource01_default_input_queue'), ('resource01_default_input_queue', 'node3'), ('resource01_default_input_queue', 'node1'), ('resource01_default_input_queue', 'node2'), ('node3', 'source01_default_output_queue'), ('node3', 'resource01_default_input_queue'), ('node3', 'node3'), ('node3', 'node1'), ('node3', 'node2'), ('node1', 'source01_default_output_queue'), ('node1', 'resource01_default_input_queue'), ('node1', 'node3'), ('node1', 'node1'), ('node1', 'node2'), ('node2', 'source01_default_output_queue'), ('node2', 'resource01_default_input_queue'), ('node2', 'node3'), ('node2', 'node1'), ('node2', 'node2')]
        for origin_id, target_id in expected_node_connections:
            cache_key = (origin_id, target_id)
            assert cache_key in process_matcher_link_transport_with_capabilities.reachability_cache, \
                f"Missing reachability cache entry for {origin_id} -> {target_id}"
            assert process_matcher_link_transport_with_capabilities.reachability_cache[cache_key] is True, \
                f"Reachability cache entry for {origin_id} -> {target_id} should be True"

    def test_precompute_transport_compatibility_link_transport_without_capabilities(self, process_matcher_link_transport_without_capabilities):
        """Test transport compatibility precomputation for link transport without capabilities system."""
        # Clear existing compatibility tables
        process_matcher_link_transport_without_capabilities.transport_compatibility = {}
        process_matcher_link_transport_without_capabilities.reachability_cache = {}
        process_matcher_link_transport_without_capabilities.route_cache = {}
        
        dummy_products = process_matcher_link_transport_without_capabilities._create_dummy_products()
        process_matcher_link_transport_without_capabilities._precompute_transport_compatibility(dummy_products)
        
        # Check that transport compatibility table is populated
        assert len(process_matcher_link_transport_without_capabilities.transport_compatibility) > 0
        assert len(process_matcher_link_transport_without_capabilities.reachability_cache) > 0

    def test_precompute_rework_compatibility(self, process_matcher_most_trivial):
        """Test rework compatibility precomputation."""
        # Clear existing compatibility tables
        process_matcher_most_trivial.rework_compatibility = {}
        
        process_matcher_most_trivial._precompute_rework_compatibility()
        
        # Check that rework compatibility table is populated (may be empty if no rework processes)
        assert isinstance(process_matcher_most_trivial.rework_compatibility, dict)

    def test_get_all_locations(self, process_matcher_most_trivial):
        """Test _get_all_locations method."""
        locations = process_matcher_most_trivial._get_all_locations()
        
        assert isinstance(locations, list)
        assert len(locations) > 0
        
        # Check that we have resources, sources, and sinks
        location_ids = [loc.data.ID for loc in locations]
        assert "machine" in location_ids
        assert "source_1" in location_ids
        assert "sink1" in location_ids

    def test_get_all_queues(self, process_matcher_most_trivial):
        """Test _get_all_queues method."""
        queues = process_matcher_most_trivial._get_all_queues()
        
        assert isinstance(queues, list)
        # In most trivial system, there should be queues for resources

    def test_add_to_transport_compatibility(self, process_matcher_most_trivial):
        """Test _add_to_transport_compatibility method."""
        # Clear existing compatibility tables
        process_matcher_most_trivial.transport_compatibility = {}
        
        # Create a mock transport resource and process
        mock_resource = Mock(spec=resources.Resource)
        mock_process = Mock(spec=process.TransportProcess)
        
        key = TransportCompatibilityKey(
            origin_id="source_1",
            target_id="sink1",
            process_signature="TransportProcess:tp"
        )
        
        process_matcher_most_trivial._add_to_transport_compatibility(key, mock_resource, mock_process)
        
        # Check that the entry was added
        assert key in process_matcher_most_trivial.transport_compatibility
        assert (mock_resource, mock_process) in process_matcher_most_trivial.transport_compatibility[key]

    def test_add_to_transport_compatibility_duplicate_prevention(self, process_matcher_most_trivial):
        """Test that _add_to_transport_compatibility prevents duplicates."""
        # Clear existing compatibility tables
        process_matcher_most_trivial.transport_compatibility = {}
        
        # Create a mock transport resource and process
        mock_resource = Mock(spec=resources.Resource)
        mock_process = Mock(spec=process.TransportProcess)
        
        key = TransportCompatibilityKey(
            origin_id="source_1",
            target_id="sink1",
            process_signature="TransportProcess:tp"
        )
        
        # Add the same entry twice
        process_matcher_most_trivial._add_to_transport_compatibility(key, mock_resource, mock_process)
        process_matcher_most_trivial._add_to_transport_compatibility(key, mock_resource, mock_process)
        
        # Check that only one entry exists
        assert len(process_matcher_most_trivial.transport_compatibility[key]) == 1

    def test_handle_required_capability_process(self, process_matcher_link_transport_with_capabilities):
        """Test _handle_required_capability_process method."""
        # Create mock objects
        mock_request = Mock(spec=request.Request)
        mock_requested_process = Mock(spec=process.RequiredCapabilityProcess)
        mock_requested_process.data = Mock()
        mock_requested_process.data.capability = "euro_palette_transport"
        mock_requested_process.get_process_signature.return_value = "RequiredCapabilityProcess:rtp01"
        
        mock_resource = Mock(spec=resources.Resource)
        mock_offered_process = Mock(spec=process.RequiredCapabilityProcess)
        mock_offered_process.data = Mock()
        mock_offered_process.data.capability = "euro_palette_transport"
        
        mock_origin = Mock()
        mock_origin.data = Mock()
        mock_origin.data.ID = "source01"
        mock_target = Mock()
        mock_target.data = Mock()
        mock_target.data.ID = "sink01"
        
        # Clear existing compatibility tables
        process_matcher_link_transport_with_capabilities.transport_compatibility = {}
        process_matcher_link_transport_with_capabilities.reachability_cache = {}
        
        process_matcher_link_transport_with_capabilities._handle_required_capability_process(
            mock_request, mock_requested_process, mock_resource, mock_offered_process, mock_origin, mock_target
        )
        
        # Check that compatibility was added
        assert len(process_matcher_link_transport_with_capabilities.transport_compatibility) > 0
        assert ("source01", "sink01") in process_matcher_link_transport_with_capabilities.reachability_cache

    def test_handle_required_capability_process_capability_mismatch(self, process_matcher_link_transport_with_capabilities):
        """Test _handle_required_capability_process with capability mismatch."""
        # Create mock objects with different capabilities
        mock_request = Mock(spec=request.Request)
        mock_requested_process = Mock(spec=process.RequiredCapabilityProcess)
        mock_requested_process.data = Mock()
        mock_requested_process.data.capability = "euro_palette_transport"
        mock_requested_process.get_process_signature.return_value = "RequiredCapabilityProcess:rtp01"
        
        mock_resource = Mock(spec=resources.Resource)
        mock_offered_process = Mock(spec=process.RequiredCapabilityProcess)
        mock_offered_process.data = Mock()
        mock_offered_process.data.capability = "different_capability"
        
        mock_origin = Mock()
        mock_origin.data = Mock()
        mock_origin.data.ID = "source01"
        mock_target = Mock()
        mock_target.data = Mock()
        mock_target.data.ID = "sink01"
        
        # Clear existing compatibility tables
        process_matcher_link_transport_with_capabilities.transport_compatibility = {}
        process_matcher_link_transport_with_capabilities.reachability_cache = {}
        
        process_matcher_link_transport_with_capabilities._handle_required_capability_process(
            mock_request, mock_requested_process, mock_resource, mock_offered_process, mock_origin, mock_target
        )
        
        # Check that no compatibility was added
        assert len(process_matcher_link_transport_with_capabilities.transport_compatibility) == 0
        assert ("source01", "sink01") not in process_matcher_link_transport_with_capabilities.reachability_cache

    @patch('prodsys.simulation.route_finder.find_route')
    def test_handle_link_transport_process(self, mock_find_route, process_matcher_link_transport_without_capabilities):
        """Test _handle_link_transport_process method."""
        # Mock the route finder to return a valid route
        mock_route = [Mock(), Mock()]
        mock_find_route.return_value = mock_route

        # Create mock objects
        mock_request = Mock(spec=request.Request)
        mock_request.requesting_item = Mock()
        mock_requested_process = Mock(spec=process.LinkTransportProcess)        
        mock_requested_process.get_process_signature.return_value = "LinkTransportProcess:ltp01"
        
        mock_resource = Mock(spec=resources.Resource)
        mock_offered_process = Mock(spec=process.LinkTransportProcess)
        
        mock_origin = Mock()
        mock_origin.data = Mock()
        mock_origin.data.ID = "source01"
        mock_target = Mock()
        mock_target.data = Mock()
        mock_target.data.ID = "sink01"
        
        # Clear existing compatibility tables
        process_matcher_link_transport_without_capabilities.transport_compatibility = {}
        process_matcher_link_transport_without_capabilities.reachability_cache = {}
        process_matcher_link_transport_without_capabilities.route_cache = {}
        
        process_matcher_link_transport_without_capabilities._handle_link_transport_process(
            mock_request, mock_requested_process, mock_resource, mock_offered_process, mock_origin, mock_target
        )
        
        # Check that compatibility was added
        assert len(process_matcher_link_transport_without_capabilities.transport_compatibility) > 0
        assert ("source01", "sink01") in process_matcher_link_transport_without_capabilities.reachability_cache
        assert len(process_matcher_link_transport_without_capabilities.route_cache) > 0

    @patch('prodsys.simulation.route_finder.find_route')
    def test_handle_link_transport_process_no_route(self, mock_find_route, process_matcher_link_transport_without_capabilities):
        """Test _handle_link_transport_process method when no route is found."""
        # Mock the route finder to return None (no route found)
        mock_find_route.return_value = None

        # Create mock objects
        mock_request = Mock(spec=request.Request)
        mock_request.requesting_item = Mock()
        mock_requested_process = Mock(spec=process.LinkTransportProcess)        
        mock_requested_process.get_process_signature.return_value = "LinkTransportProcess:ltp01"
        
        mock_resource = Mock(spec=resources.Resource)
        mock_offered_process = Mock(spec=process.LinkTransportProcess)
        
        mock_origin = Mock()
        mock_origin.data = Mock()
        mock_origin.data.ID = "source01"
        mock_target = Mock()
        mock_target.data = Mock()
        mock_target.data.ID = "sink01"
        
        # Clear existing compatibility tables
        process_matcher_link_transport_without_capabilities.transport_compatibility = {}
        process_matcher_link_transport_without_capabilities.reachability_cache = {}
        process_matcher_link_transport_without_capabilities.route_cache = {}
        
        process_matcher_link_transport_without_capabilities._handle_link_transport_process(
            mock_request, mock_requested_process, mock_resource, mock_offered_process, mock_origin, mock_target
        )
        
        # Check that no compatibility was added
        assert len(process_matcher_link_transport_without_capabilities.transport_compatibility) == 0
        assert ("source01", "sink01") not in process_matcher_link_transport_without_capabilities.reachability_cache

    def test_cache_route(self, process_matcher_most_trivial):
        """Test _cache_route method."""
        # Clear existing route cache
        process_matcher_most_trivial.route_cache = {}
        
        # Create mock objects
        mock_request = Mock(spec=request.Request)
        mock_origin = Mock()
        mock_origin.data = Mock()
        mock_origin.data.ID = "source_1"
        mock_target = Mock()
        mock_target.data = Mock()
        mock_target.data.ID = "sink1"
        mock_process = Mock(spec=process.TransportProcess)
        mock_process.get_process_signature.return_value = "TransportProcess:tp"
        
        mock_route = [Mock(), Mock()]
        
        process_matcher_most_trivial._cache_route(
            mock_request, mock_origin, mock_target, mock_process, mock_route
        )
        
        # Check that route was cached
        route_key = ("source_1", "sink1", "TransportProcess:tp")
        assert route_key in process_matcher_most_trivial.route_cache
        assert process_matcher_most_trivial.route_cache[route_key] == mock_request

    def test_precompute_compatibility_tables_integration(self, process_matcher_most_trivial):
        """Test the complete precompute_compatibility_tables method integration."""
        # Clear all compatibility tables
        process_matcher_most_trivial.production_compatibility = {}
        process_matcher_most_trivial.transport_compatibility = {}
        process_matcher_most_trivial.reachability_cache = {}
        process_matcher_most_trivial.rework_compatibility = {}
        process_matcher_most_trivial.route_cache = {}
        
        # Run the complete precomputation
        process_matcher_most_trivial.precompute_compatibility_tables()
        
        # Check that all tables are populated
        assert len(process_matcher_most_trivial.production_compatibility) > 0
        assert len(process_matcher_most_trivial.transport_compatibility) > 0
        assert len(process_matcher_most_trivial.reachability_cache) > 0
        assert isinstance(process_matcher_most_trivial.rework_compatibility, dict)

    def test_get_compatible_production_processes(self, process_matcher_most_trivial):
        """Test get_compatible method for production processes."""
        # Get a product from the system
        dummy_products = process_matcher_most_trivial._create_dummy_products()
        product = list(dummy_products.values())[0]
        
        # Get all required processes
        required_processes = process_matcher_most_trivial.get_all_required_processes(product)
        
        # Get compatible resources
        compatible_resources = process_matcher_most_trivial.get_compatible(required_processes)
        
        assert isinstance(compatible_resources, list)
        assert len(compatible_resources) > 0
        
        # Check that all returned items are tuples of (resource, process)
        for resource, process_obj in compatible_resources:
            assert isinstance(resource, resources.Resource)
            assert isinstance(process_obj, (process.ProductionProcess, process.TransportProcess, process.CapabilityProcess, process.ReworkProcess, process.CompoundProcess))

    def test_get_transport_compatible(self, process_matcher_most_trivial):
        """Test get_transport_compatible method."""
        # Get locations from the system
        locations = process_matcher_most_trivial._get_all_locations()
        origin = locations[0]
        target = locations[1]
        
        # Get transport compatible resources
        compatible_resources = process_matcher_most_trivial.get_transport_compatible(
            origin, target, "TransportProcess:tp"
        )
        
        assert isinstance(compatible_resources, list)

    def test_get_rework_compatible_no_rework_processes(self, process_matcher_most_trivial):
        """Test get_rework_compatible method when no rework processes exist."""
        # Create a mock failed process
        mock_failed_process = Mock(spec=process.ProductionProcess)
        mock_failed_process.data = Mock()
        mock_failed_process.data.ID = "p1"
        mock_failed_process.get_process_signature.return_value = "ProductionProcess:p1"
        
        # This should raise a ValueError since no rework processes exist
        with pytest.raises(ValueError, match="No compatible rework processes found"):
            process_matcher_most_trivial.get_rework_compatible(mock_failed_process)

    def test_get_route(self, process_matcher_most_trivial):
        """Test get_route method."""
        # Get locations from the system
        locations = process_matcher_most_trivial._get_all_locations()
        origin = locations[0]
        target = locations[1]
        
        # Create a mock process
        mock_process = Mock(spec=process.TransportProcess)
        mock_process.get_process_signature.return_value = "TransportProcess:tp"
        
        # Clear the route cache to ensure no route is found
        process_matcher_most_trivial.route_cache = {}
        
        # This should raise a ValueError since no route is cached
        with pytest.raises(ValueError, match="No route found"):
            process_matcher_most_trivial.get_route(origin, target, mock_process)

    def test_resource_compatibility_key_creation(self):
        """Test ResourceCompatibilityKey creation and equality."""
        key1 = ResourceCompatibilityKey(process_signature="ProductionProcess:p1")
        key2 = ResourceCompatibilityKey(process_signature="ProductionProcess:p1")
        key3 = ResourceCompatibilityKey(process_signature="ProductionProcess:p2")
        
        assert key1 == key2
        assert key1 != key3
        assert hash(key1) == hash(key2)
        assert hash(key1) != hash(key3)

    def test_transport_compatibility_key_creation(self):
        """Test TransportCompatibilityKey creation and equality."""
        key1 = TransportCompatibilityKey(
            origin_id="source1", target_id="sink1", process_signature="TransportProcess:tp"
        )
        key2 = TransportCompatibilityKey(
            origin_id="source1", target_id="sink1", process_signature="TransportProcess:tp"
        )
        key3 = TransportCompatibilityKey(
            origin_id="source1", target_id="sink2", process_signature="TransportProcess:tp"
        )
        
        assert key1 == key2
        assert key1 != key3
        assert hash(key1) == hash(key2)
        assert hash(key1) != hash(key3)

    def test_empty_system_compatibility(self):
        """Test compatibility precomputation with an empty system."""
        # Create an empty production system
        empty_system = psx.ProductionSystem([], [], [])
        adapter = empty_system.to_model()
        
        from prodsys import runner
        runner_instance = runner.Runner(production_system_data=adapter)
        runner_instance.initialize_simulation()
        process_matcher = runner_instance.product_factory.router.request_handler.process_matcher
        
        # Clear all compatibility tables
        process_matcher.production_compatibility = {}
        process_matcher.transport_compatibility = {}
        process_matcher.reachability_cache = {}
        process_matcher.rework_compatibility = {}
        process_matcher.route_cache = {}
        
        # Run precomputation
        process_matcher.precompute_compatibility_tables()
        
        # Check that tables are empty but initialized
        assert len(process_matcher.production_compatibility) == 0
        assert len(process_matcher.transport_compatibility) == 0
        assert len(process_matcher.reachability_cache) == 0
        assert len(process_matcher.rework_compatibility) == 0
        assert len(process_matcher.route_cache) == 0
