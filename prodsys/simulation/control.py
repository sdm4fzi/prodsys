from __future__ import annotations

from collections.abc import Callable
from pydantic import ConfigDict, Field, field_validator, ValidationInfo
from typing import List, Generator, TYPE_CHECKING, Literal, Optional, Union
import numpy as np
import random

import logging

from prodsys.models.processes_data import ProcessTypeEnum
from prodsys.models.queue_data import StoreData
from prodsys.models.resource_data import ResourceData
from prodsys.simulation.request import RequestType


logger = logging.getLogger(__name__)

from simpy import events

from prodsys.simulation import (
    primitive,
    route_finder,
    sim,
    state,
    process,
    store,
)

from prodsys.simulation.process import (
    LinkTransportProcess,
    ReworkProcess,
)

if TYPE_CHECKING:
    from prodsys.simulation import (
        product,
        process,
        state,
        resources,
        sink,
        source,
        store,
    )
    from prodsys.simulation import request as request_module
    from prodsys.control import sequencing_control_env
    from prodsys.simulation.product import Locatable
    from prodsys.simulation.dependency import Dependency


class Controller:
    """
    A controller is responsible for controlling the processes of a resource. The controller is requested by products requiring processes. The controller decides has a control policy that determines with which sequence requests are processed.

    Args:
        control_policy (Callable[[List[Request]], None]): The control policy that determines the sequence of requests to be processed.
        env (sim.Environment): The environment in which the controller is running.

    Attributes:
        control_policy (Callable[[List[Request]], None]): The control policy that determines the sequence of requests to be processed.
        env (sim.Environment): The environment in which the controller is running.
        requests (List[Request]): The list of requests that are waiting to be processed.
        requested (events.Event): The event that is triggered when a request is made.
        resource (resources.Resource): The resource that is controlled by the controller.
        process_finished (events.Event): The event that is triggered when a process is finished.
        num_running_processes (int): The number of processes that are currently running.
        reserved_requests_count (int): The number of requests that are reserved for processing.
    """

    def __init__(
        self,
        control_policy: Callable[
            [
                List[request_module.Request],
            ],
            None,
        ],
        env: sim.Environment,
    ) -> None:
        self.control_policy = control_policy
        self.env = env
        self.requests: List[request_module.Request] = []
        self.state_changed: events.Event = events.Event(env)
        self.resource: resources.Resource = None
        self.num_running_processes = 0
        self.reserved_requests_count = 0

    def set_resource(self, resource: resources.Resource) -> None:
        self.resource = resource
        self.env = resource.env

    def request(self, process_request: request_module.Request) -> None:
        """
        Request the controller consider the request in the future for processing.

        Args:
            process_request (Request): The request to be processed.
        """
        self.requests.append(process_request)
        if not self.state_changed.triggered:
            self.state_changed.succeed()

    def control_loop(self) -> Generator:
        """
        The control loop is the main process of the controller. It has to run indefinetely.
        It should repeatedly check if requests are made or a process is finished and then start the next process.
        """
        while True:
            if self.resource.requires_charging:
                # TODO: transport AGV to charging station, -> use a ChargingHandler for this!
                yield self.env.process(self.resource.charge())
            yield self.state_changed
            self.state_changed = events.Event(self.env)
            if (
                self.resource.full
                or self.resource.in_setup
                or self.resource.bound
                or not self.requests
            ):
                continue
            self.control_policy(self.requests)
            selected_request = self.requests.pop(0)
            self.reserved_requests_count += 1
            self.resource.update_full()
            process_handler = get_requets_handler(selected_request)
            self.env.process(process_handler.handle_request(selected_request))
            if not self.resource.full and self.requests:
                self.state_changed.succeed()

    def mark_started_process(self) -> None:
        """
        Mark the process as started.

        Args:
            process_request (Request): The request that is being processed.
        """
        self.reserved_requests_count -= 1
        self.num_running_processes += 1

    def mark_finished_process(self) -> None:
        """
        Mark the process as finished.

        Args:
            process_request (Request): The request that is being processed.
        """
        self.num_running_processes -= 1
        self.resource.update_full()
        if not self.state_changed.triggered:
            self.state_changed.succeed()


def get_requets_handler(
    request: request_module.Request,
) -> Union[ProductionProcessHandler, TransportProcessHandler, DependencyProcessHandler]:
    """
    Get the process handler for a given process.

    Args:
        process (process.PROCESS_UNION): The process to get the handler for.

    Returns:
        Union[ProductionProcessHandler, TransportProcessHandler]: The process handler for the given process.
    """
    if (
        request.request_type == request_module.RequestType.PRODUCTION
        or request.request_type == request_module.RequestType.REWORK
    ):
        return ProductionProcessHandler(request.requesting_item.env)
    elif request.request_type == request_module.RequestType.TRANSPORT:
        return TransportProcessHandler(request.requesting_item.env)
    elif (
        request.request_type == request_module.RequestType.PROCESS_DEPENDENCY
        or request.request_type == request_module.RequestType.RESOURCE_DEPENDENCY
    ):
        return DependencyProcessHandler(request.requesting_item.env)
    else:
        raise ValueError(f"Unknown process type: {type(process)}")


class ProductionProcessHandler:
    """
    A production controller is responsible for controlling the processes of a production resource. The controller is requested by products requiring processes. The controller decides has a control policy that determines with which sequence requests are processed.
    """

    def __init__(self, env: sim.Environment) -> None:
        self.env = env
        self.resource = None
        self.process_time: Optional[float] = None

    def set_process_time(self, process_time: float) -> None:
        """
        Set the process time for the production process.

        Args:
            process_time (float): The process time for the production process.
        """
        self.process_time = process_time

    def get_next_product_for_process(
        self, queue: store.Queue, product: product.Product
    ) -> Generator:
        """
        Get the next product for a process. The product is removed (get) from the input queues of the resource.

        Args:
            resource (resources.Resource): The resource to take the product from.
            product (product.Product): The product that is requesting the product.

        Returns:
            List[events.Event]: The event that is triggered when the product is taken from the queue (multiple events for multiple products, e.g. for a batch process or an assembly).
        """
        yield from queue.get(product.data.ID)

    def put_product_to_output_queue(
        self, queue: store.Queue, product: product.Product
    ) -> Generator:
        """
        Place a product to the output queue (put) of the resource.

        Args:
            resource (resources.Resource): The resource to place the product to.
            products (List[product.Product]): The products to be placed.

        Returns:
            List[events.Event]: The event that is triggered when the product is placed in the queue (multiple events for multiple products, e.g. for a batch process or an assembly).
        """
        yield from queue.put(product.data)

    def handle_request(self, process_request: request_module.Request) -> Generator:
        """
        Start the next process with the following logic:

        1. Setup the resource for the process.
        2. Wait until the resource is free for the process.
        3. Retrieve the product from the queue.
        4. Run the process and wait until finished.
        5. Place the product in the output queue.

        Yields:
            Generator: The generator yields when the process is finished.
        """
        resource = process_request.get_resource()
        self.resource = resource
        process = process_request.get_process()
        product = process_request.get_item()

        origin_queue, target_queue = (
            process_request.origin_queue,
            process_request.target_queue,
        )
        if process_request.required_dependencies:
            yield process_request.request_dependencies()
        yield from resource.setup(process)
        with resource.request() as req:
            yield req
            self.get_next_product_for_process(origin_queue, product)
            resource.controller.mark_started_process()
            production_state: state.State = yield from resource.wait_for_free_process(
                process
            )
            production_state.reserved = True
            yield from self.run_process(production_state, product, process)
            production_state.process = None

            yield from self.put_product_to_output_queue(target_queue, product)
            resource.adjust_pending_put_of_output_queues()  # output queues do not get reserved, so the pending put has to be adjusted manually
            product.router.mark_finished_request(process_request)
            self.resource.controller.mark_finished_process()

    def run_process(
        self,
        input_state: state.State,
        target_product: product.Product,
        process: process.Process,
    ):
        """
        Run the process of a product. The process is started and the product is logged.

        Args:
            input_state (state.State): The production state of the process.
            target_product (product.Product): The product that is processed.
        """
        input_state.state_info.log_product(
            target_product, state.StateTypeEnum.production
        )
        input_state.process = self.env.process(input_state.process_state(time=self.process_time))  # type: ignore False
        input_state.reserved = False
        self.handle_rework_required(target_product, process)

        yield input_state.process

    def handle_rework_required(
        self, product: product.Product, process: process.Process
    ):
        """
        Determine if rework is needed based on the process's failure rate.

        Args:
            process (process.Process): The process to check for failure rate.
        """
        if isinstance(process, ReworkProcess):
            return
        failure_rate = process.data.failure_rate
        if not failure_rate or failure_rate == 0:
            return
        rework_needed = np.random.choice(
            [True, False], p=[failure_rate, 1 - failure_rate]
        )
        if not rework_needed:
            return
        product.add_needed_rework(process)


class TransportProcessHandler:
    """
    Controller for transport resources.
    """

    def __init__(self, env: sim.Environment) -> None:
        self.env = env
        self.resource = None

    def get_next_product_for_process(
        self, queue: store.Queue, product: product.Product
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
        queue.get(product.data.ID)

    def put_product_to_input_queue(
        self, queue: store.Queue, product: product.Product
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
            if origin.get_location() != resource.get_location():
                route_to_origin = self.find_route_to_origin(process_request)
                transport_state: state.State = yield self.env.process(
                    resource.wait_for_free_process(process)
                )
                transport_state.reserved = True
                yield from self.run_transport(
                    transport_state, product, route_to_origin, empty_transport=True
                )
                transport_state.process = None

            self.get_next_product_for_process(origin_queue, product)
            product.update_location(self.resource)

            transport_state: state.State = yield from resource.wait_for_free_process(
                process
            )
            transport_state.reserved = True
            yield from self.run_transport(
                transport_state, product, route_to_target, empty_transport=False
            )
            transport_state.process = None

            yield from self.put_product_to_input_queue(target_queue, product)
            product.update_location(target)

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
        if not last_transport_step or hasattr(target, "product_factory"):
            return target.get_location()
        if empty_transport:
            return target.get_location(interaction="output")
        else:
            return target.get_location(interaction="input")

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
            return [self.resource.current_locatable, process_request.get_origin()]


class DependencyProcessHandler:
    def __init__(self, env: sim.Environment) -> None:
        self.env = env
        self.resource = None

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
        route: List[product.Locatable],
        empty_transport: bool,
        dependency: Dependency,
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
        if not last_transport_step or hasattr(target, "product_factory"):
            return target.get_location()
        if empty_transport:
            return target.get_location(interaction="output")
        else:
            return target.get_location(interaction="input")

    def run_process(
        self,
        input_state: state.TransportState,
        target: product.Locatable,
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
            target (product.Locatable): The target of the transport.
            empty_transport (bool): If the transport is empty.
            initial_transport_step (bool): If this is the initial transport step.
            last_transport_step (bool): If this is the last transport step.
        """
        # TODO: update logs here to consider dependencies
        # if not hasattr(product, "product_info"):
        #     input_state.state_info.log_auxiliary(product, state.StateTypeEnum.transport)
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
            return [self.resource.current_locatable, process_request.get_origin()]


def FIFO_control_policy(requests: List[request_module.Request]) -> None:
    """
    Sort the requests according to the FIFO principle.

    Args:
        requests (List[Request]): The list of requests.
    """
    pass


def LIFO_control_policy(requests: List[request_module.Request]) -> None:
    """
    Sort the requests according to the LIFO principle (reverse the list).

    Args:
        requests (List[Request]): The list of requests.
    """
    requests.reverse()


def SPT_control_policy(requests: List[request_module.Request]) -> None:
    """
    Sort the requests according to the SPT principle (shortest process time first).

    Args:
        requests (List[Request]): The list of requests.
    """
    requests.sort(key=lambda x: x.process.get_expected_process_time())


def get_location(locatable: Locatable, mode: Literal["origin", "target"]):
    if not isinstance(locatable.data, (ResourceData, StoreData)):
        return locatable.get_location()
    if mode == "target":
        return locatable.get_location(interaction="input")
    else:
        return locatable.get_location(interaction="output")


def SPT_transport_control_policy(
    requests: List[request_module.Request],
) -> None:
    """
    Sort the requests according to the SPT principle (shortest process time first).

    Args:
        requests (List[request.Request]): The list of requests.
    """
    requests.sort(
        key=lambda x: x.process.get_expected_process_time(
            get_location(x.origin, "origin"), get_location(x.target, "target")
        )
    )


def nearest_origin_and_longest_target_queues_transport_control_policy(
    requests: List[request_module.Request],
) -> None:
    """
    Sort the requests according to nearest origin without considering the target location.
    Second order sorting by descending length of the target output queues, to prefer targets where a product can be picked up.
    Args:
        requests (List[request.Request]): The list of requests.
    """
    requests.sort(
        key=lambda x: (
            x.process.get_expected_process_time(
                get_location(x.resource), get_location(x.origin, mode="origin")
            ),
            -x.target.get_output_queue_length(),
        )
    )


def nearest_origin_and_shortest_target_input_queues_transport_control_policy(
    requests: List[request_module.Request],
) -> None:
    """
    Sort the requests according to nearest origin without considering the target location.
    Second order sorting by ascending length of the target input queue so that resources with empty input queues get material to process.

    Args:
        requests (List[request.Request]): The list of requests.
    """
    requests.sort(
        key=lambda x: (
            x.process.get_expected_process_time(
                get_location(x.resource), get_location(x.origin, mode="origin")
            ),
            x.target.get_input_queue_length(),
        )
    )


def agent_control_policy(
    gym_env: sequencing_control_env.AbstractSequencingControlEnv,
    requests: List[request_module.Request],
) -> None:
    """
    Sort the requests according to the agent's policy.

    Args:
        gym_env (gym_env.ProductionControlEnv): A gym environment, where the agent can interact with the simulation.
        requests (List[Request]): The list of requests.
    """
    gym_env.interrupt_simulation_event.succeed()


class BatchController(Controller):
    """
    A batch controller is responsible for controlling the batch processes of a production resource. The controller is requested by products requiring processes. The controller decides has a control policy that determines with which sequence requests are processed.
    """

    def control_loop(self) -> Generator:
        """
        The control loop is the main process of the controller. It has to run indefinetely.

        The logic is the control loop of a production resource is the following:

        1. Wait until a request is made or a process is finished.
        2. If a request is made, add it to the list of requests.
        3. If a process is finished, remove it from the list of running processes.
        4. If the resource is full or there are not enough requests for a batch, go to 1.
        5. Sort the queue according to the control policy.
        6. Start the next process. Go to 1.

        Yields:
            Generator: The generator yields when a request is made or a process is finished.
        """
        while True:
            if self.resource.requires_charging:
                yield self.env.process(self.resource.charge())
            yield self.state_changed
            self.state_changed = events.Event(self.env)
            if (
                self.resource.full 
                or self.resource.in_setup
                or self.resource.bound
                or not self.requests
            ):
                continue
            if self.resource.get_free_capacity() < self.resource.batch_size:
                continue
            self.control_policy(self.requests)
            selected_request = self.requests.pop(0)
            batch_requests = self.get_batch_requests(
                selected_request
            )

            # TODO: add this as an option in the data model, if only full batches should be processed
            if len(batch_requests) < self.resource.batch_size:
                self.requests.extend(batch_requests)
                continue

            self.reserved_requests_count += len(batch_requests)
            self.resource.update_full()

            process_handlers = [get_requets_handler(request) for request in batch_requests]
            batch_process_time = self.get_batch_process_time(
                selected_request
            )
            for process_handler, request in zip(process_handlers, batch_requests):
                process_handler.set_process_time(
                    batch_process_time
                )
                self.env.process(
                    process_handler.handle_request(request)
                )

    def get_batch_requests(
            self, selected_request: request_module.Request
    ) -> List[request_module.Request]:
        """
        Get the batch requests for a given request which have the same process.

        Args:
            request (request_module.Request): The request to get the batch requests for.

        Returns:
            List[request_module.Request]: The batch requests for the given request.
        """
        batch_requests = [selected_request]
        for req in list(self.requests):
            if len(batch_requests) >= self.resource.batch_size:
                break

            if (
                req.process == selected_request.process
                and req.get_item().data.type == selected_request.get_item().data.type
            ):
                batch_requests.append(req)
                self.requests.remove(req)

        return batch_requests

    def get_batch_process_time(
            self, request: request_module.Request
    ) -> float:
        """
        Get the expected process time for a batch of requests.

        Args:
            request (request_module.Request): The request to get the process time for.

        Returns:
            float: The expected process time for the batch.
        """
        if not request.process:
            raise ValueError("Request has no process.")
        return request.process.time_model.get_next_time(
        )

from prodsys.simulation import request as request_module
from prodsys.simulation import source, sink
