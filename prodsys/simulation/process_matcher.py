from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Tuple

import logging
import time


logger = logging.getLogger(__name__)


from prodsys.factories import primitive_factory
from prodsys.models.source_data import RoutingHeuristic
from prodsys.simulation import primitive, request, process


if TYPE_CHECKING:
    from prodsys.simulation import resources, product, sink, process
    from prodsys.factories import (
        resource_factory,
        sink_factory,
        product_factory,
        source_factory,
    )
    from prodsys.control import routing_control_env
    from prodsys.models import product_data
    from prodsys.simulation.product import Locatable

    # from prodsys.factories.source_factory import SourceFactory


@dataclass(frozen=True)
class ResourceCompatibilityKey:
    """Key for the resource compatibility lookup table."""
    process_signature: str

    @classmethod
    def from_request(cls, request: request.Request) -> "ResourceCompatibilityKey":
        """Create a key from a request."""
        product_type = request.requesting_item.data.type
        process_signature = request.process.get_process_signature()
        return cls(product_type=product_type, process_signature=process_signature)


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
        reachability_cache: Dict[Tuple[str, str], bool],
        route_cache: Dict[Tuple[str, str, str], request.Request],
    ):
        """
        Initialize the ProcessMatcher with the necessary factories and routing control environment.

        Args:
            resource_factory (ResourceFactory): Factory for creating resources.
            sink_factory (SinkFactory): Factory for creating sinks.
            auxiliary_factory (AuxiliaryFactory): Factory for creating auxiliaries.
            product_factory (ProductFactory): Factory for creating products.
            source_factory (SourceFactory): Factory for creating sources.
            routing_control_env (RoutingControlEnv): Environment for routing control.
        """
        self.resource_factory = resource_factory
        self.sink_factory = sink_factory
        self.product_factory = product_factory
        self.source_factory = source_factory
        self.primitive_factory = primitive_factory
        self.route_cache = route_cache
        self.reachability_cache = reachability_cache

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
        process_model = product.process_model
        # FIXME: resolve that also precedence graph models work
        return process_model.process_list

    def precompute_compatibility_tables(self):
        """
        Precompute compatibility tables for resources and processes.
        This method runs at initialization time to create lookup tables
        that will speed up resource selection during simulation.
        """
        start_time = time.time()
        logger.info("Precomputing resource compatibility tables...")

        # Get dummy product for testing
        dummy_products: dict[str, product.Product] = {}
        for source in self.source_factory.sources.values():
            product_type = source.product_data.type
            dummy_products[product_type] = self._create_dummy_product(
                source.product_data
            )

        # Precompute production resource compatibility
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
                            dummy_product.update_executed_process(offered_process)

        # Precompute transport resource compatibility and reachability
        required_transport_processes = [(item, item.transport_process) for item in list(dummy_products.values()) + self.primitive_factory.primitives]
        for item, requested_process in required_transport_processes:
            for transport_resource in self.resource_factory.get_movable_resources():
                for offered_process in transport_resource.processes:
                    # For each possible origin-target pair
                    all_locations = (
                        list(self.resource_factory.all_resources.values())
                        + list(self.sink_factory.sinks.values())
                        + list(self.source_factory.sources.values())
                        + [q for q in self.resource_factory.queue_factory.queues if hasattr(q.data, "location") and q.data.location is not None]
                    )
                    for origin in all_locations:
                        for target in all_locations:
                            # Create a dummy request to test matching
                            dummy_product.current_locatable = origin

                            dummy_transport_request = request.Request(
                                process=requested_process,
                                requesting_item=dummy_product,
                                resource=transport_resource,
                                origin=origin,
                                target=target,
                                request_type=request.RequestType.TRANSPORT,
                            )

                            # Test if this transport process can handle this origin-target pair
                            if offered_process.matches_request(dummy_transport_request):
                                key = TransportCompatibilityKey(
                                    origin_id=origin.data.ID,
                                    target_id=target.data.ID,
                                    process_signature=requested_process.get_process_signature(),
                                )
                                if key not in self.transport_compatibility:
                                    self.transport_compatibility[key] = []

                                if (transport_resource, offered_process) in self.transport_compatibility[key]:
                                    # Avoid duplicates
                                    continue
                                self.transport_compatibility[key].append(
                                    (transport_resource, offered_process)
                                )

                                # Cache reachability information
                                self.reachability_cache[
                                    (origin.data.ID, target.data.ID)
                                ] = True

                                # Cache the route
                                route_key = (
                                    origin.data.ID,
                                    target.data.ID,
                                    offered_process.get_process_signature(),
                                )
                                if route_key not in self.route_cache:
                                    self.route_cache[route_key] = (
                                        dummy_transport_request
                                    )

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


        # Precompute rework process compatibility

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
                if not process_signature in self.rework_compatibility:
                    self.rework_compatibility[process_signature] = []
                self.rework_compatibility[process_signature].append(rework_process)

        

        print(self.rework_compatibility)

        logger.info(
            f"Precomputation completed in {time.time() - start_time:.2f} seconds"
        )
        logger.info(
            f"Production compatibility table contains {len(self.production_compatibility)} entries"
        )
        logger.info(
            f"Transport compatibility table contains {len(self.transport_compatibility)} entries"
        )
        logger.info(
            f"Reachability cache contains {len(self.reachability_cache)} entries"
        )
        logger.info(
            f"Rework compatibility table contains {len(self.rework_compatibility)} entries"
        )

    def get_route(
        self, origin: Locatable, target: Locatable, process: process.PROCESS_UNION
    ) -> request.Request:
        """
        Returns the route for a given origin, target, and process signature.

        Args:
            origin (Locatable): The origin location.
            target (Locatable): The target location.
            process_signature (str): The process signature.

        Returns:
            request.Request: The route request.
        """
        process_signature = process.get_process_signature()
        key = (origin.data.ID, target.data.ID, process_signature)
        return self.route_cache.get(key).route

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
            raise ValueError(
                f"No compatible rework processes found for failed process {failed_process.data.ID} with signature {process_signature}"
            )
        return rework_processes