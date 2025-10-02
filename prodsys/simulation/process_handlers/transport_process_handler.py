
from __future__ import annotations
from typing import List, Generator, TYPE_CHECKING, Union

import logging

from prodsys.simulation import (
    port,
    primitive,
    route_finder,
    sim,
    state,
)

from prodsys.simulation.process import (
    LinkTransportProcess,
)

if TYPE_CHECKING:
    from prodsys.simulation import (
        product,
        state,
    )
    from prodsys.simulation import request as request_module

logger = logging.getLogger(__name__)


class TransportProcessHandler:
    """
    Controller for transport resources.
    """

    def __init__(self, env: sim.Environment) -> None:
        self.env = env
        self.resource = None

    def get_next_product_for_process(
        self, queue: port.Queue, product: product.Product
    ) -> Generator:
        """
        Get the next product for a process from the output queue of a resource.

        Args:
            resource (product.Locatable): Resource or Source to get the product from.
            product (product.Product): The product that shall be transported.

        Raises:
            ValueError: If the product is not in the queue.
            ValueError: If the resource is not a  Resource

        Returns:
            Generator: The generator yields when the product is in the queue.
        """
        yield from queue.get(product.data.ID)

    def put_product_to_input_queue(
        self, queue: port.Queue, product: product.Product
    ) -> Generator:
        """
        Put a product to the input queue of a resource.

        Args:
            locatable (product.Locatable): Resource or Sink to put the product to.
            product (product.Product): The product that shall be transported.

        Raises:
            ValueError: If the resource is not a  Resource

        Returns:
            Generator: The generator yields when the product is in the queue.
        """
        yield from queue.put(product.data)

    def update_location(
        self, locatable: product.Locatable, location: list[float]
    ) -> None:
        """
        Set the current position of the transport resource.

        Args:
            locatable (product.Locatable): The current position.
            to_output (Optional[bool], optional): If the transport resource is moving to the output location. Defaults to None.
        """
        self.resource.set_location(locatable)

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
        product = process_request.get_item()
        origin = process_request.get_origin()
        target = process_request.get_target()

        origin_queue, target_queue = (
            process_request.origin_queue,
            process_request.target_queue,
        )
        route_to_target = process_request.get_route()
        if process_request.required_dependencies:
            yield process_request.request_dependencies()
        yield from resource.setup(process)
        if not resource.current_locatable:
            resource.set_location(origin)
        with resource.request() as req:
            yield req
            resource.controller.mark_started_process()
            if origin_queue.get_location() != resource.get_location():
                # FIXME: move to origin_queue and not to origin for link transport process route finder...
                route_to_origin = self.find_route_to_origin(process_request)
                transport_state: state.State = yield self.env.process(
                    resource.wait_for_free_process(process)
                )
                transport_state.reserved = True
                yield from self.run_transport(
                    transport_state, product, route_to_origin, empty_transport=True
                )
                transport_state.process = None

            yield from self.get_next_product_for_process(origin_queue, product)
            product.update_location(self.resource)

            transport_state: state.State = yield from resource.wait_for_free_process(
                process
            )
            transport_state.reserved = True
            yield from self.run_transport(
                transport_state, product, route_to_target, empty_transport=False
            )
            transport_state.process = None
            # FIXME: Primitives should not be places in product queues...
            yield from self.put_product_to_input_queue(target_queue, product)
            product.update_location(target_queue)

            product.router.mark_finished_request(process_request)
            self.resource.controller.mark_finished_process()

    def run_transport(
        self,
        transport_state: state.State,
        item: Union[product.Product, primitive.Primitive],
        route: List[product.Locatable],
        empty_transport: bool,
    ) -> Generator:
        """
        Run the transport process and every single transport step in the route of the transport process.

        Args:
            transport_state (state.State): The transport state of the process.
            product (product.Product): The product that is transported.
            route (List[product.Locatable]): The route of the transport with locatable objects.
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
        target: product.Locatable,
        empty_transport: bool,
        last_transport_step: bool,
    ) -> list[float]:
        """
        Get the position of the target where the material exchange is done (either picking up or putting down)

        Args:
            target (product.Locatable): The target of the transport.
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
        target: product.Locatable,
        empty_transport: bool,
        initial_transport_step: bool,
        last_transport_step: bool,
    ):
        """
        Run the process of a product. The process is started and the product is logged.

        Args:
            input_state (state.State): The transport state of the process.
            item (Union[product.Product, primitive.Primitive]): The product that is transported.
            target (product.Locatable): The target of the transport.
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
        )
        target_location = self.get_target_location(
            target, empty_transport, last_transport_step=last_transport_step
        )
        input_state.process = self.env.process(
            input_state.process_state(target=target_location, empty_transport=empty_transport, initial_transport_step=initial_transport_step, last_transport_step=last_transport_step)  # type: ignore False
        )
        yield input_state.process
        self.update_location(target, location=target_location)

    def find_route_to_origin(
        self, process_request: request_module.Request
    ) -> List[product.Locatable]:
        """
        Find the route to the origin of the transport request.

        Args:
            process_request (request.TransportResquest): The transport request.

        Returns:
            List[product.Locatable]: The route to the origin. In case of a simple transport process, the route is just the origin.
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
