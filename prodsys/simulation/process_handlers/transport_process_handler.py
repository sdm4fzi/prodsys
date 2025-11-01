
from __future__ import annotations
from typing import List, Generator, TYPE_CHECKING, Union

import logging

from prodsys.simulation import (
    route_finder,
    sim,
    state,
)

from prodsys.simulation.process import (
    LinkTransportProcess,
)

if TYPE_CHECKING:
    from prodsys.simulation import (
        state,
        resources,
    )
    from prodsys.simulation import request as request_module
    from prodsys.simulation import locatable
    from prodsys.simulation.entities import product, primitive
logger = logging.getLogger(__name__)


class TransportProcessHandler:
    """
    Controller for transport resources.
    """

    def __init__(self, env: sim.Environment) -> None:
        self.env = env
        self.resource = None
        self.blocked_capacity = 0

    def get_entities_of_request(
        self, process_request: request_module.Request
    ) -> Generator:
        """
        Get the next product for a process from the output queue of a resource.

        Args:
            process_request (request_module.Request): The request to get the entities from.
        
        Raises:
            ValueError: If the product is not in the queue.

        Returns:
            Generator: The generator yields when the product is in the queue.
        """
        for entity in process_request.get_atomic_entities():
            yield from process_request.origin_queue.get(entity.data.ID)


        
    def put_entities_of_request(
        self, process_request: request_module.Request
    ) -> Generator:
        """
        Put a product to the input queue of a resource.

        Args:
            process_request (request_module.Request): The request to put the entities to.


        Returns:
            Generator: The generator yields when the product is in the queue.
        """
        for entity in process_request.get_atomic_entities():
            yield from process_request.target_queue.put(entity.data)
        
    def update_location(
        self, locatable: locatable.Locatable
    ) -> None:
        """
        Set the current position of the transport resource.

        Args:
            locatable (locatable.Locatable): The current position.
            to_output (Optional[bool], optional): If the transport resource is moving to the output location. Defaults to None.
        """
        self.resource.set_location(locatable)

    def block_other_transports(self, transport_resource: resources.Resource):
        free_capacity = transport_resource.get_free_capacity()
        transport_resource.controller.reserved_requests_count += free_capacity
        self.blocked_capacity += free_capacity
        transport_resource.update_full()

    def unblock_other_transports(self, transport_resource: resources.Resource):
        transport_resource.controller.reserved_requests_count -= self.blocked_capacity
        self.blocked_capacity = 0
        transport_resource.update_full()

    def handle_request(self, process_request: request_module.Request) -> Generator:
        """
        Start the next process.

        The logic is the following:

        1. Get the next request.
        2. Get the resource, process, product, origin and target from the request.
        3. Setup the resource for the process.
        4. Wait until the resource is free.
        5. If the origin is not the location of the transport resource, wait until the transport is free.
        6. Move transport resource to the origin.
        7. Get the product from the origin.
        8. Move transport resource to the target.
        9. Put the product to the target.
        10. Go to 1.


        Yields:
            Generator: The generator yields when the transport is over.
        """
        resource = process_request.get_resource()
        self.resource = resource
        process = process_request.get_process()
        origin = process_request.get_origin()
        origin_queue = process_request.origin_queue
        self.block_other_transports(resource)
        # Take only route and dependencies of the main request of the lot
        route_to_target = process_request.get_route()
        if process_request.required_dependencies:
            yield process_request.request_dependencies()
        yield from resource.setup(process)
        if not resource.current_locatable:
            resource.set_location(origin)
        resource_requests = []
        for _ in range(process_request.capacity_required):
            resource_request = resource.request()
            yield resource_request
            resource_requests.append(resource_request)
        resource.controller.mark_started_process(process_request.capacity_required)
        # TODO: consider conveyor must not go to origin to pickup material, only agv -> differntiate by can_move attribute of resource
        if origin_queue.get_location() != resource.get_location():
            route_to_origin = self.find_route_to_origin(process_request)
            transport_state_events = []
            for entity in process_request.get_atomic_entities():
                transport_state: state.State = yield from resource.wait_for_free_process(process)
                transport_state.reserved = True
                transport_event = self.env.process(self.run_transport(
                    transport_state, entity, route_to_origin, empty_transport=True
                ))
                transport_state_events.append((transport_event, transport_state))
            for transport_event, transport_state in transport_state_events:
                yield transport_event
                transport_state.process = None
        self.update_location(process_request.get_origin())
        yield from self.get_entities_of_request(process_request)
        for entity in process_request.get_atomic_entities():
            entity.update_location(self.resource)

        # Don't reserve target queue for transport!
        # For INPUT_OUTPUT queues, reserving causes deadlock because processed items fill the queue
        # For separate queues with batching, we can't know batch size until lot is formed
        # Let PUT naturally wait for space - this is safer and avoids circular dependencies

        transport_state_events = []
        for entity in process_request.get_atomic_entities():
            transport_state: state.State = yield from resource.wait_for_free_process(
                process
            )
            transport_state.reserved = True
            transport_event = self.env.process(self.run_transport(
                transport_state, entity, route_to_target, empty_transport=False
            ))
            transport_state_events.append((transport_event, transport_state))
        for transport_event, transport_state in transport_state_events:
            yield transport_event
            transport_state.process = None


        yield from self.put_entities_of_request(process_request)
        for entity in process_request.get_atomic_entities():
            entity.update_location(process_request.target_queue)

        process_request.entity.router.mark_finished_request(process_request)
        self.resource.controller.mark_finished_process(process_request.capacity_required)
        for resource_request in resource_requests:
            resource.release(resource_request)
        self.unblock_other_transports(resource)

    def run_transport(
        self,
        transport_state: state.State,
        item: Union[product.Product, primitive.Primitive],
        route: List[locatable.Locatable],
        empty_transport: bool,
    ) -> Generator:
        """
        Run the transport process and every single transport step in the route of the transport process.

        Args:
            transport_state (state.State): The transport state of the process.
            product (product.Product): The product that is transported.
            route (List[locatable.Locatable]): The route of the transport with locatable objects.
            empty_transport (bool): If the transport is empty.

        Yields:
            Generator: The generator yields when the transport is over.
        """
        for link_index, (location, next_location) in enumerate(zip(route, route[1:])):
            if link_index == 0:
                initial_transport_step = True
            else:
                initial_transport_step = False
            if link_index == len(route) - 2:
                last_transport_step = True
            else:
                last_transport_step = False
            transport_state.process = self.env.process(
                self.run_process(
                    transport_state,
                    item,
                    target=next_location,
                    empty_transport=empty_transport,
                    initial_transport_step=initial_transport_step,
                    last_transport_step=last_transport_step,
                )
            )
            transport_state.reserved = False
            yield transport_state.process

    def get_target_location(
        self,
        target: locatable.Locatable,
        empty_transport: bool,
        last_transport_step: bool,
    ) -> list[float]:
        """
        Get the position of the target where the material exchange is done (either picking up or putting down)

        Args:
            target (locatable.Locatable): The target of the transport.
            empty_transport (bool): If the transport is empty.
            last_transport_step (bool): If this is the last transport step.

        Returns:
            list[float]: The position of the target, list with 2 floats.
        """
        return target.get_location()
    
    def run_process(
        self,
        input_state: state.TransportState,
        item: Union[product.Product, primitive.Primitive],
        target: locatable.Locatable,
        empty_transport: bool,
        initial_transport_step: bool,
        last_transport_step: bool,
    ):
        """
        Run the process of a product. The process is started and the product is logged.

        Args:
            input_state (state.State): The transport state of the process.
            item (Union[product.Product, primitive.Primitive]): The product that is transported.
            target (locatable.Locatable): The target of the transport.
            empty_transport (bool): If the transport is empty.
            initial_transport_step (bool): If this is the initial transport step.
            last_transport_step (bool): If this is the last transport step.
        """
        if not hasattr(item, "product_info"):
            input_state.state_info.log_primitive(item, state.StateTypeEnum.transport)
        else:
            input_state.state_info.log_product(item, state.StateTypeEnum.transport)

        origin = self.resource.current_locatable
        input_state.state_info.log_transport(
            origin,
            target,
            state.StateTypeEnum.transport,
            empty_transport=empty_transport,
            initial_transport_step=initial_transport_step,
            last_transport_step=last_transport_step,
        )
        target_location = self.get_target_location(
            target, empty_transport, last_transport_step=last_transport_step
        )
        input_state.process = self.env.process(
            input_state.process_state(target=target_location, empty_transport=empty_transport, initial_transport_step=initial_transport_step, last_transport_step=last_transport_step)  # type: ignore False
        )
        yield input_state.process
        self.update_location(target)

    def find_route_to_origin(
        self, process_request: request_module.Request
    ) -> List[locatable.Locatable]:
        """
        Find the route to the origin of the transport request.

        Args:
            process_request (request.TransportResquest): The transport request.

        Returns:
            List[locatable.Locatable]: The route to the origin. In case of a simple transport process, the route is just the origin.
        """
        if isinstance(process_request.process, LinkTransportProcess):
            route_to_origin = route_finder.find_route(
                request=process_request,
                find_route_to_origin=True,
                process=process_request.get_process(),
            )
            if not route_to_origin:
                raise ValueError(
                    f"Route to origin for transport of {process_request.requesting_item.data.ID} could not be found. Router selected a transport resource that can perform the transport but does not reach the origin."
                )
            return route_to_origin
        else:
            return [self.resource.current_locatable, process_request.origin_queue]
