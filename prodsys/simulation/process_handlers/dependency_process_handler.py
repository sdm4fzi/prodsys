
from __future__ import annotations

from typing import List, Generator, TYPE_CHECKING

import logging

from prodsys.models.processes_data import ProcessTypeEnum
from prodsys.simulation.request import RequestType

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
    )
    from prodsys.simulation import request as request_module
    from prodsys.simulation.dependency import Dependency
    from prodsys.simulation import locatable

logger = logging.getLogger(__name__)


class DependencyProcessHandler:
    def __init__(self, env: sim.Environment) -> None:
        self.env = env
        self.resource = None

    def update_location(
        self, locatable: locatable.Locatable, location: list[float]
    ) -> None:
        """
        Set the current position of the transport resource.

        Args:
            locatable (locatable.Locatable): The current position.
            to_output (Optional[bool], optional): If the transport resource is moving to the output location. Defaults to None.
        """
        self.resource.set_location(locatable)

    def handle_request(self, process_request: request_module.Request) -> Generator:
        """
        Start the next process with the following logic:

        1. Wait until the resource is free for the process.
        2. Wait until the dependencies are fulfilled.
        3. Run the process and wait until finished.

        Yields:
            Generator: The generator yields when the process is finished.
        """
        requesting_item = process_request.requesting_item
        self.resource = process_request.get_resource()
        self.resource.bind_to_dependant(requesting_item)
        process = [
            process
            for process in self.resource.processes
            if process.data.type
            in (
                ProcessTypeEnum.TransportProcesses,
                ProcessTypeEnum.LinkTransportProcesses,
            )
        ].pop()
        if process_request.resolved_dependency.interaction_node:
            target = process_request.resolved_dependency.interaction_node
        else:
            target = requesting_item
        if process_request.required_dependencies:
            yield process_request.request_dependencies()
        yield from self.resource.setup(process)
        if not self.resource.current_locatable:
            self.resource.set_location(target)
        with self.resource.request() as req:
            yield req
            self.resource.controller.mark_started_process()
            if target.get_location() != self.resource.get_location():
                move_request = request_module.Request(
                    request_type=RequestType.TRANSPORT,
                    process=process,
                    resource=self.resource,
                    requesting_item=target,
                    origin=target,
                )
                route_to_origin = self.find_route_to_origin(move_request)
                transport_state: state.State = yield self.env.process(
                    self.resource.wait_for_free_process(process)
                )
                transport_state.reserved = True
                yield from self.run_transport(
                    transport_state,
                    route_to_origin,
                    empty_transport=True,
                    dependency=process_request.resolved_dependency,
                )
                transport_state.process = None

            # product.product_router.mark_finished_request(process_request)
        process_request.completed.succeed()
        self.resource.dependency_info.log_start_dependency(
            event_time=self.env.now,
            requesting_item_id=process_request.requesting_item.data.ID,
            dependency_id=process_request.resolved_dependency.data.ID,
        )
        yield process_request.dependency_release_event
        self.resource.dependency_info.log_end_dependency(
            event_time=self.env.now,
            requesting_item_id=process_request.requesting_item.data.ID,
            dependency_id=process_request.resolved_dependency.data.ID,
        )
        self.resource.release_from_dependant()
        self.resource.controller.mark_finished_process()

    def run_transport(
        self,
        transport_state: state.State,
        route: List[locatable.Locatable],
        empty_transport: bool,
        dependency: Dependency,
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
        transport_state.state_info._dependency_ID = None
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
                    target=next_location,
                    dependency=dependency,
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
        target: locatable.Locatable,
        empty_transport: bool,
        initial_transport_step: bool,
        last_transport_step: bool,
        dependency: Dependency,
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
        # TODO: update logs here to consider dependencies
        # if not hasattr(product, "product_info"):
        #     input_state.state_info.log_Primitive(product, state.StateTypeEnum.transport)
        # else:
        #     input_state.state_info.log_product(product, state.StateTypeEnum.transport)

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
            return [self.resource.current_locatable, process_request.get_origin()]


from prodsys.simulation import request as request_module