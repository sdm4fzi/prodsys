from __future__ import annotations

from dataclasses import dataclass
from prodsys.simulation.port import Queue
from prodsys.simulation.source import Source
from prodsys.simulation.sink import Sink
from prodsys.simulation.resources import Resource
from typing import TYPE_CHECKING, Dict, List, Tuple

import logging
import time

from prodsys.factories import primitive_factory
from prodsys.models.source_data import RoutingHeuristic
from prodsys.models.dependency_data import DependencyType
from prodsys.simulation import request, process, route_finder


if TYPE_CHECKING:
    from prodsys.simulation import resources, process
    from prodsys.factories import (
        resource_factory,
        sink_factory,
        product_factory,
        source_factory,
        dependency_factory,
    )
    from prodsys.simulation.entities import product
    from prodsys.models import product_data
    from prodsys.simulation.locatable import Locatable

    # from prodsys.factories.source_factory import SourceFactory

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class ResourceCompatibilityKey:
    """Key for the resource compatibility lookup table."""
    process_signature: str

    @classmethod
    def from_request(cls, request: request.Request) -> "ResourceCompatibilityKey":
        """Create a key from a request."""
        process_signature = request.process.get_process_signature()
        return cls(process_signature=process_signature)


@dataclass(frozen=True)
class TransportCompatibilityKey:
    """Key for the transport compatibility lookup table."""

    origin_id: str
    target_id: str
    process_signature: str

    @classmethod
    def from_request(
        cls, request: request.Request
    ) -> "TransportCompatibilityKey":
        """Create a key from a transport request."""
        origin_id = request.origin.data.ID
        target_id = request.target.data.ID
        process_signature = request.process.get_process_signature()
        return cls(
            origin_id=origin_id,
            target_id=target_id,
            process_signature=process_signature,
        )


class ProcessMatcher:

    def __init__(
        self,
        resource_factory: resource_factory.ResourceFactory,
        sink_factory: sink_factory.SinkFactory,
        product_factory: product_factory.ProductFactory,
        source_factory: source_factory.SourceFactory,
        primitive_factory: primitive_factory.PrimitiveFactory,
        dependency_factory: dependency_factory.DependencyFactory,
    ):
        """
        Initialize the ProcessMatcher with the necessary factories and routing control environment.

        Args:
            resource_factory (ResourceFactory): Factory for creating resources.
            sink_factory (SinkFactory): Factory for creating sinks.
            primtiive_factory (PrimitiveFactory): Factory for creating primitives.
            product_factory (ProductFactory): Factory for creating products.
            source_factory (SourceFactory): Factory for creating sources.
            routing_control_env (RoutingControlEnv): Environment for routing control.
        """
        self.resource_factory = resource_factory
        self.sink_factory = sink_factory
        self.product_factory = product_factory
        self.source_factory = source_factory
        self.primitive_factory = primitive_factory
        self.dependency_factory = dependency_factory
        self.route_cache: Dict[Tuple[str, str, str], request.Request] = {}
        self.reachability_cache: Dict[Tuple[str, str], bool] = {}

        # Compatibility tables for resources and processes
        self.production_compatibility: dict[
            tuple[str, str], list[tuple[resources.Resource, process.ProductionProcess]]
        ] = {}
        self.transport_compatibility: dict[
            tuple[str, str], list[tuple[resources.Resource, process.TransportProcess]]
        ] = {}
        self.rework_compatibility: dict[
            str, list[process.ReworkProcess]
        ] = {}

        # Precompute compatibility tables at initialization time
        self.precompute_compatibility_tables()

    def _create_dummy_product(
        self, product_data: product_data.ProductData
    ) -> product.Product:
        """
        Create a dummy product for compatibility testing.

        Args:
            product_type: The product type

        Returns:
            A dummy product instance
        """
        return self.product_factory.create_product(
            product_data=product_data, routing_heuristic=RoutingHeuristic.FIFO
        )

    def _create_dummy_products(self) -> dict[str, product.Product]:
        """
        Create dummy products for compatibility testing.
        
        Returns:
            dict[str, product.Product]: Dictionary mapping product types to dummy products.
        """
        dummy_products: dict[str, product.Product] = {}
        for source in self.source_factory.sources.values():
            product_type = source.product_data.type
            dummy_products[product_type] = self._create_dummy_product(
                source.product_data
            )
        return dummy_products

    def _remove_dummy_products(self, dummy_products: dict[str, product.Product]):
        """
        Remove dummy products from the system.
        """
        for product_type, dummy_product in dummy_products.items():
            self.product_factory.products.pop(dummy_product.data.ID)

    def _reset_primitives_in_queues(self):
        """
        Reset primitives in queues to their original locations.
        """
        self.primitive_factory.reset_primitives_current_locatable()

    def _precompute_production_compatibility(self, dummy_products: dict[str, product.Product]):
        """
        Precompute production resource compatibility.
        
        Args:
            dummy_products: Dictionary of dummy products for testing.
        """
        for product_type, dummy_product in dummy_products.items():
            all_processes_of_product = self.get_all_required_processes(dummy_product)
            for requested_process in all_processes_of_product:
                for resource in self.resource_factory.get_production_resources():
                    dummy_production_request = request.Request(
                        process=requested_process,
                        requesting_item=dummy_product,
                        resource=resource,
                        request_type=request.RequestType.PRODUCTION,
                    )
                    for offered_process in resource.processes:
                        # Test if this process matches the request
                        if offered_process.matches_request(dummy_production_request):
                            key = ResourceCompatibilityKey(
                                process_signature=requested_process.get_process_signature(),
                            )
                            if key not in self.production_compatibility:
                                self.production_compatibility[key] = []
                            self.production_compatibility[key].append(
                                (resource, offered_process)
                            )

    def get_all_required_processes(
        self, product: product.Product
    ) -> List[process.PROCESS_UNION]:
        """
        Get all required processes for a product.

        Args:
            product (product.Product): The product for which to get required processes.

        Returns:
            List[process.PROCESS_UNION]: List of required processes.
        """
        return product.process_model.contained_processes

    def precompute_compatibility_tables(self):
        """
        Precompute compatibility tables for resources and processes.
        This method runs at initialization time to create lookup tables
        that will speed up resource selection during simulation.
        """
        start_time = time.time()

        # Get dummy products for testing
        dummy_products = self._create_dummy_products()

        # Precompute different types of compatibility
        self._precompute_production_compatibility(dummy_products)
        self._precompute_transport_compatibility(dummy_products)
        self._precompute_rework_compatibility()

        # Precompute compatibility of resource processes
        for resource_id, resource in self.resource_factory.all_resources.items():
            for offered_process in resource.processes:
                # Create a key for the resource compatibility
                key = ResourceCompatibilityKey(
                    process_signature=offered_process.get_process_signature(),
                )
                if key not in self.production_compatibility:
                    self.production_compatibility[key] = []
                self.production_compatibility[key].append((resource, offered_process))

        self._remove_dummy_products(dummy_products)
        self._reset_primitives_in_queues()

    def _get_parent_from_queue(self, locatable: Locatable) -> Locatable:
        """
        Get the parent object from a queue object.
        
        Args:
            locatable (Locatable): The queue or parent object.
            
        Returns:
            Locatable: The parent object (source/resource/sink) or the original object if it's not a queue.
        """
        # If it's a queue, try to find its parent
        if hasattr(locatable, 'data') and hasattr(locatable.data, 'ID'):
            queue_id = locatable.data.ID
            
            # Check if this is a queue by looking for the pattern "_default_input_queue" or "_default_output_queue"
            if "_default_input_queue" in queue_id or "_default_output_queue" in queue_id:
                # Extract the parent ID by removing the queue suffix
                if "_default_input_queue" in queue_id:
                    parent_id = queue_id.replace("_default_input_queue", "")
                else:
                    parent_id = queue_id.replace("_default_output_queue", "")
                
                # Look up the parent in all locations
                all_locations = self._get_all_locations()
                for loc in all_locations:
                    if hasattr(loc, 'data') and hasattr(loc.data, 'ID') and loc.data.ID == parent_id:
                        return loc
                        
        # If not a queue or parent not found, return the original object
        return locatable

    def get_route(
        self, origin: Locatable, target: Locatable, process: process.PROCESS_UNION
    ) -> List[Locatable]:
        """
        Returns the route for a given origin, target, and process signature.
        Handles mapping between queue objects and their parent objects.

        Args:
            origin (Locatable): The origin location (could be a queue or parent object).
            target (Locatable): The target location (could be a queue or parent object).
            process_signature (str): The process signature.

        Returns:
            List[Locatable]: The route as a list of locations.
        """
        
        process_signature = process.get_process_signature()
        key = (origin.data.ID, target.data.ID, process_signature)
        cached_request = self.route_cache.get(key)
        if cached_request is None:
            raise ValueError(f"No route found for {origin.data.ID} -> {target.data.ID} with process {process_signature}")
        
        # Return the route from the cached request
        return cached_request.get_route()

    def get_compatible(
        self, requested_processes: List[process.PROCESS_UNION]
    ) -> List[Tuple[resources.Resource, process.PROCESS_UNION]]:
        """
        Returns a list of compatible resources and processes for the requested processes.

        Args:
            requested_processes (List[process.PROCESS_UNION]): The processes to find compatible resources for.
            product_type (str): The product type for which to find compatible resources.

        Returns:
            List[Tuple[resources.Resource, process.PROCESS_UNION]]: List of compatible resources and their processes.
        """
        compatible_resources = []

        for requested_process in requested_processes:
            if isinstance(
                requested_process,
                (process.ProductionProcess, process.CapabilityProcess, process.ReworkProcess),
            ):
                key = ResourceCompatibilityKey(
                    process_signature=requested_process.get_process_signature(),
                )
                compatible_resources.extend(self.production_compatibility.get(key, []))

            elif isinstance(requested_process, process.ProcessModelProcess):
                # For ProcessModel processes, find resources that offer this specific process model
                key = ResourceCompatibilityKey(
                    process_signature=requested_process.get_process_signature(),
                )
                compatible_resources.extend(self.production_compatibility.get(key, []))

            elif isinstance(requested_process, process.CompoundProcess):
                # For compound processes, check compatibility for each contained process
                for process_id in requested_process.data.process_ids:
                    # Create a process signature for the contained process
                    process_signature = f"ProductionProcess:{process_id}"
                    key = ResourceCompatibilityKey(
                        process_signature=process_signature
                    )
                    compatible_resources.extend(
                        self.production_compatibility.get(key, [])
                    )

                # Check for capability processes in compound process
                for contained_process in requested_process.contained_processes_data:
                    if (
                        hasattr(contained_process, "capability")
                        and contained_process.capability
                    ):
                        process_signature = (
                            f"CapabilityProcess:{contained_process.capability}"
                        )
                        key = ResourceCompatibilityKey(
                            process_signature=process_signature,
                        )
                        compatible_resources.extend(
                            self.production_compatibility.get(key, [])
                        )

        return compatible_resources

    def get_transport_compatible(
        self, origin: Locatable, target: Locatable, process_signature: str
    ) -> List[Tuple[resources.Resource, process.PROCESS_UNION]]:
        """
        Returns a list of compatible transport resources and processes for moving between origin and target.

        Args:
            origin (Locatable): The origin location.
            target (Locatable): The target location.
            process_signature (str): The transport process signature.

        Returns:
            List[Tuple[resources.Resource, process.PROCESS_UNION]]: List of compatible transport resources and processes.
        """
        key = TransportCompatibilityKey(
            origin_id=origin.data.ID,
            target_id=target.data.ID,
            process_signature=process_signature,
        )
        return self.transport_compatibility.get(key, [])

    def get_rework_compatible(
            self, failed_process: process.PROCESS_UNION
    ) -> List[process.ReworkProcess]: 
        """
        Returns a list of compatible rework processes for a failed process.

        Args:
            failed_process (process.PROCESS_UNION): The process that has failed.

        Returns:
            List[process.ReworkProcess]: List of compatible rework processes.
        """
        process_signature = failed_process.get_process_signature()
        rework_processes = self.rework_compatibility.get(process_signature, [])
        if not rework_processes:
            # Get the process ID for error message
            process_id = getattr(failed_process.data, 'ID', 'unknown') if hasattr(failed_process, 'data') else 'unknown'
            raise ValueError(
                f"No compatible rework processes found for failed process {process_id} with signature {process_signature}"
            )
        return rework_processes

    def _get_all_locations(self) -> List[Locatable]:
        """
        Get all locations in the system (resources, sources, sinks, nodes, queues with locations).
        
        Returns:
            List[Locatable]: List of all locations in the system.
        """
        all_locations = (
            list(self.resource_factory.get_production_resources())
            + list(self.sink_factory.sinks.values())
            + list(self.source_factory.sources.values())
            + [q for q in self.resource_factory.queue_factory.queues 
               if hasattr(q.data, "location") and q.data.location is not None]
        )
        
        # Add nodes from link transport processes
        nodes_from_links = set()
        for resource in self.resource_factory.all_resources.values():
            for process in resource.processes:
                if hasattr(process, 'links') and process.links:
                    for link in process.links:
                        for locatable in link:
                            if hasattr(locatable, 'data') and hasattr(locatable.data, 'ID'):
                                # Check if this is a node by checking the type name
                                if (type(locatable).__name__ == 'Node' and 
                                    locatable not in all_locations):
                                    nodes_from_links.add(locatable)
        
        all_locations.extend(list(nodes_from_links))
        return all_locations


    def get_all_transport_locations(self) -> List[Locatable]:
        """
        Get all transport locations in the system.
        
        Returns:
            List[Locatable]: List of all transport locations in the system.
        """
        transport_interaction_locations = (
            [q for q in self.resource_factory.queue_factory.queues 
               if hasattr(q.data, "location") and q.data.location is not None]
        )
        
        # Also consider nodes that are interaction nodes of dependencies
        interaction_nodes = {}
        # TODO: probably also consider depndencies without interaction points -> goes to the resource having this dependency
        for resource in self.resource_factory.all_resources.values():
            process_dependencies = []
            for process in resource.processes:
                process_dependencies.extend(process.dependencies)

            for dependency in resource.dependencies + process_dependencies:
                if dependency.interaction_node:
                    interaction_nodes[dependency.interaction_node.data.ID] = dependency.interaction_node
                else:
                    interaction_nodes[resource.data.ID] = resource

        transport_interaction_locations.extend(list(interaction_nodes.values()))
        return transport_interaction_locations

    def _get_all_queues(self) -> List:
        """
        Get all queues in the system.
        
        Returns:
            List: List of all queues in the system.
        """
        return list(self.resource_factory.queue_factory.queues)

    def _create_queue_to_parent_mapping(self, all_queues: List, all_locations: list) -> Dict[str, Locatable]:
        """
        Create a mapping from queue IDs to their parent objects.
        
        Args:
            all_queues: List of all queues in the system.
            
        Returns:
            Dict[str, Locatable]: Mapping from queue ID to parent object.
        """
        queue_to_parent = {}
        for queue in all_queues:
            queue_id = queue.data.ID
            for resource in all_locations:
                if queue_id in resource.data.ports:
                    queue_to_parent[queue_id] = resource
                    break
        return queue_to_parent

    def _add_to_transport_compatibility(
        self, 
        key: TransportCompatibilityKey, 
        resource: resources.Resource, 
        process: process.PROCESS_UNION
    ):
        """
        Add a resource-process pair to the transport compatibility table.
        
        Args:
            key: The compatibility key.
            resource: The transport resource.
            process: The transport process.
        """
        if key not in self.transport_compatibility:
            self.transport_compatibility[key] = []
        
        if (resource, process) not in self.transport_compatibility[key]:
            self.transport_compatibility[key].append((resource, process))

    def _handle_required_capability_process(
        self,
        transport_request: request.Request,
        requested_process: process.RequiredCapabilityProcess,
        resource: resources.Resource,
        offered_process: process.RequiredCapabilityProcess,
        origin: Locatable,
        target: Locatable
    ):
        """
        Handle compatibility checking for required capability processes.
        
        Args:
            transport_request: The transport request.
            requested_process: The requested capability process.
            resource: The transport resource.
            offered_process: The offered capability process.
            origin: The origin location.
            target: The target location.
        """
        # Check if capabilities match
        if (hasattr(requested_process.data, 'capability') and 
            hasattr(offered_process.data, 'capability') and
            requested_process.data.capability == offered_process.data.capability):
            
            key = TransportCompatibilityKey(
                origin_id=origin.data.ID,
                target_id=target.data.ID,
                process_signature=requested_process.get_process_signature(),
            )
            self._add_to_transport_compatibility(key, resource, offered_process)
            
            # Cache reachability
            self.reachability_cache[(origin.data.ID, target.data.ID)] = True

    def _handle_link_transport_process(
        self,
        transport_request: request.Request,
        requested_process: process.LinkTransportProcess,
        resource: resources.Resource,
        offered_process: process.LinkTransportProcess,
        origin: Locatable,
        target: Locatable,
    ):
        """
        Handle compatibility checking for link transport processes.
        
        Args:
            transport_request: The transport request.
            requested_process: The requested link transport process.
            resource: The transport resource.
            offered_process: The offered link transport process.
            origin: The origin location.
            target: The target location.
        """
        try:
            from prodsys.simulation.route_finder import find_route
            
            # Create a proper request object for the route finder
            route_request = request.Request(
                process=offered_process,
                requesting_item=transport_request.requesting_item,
                resource=resource,
                origin=origin,
                target=target,
                request_type=request.RequestType.TRANSPORT,
            )
            
            # Use the route finder to check if a valid route exists
            # The route finder will handle the link connectivity checking internally
            if (origin.data.ID, target.data.ID, offered_process.get_process_signature()) in self.route_cache:
                route = self.route_cache[(origin.data.ID, target.data.ID, offered_process.get_process_signature())].get_route()
            else:
                route = find_route(route_request, offered_process)
            
            if route:
                key = TransportCompatibilityKey(
                    origin_id=origin.data.ID,
                    target_id=target.data.ID,
                    process_signature=requested_process.get_process_signature(),
                )
                self._add_to_transport_compatibility(key, resource, offered_process)
                
                # Cache reachability
                self.reachability_cache[(origin.data.ID, target.data.ID)] = True

                # Cache the route
                self._cache_route(route_request, origin, target, offered_process, route)
        except ImportError:
            # If route finder is not available, skip this process
            pass


    def _cache_route(
        self,
        request_instance: request.Request,
        origin: Locatable,
        target: Locatable,
        process: process.PROCESS_UNION,
        route: List
    ):
        """
        Cache a route for future use.
        
        Args:
            request: The transport request.
            origin: The origin location.
            target: The target location.
            process: The transport process.
            route: The route to cache.
        """
        route_key = (
            origin.data.ID,
            target.data.ID,
            process.get_process_signature(),
        )
        if route_key not in self.route_cache:
            self.route_cache[route_key] = request_instance

    def get_required_transport_processes(self, dummy_products: dict[str, product.Product]) -> List[Tuple[product.Product, process.PROCESS_UNION]]:
        transport_process_with_product = {}
        for product in dummy_products.values():
            transport_process_with_product[product.transport_process.data.ID] = (product, product.transport_process)
        for primitive in self.primitive_factory.primitives:
            transport_process_with_product[primitive.transport_process.data.ID] = (primitive, primitive.transport_process)
        return list(transport_process_with_product.values())

    def _precompute_transport_compatibility(self, dummy_products: dict[str, product.Product]):
        """
        Precompute transport resource compatibility.
        
        Args:
            dummy_products: Dictionary of dummy products for testing.
        """
        all_locations = self.get_all_transport_locations()

        # TODO: maybe add caching to avoid symmetric keys (origin -> target and target -> origin)        
        required_transport_processes = self.get_required_transport_processes(dummy_products)

        for item, requested_process in required_transport_processes:
            original_locatable = item.current_locatable
            for transport_resource in self.resource_factory.get_movable_resources():
                for offered_process in transport_resource.processes:
                    # For each possible origin-target pair (including queues)
                    for origin in all_locations:
                        for target in all_locations:
                            item.current_locatable = origin
                            dummy_transport_request = request.Request(
                                process=requested_process,
                                requesting_item=item,
                                resource=transport_resource,
                                origin=origin,
                                target=target,
                                request_type=request.RequestType.TRANSPORT,
                            )
                            if not offered_process.matches_request(dummy_transport_request):
                                continue
                            # Handle different types of transport processes
                            if isinstance(offered_process, process.RequiredCapabilityProcess):
                                self._handle_required_capability_process(
                                    dummy_transport_request, requested_process, 
                                    transport_resource, offered_process, origin, target
                                )
                            elif isinstance(offered_process, process.LinkTransportProcess):
                                self._handle_link_transport_process(
                                    dummy_transport_request, requested_process,
                                    transport_resource, offered_process, origin, target
                                )
                            else:
                                # Regular transport process
                                key = TransportCompatibilityKey(
                                    origin_id=origin.data.ID,
                                    target_id=target.data.ID,
                                    process_signature=requested_process.get_process_signature(),
                                )
                                self._add_to_transport_compatibility(key, transport_resource, offered_process)
                                self.reachability_cache[(origin.data.ID, target.data.ID)] = True
                                
                                # Cache the route
                                self._cache_route(dummy_transport_request, origin, target, offered_process, [])
            item.current_locatable = original_locatable

    def _precompute_rework_compatibility(self):
        """
        Precompute rework process compatibility.
        """
        self.rework_compatibility = {}
        for rework_process in self.resource_factory.process_factory.processes.values():
            if not isinstance(rework_process, process.ReworkProcess):
                continue

            for reworked_process_id in rework_process.reworked_process_ids:
                reworked_process = self.resource_factory.process_factory.get_process(
                    reworked_process_id
                )
                if not reworked_process:
                    raise ValueError(
                        f"Reworked process ID {reworked_process_id} not found in process factory for rework process {rework_process.data.ID}"
                    )
                if not reworked_process.data.failure_rate or reworked_process.data.failure_rate == 0:
                    continue
                process_signature = reworked_process.get_process_signature()
                if process_signature not in self.rework_compatibility:
                    self.rework_compatibility[process_signature] = []
                self.rework_compatibility[process_signature].append(rework_process)