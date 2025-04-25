from __future__ import annotations

from abc import ABC
from collections.abc import Callable
from pydantic import BaseModel, ConfigDict, Field, field_validator, ValidationInfo
from typing import List, Generator, TYPE_CHECKING, Literal, Optional, Union
import numpy as np
import random

import logging


logger = logging.getLogger(__name__)

from simpy import events

from prodsys.simulation import (
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
        auxiliary,
        store,
    )
    from prodsys.simulation import request as request_module
    from prodsys.control import sequencing_control_env
    from prodsys.simulation.product import Locatable


class Controller(ABC, BaseModel):
    """
    A controller is responsible for controlling the processes of a resource. The controller is requested by products requiring processes. The controller decides has a control policy that determines with which sequence requests are processed.

    Args:
        control_policy (Callable[[List[Request]], None]): The control policy that determines the sequence of requests to be processed.
        env (sim.Environment): The environment in which the controller is running.

    Attributes:
        resource (resources.Resource): The resource that is controlled by the controller.
        requested (events.Event): An event that is triggered when a request is made to the controller.
        requests (List[Request]): A list of requests that are made to the controller.
        running_processes (List[events.Event]): A list of (simpy) processes that are currently running on the resource.
    """

    control_policy: Callable[
        [
            List[request_module.Request],
        ],
        None,
    ]
    env: sim.Environment

    resource: resources.Resource = Field(init=False, default=None)
    requested: events.Event = Field(init=False, validate_default=True, default=None)
    requests: List[request_module.Request] = Field(init=False, default_factory=list)
    running_processes: List[events.Process] = []
    reserved_requests_count: int = 0

    @field_validator("requested", mode="before")
    def init_requested(cls, v, info: ValidationInfo):
        event = events.Event(info.data["env"])
        return event

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

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
        logger.debug(
            {
                "ID": "controller",
                "sim_time": self.env.now,
                "resource": self.resource.data.ID,
                "event": f"Got requested by {process_request.product.product_data.ID}",
            }
        )
        if not self.requested.triggered:
            logger.debug(
                {
                    "ID": "controller",
                    "sim_time": self.env.now,
                    "resource": self.resource.data.ID,
                    "event": "Triggered requested event",
                }
            )
            self.requested.succeed()

    def control_loop(self) -> Generator:
        """
        The control loop is the main process of the controller. It has to run indefinetely.
        It should repeatedly check if requests are made or a process is finished and then start the next process.
        """
        while True:
            logger.debug(
                {
                    "ID": "controller",
                    "sim_time": self.env.now,
                    "resource": self.resource.data.ID,
                    "event": "Waiting for request or process to finish",
                }
            )
            if self.resource.requires_charging:
                # TODO: transport AGV to charging station
                yield self.env.process(self.resource.charge())
            yield events.AnyOf(
                env=self.env, events=self.running_processes + [self.requested]
            )
            if self.requested.triggered:
                self.requested = events.Event(self.env)
            for process in self.running_processes:
                if not process.is_alive:
                    self.running_processes.remove(process)
            if (
                self.resource.full
                or not self.requests
                or self.reserved_requests_count == len(self.requests)
            ):
                logger.debug(
                    {
                        "ID": "controller",
                        "sim_time": self.env.now,
                        "resource": self.resource.data.ID,
                        "event": f"No request ({len(self.requests)}) or resource full ({self.resource.full}) or all requests reserved ({self.reserved_requests_count == len(self.requests)})",
                    }
                )
                continue
            self.control_policy(self.requests)
            # TODO: this is maybe not needed for transport processes?
            selected_request = self.requests.pop(0)
            process_handler = get_requets_handler(selected_request)
            running_process = self.env.process(
                process_handler.handle_request(selected_request)
            )
            self.running_processes.append(running_process)
            if not self.resource.full:
                logger.debug(
                    {
                        "ID": "controller",
                        "sim_time": self.env.now,
                        "resource": self.resource.data.ID,
                        "event": "Triggered requested event after process",
                    }
                )
                self.requested.succeed()


def get_requets_handler(
    request: request_module.Request,
) -> Union[ProductionProcessHandler, TransportProcessHandler]:
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
        return ProductionProcessHandler(request.product.env)
    elif request.request_type == request_module.RequestType.TRANSPORT:
        return TransportProcessHandler(request.product.env)
    elif request.request_type == request_module.RequestType.AUXILIARY:
        return AuxiliaryProcessHandler()
    elif request.request_type == request_module.RequestType.MOVE:
        return MoveProcessHandler()
    else:
        raise ValueError(f"Unknown process type: {type(process)}")


class ProductionProcessHandler:
    """
    A production controller is responsible for controlling the processes of a production resource. The controller is requested by products requiring processes. The controller decides has a control policy that determines with which sequence requests are processed.
    """

    def __init__(self, env: sim.Environment) -> None:
        self.env = env
        self.resource = None

    def get_next_product_for_process(
        self, queue: store.Queue, product: product.Product
    ):
        """
        Get the next product for a process. The product is removed (get) from the input queues of the resource.

        Args:
            resource (resources.Resource): The resource to take the product from.
            product (product.Product): The product that is requesting the product.

        Returns:
            List[events.Event]: The event that is triggered when the product is taken from the queue (multiple events for multiple products, e.g. for a batch process or an assembly).
        """
        events = [queue.get(filter=lambda item: item is product.product_data)]

        if not events:
            raise ValueError("No product in queue")
        return events

    def put_product_to_output_queue(self, queue: store.Queue, product: product.Product):
        """
        Place a product to the output queue (put) of the resource.

        Args:
            resource (resources.Resource): The resource to place the product to.
            products (List[product.Product]): The products to be placed.

        Returns:
            List[events.Event]: The event that is triggered when the product is placed in the queue (multiple events for multiple products, e.g. for a batch process or an assembly).
        """
        events = []
        events.append(queue.put(product.product_data))
        return events

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
        product = process_request.get_product()

        # TODO: wait here until all auxiliaries are available for the process
        # auxiliaries = yield self.env.process(product.product_router.get_auxiliaries(process_request))
        origin_queue, target_queue = (
            process_request.origin_queue,
            process_request.target_queue,
        )
        logger.debug(
            {
                "ID": "controller",
                "sim_time": self.env.now,
                "resource": self.resource.data.ID,
                "event": f"Starting process",
            }
        )
        logger.debug(
            {
                "ID": "controller",
                "sim_time": self.env.now,
                "resource": self.resource.data.ID,
                "event": f"Starting setup for process for {product.product_data.ID}",
            }
        )

        yield self.env.process(resource.setup(process))
        with resource.request() as req:
            yield req
            product_retrieval_events = self.get_next_product_for_process(
                origin_queue, product
            )
            logger.debug(
                {
                    "ID": "controller",
                    "sim_time": self.env.now,
                    "resource": self.resource.data.ID,
                    "event": f"Waiting to retrieve product {product.product_data.ID} from queue",
                }
            )
            yield events.AllOf(resource.env, product_retrieval_events)

            production_state: state.State = yield self.env.process(
                resource.wait_for_free_process(process)
            )
            logger.debug(
                {
                    "ID": "controller",
                    "sim_time": self.env.now,
                    "resource": self.resource.data.ID,
                    "event": f"Starting process for {product.product_data.ID}",
                }
            )
            yield self.env.process(self.run_process(production_state, product, process))
            production_state.process = None

            product_put_events = self.put_product_to_output_queue(target_queue, product)
            logger.debug(
                {
                    "ID": "controller",
                    "sim_time": self.env.now,
                    "resource": self.resource.data.ID,
                    "event": f"Waiting to put product {product.product_data.ID} to queue",
                }
            )
            yield events.AllOf(resource.env, product_put_events)
            resource.adjust_pending_put_of_output_queues()  # output queues do not get reserved, so the pending put has to be adjusted manually
            # TODO: add auxiliary logic again
            # for auxiliary in auxiliaries:
            #     auxiliary.release()
            product.product_router.mark_finished_request(process_request)
            product.finished_process.succeed()
            logger.debug(
                {
                    "ID": "controller",
                    "sim_time": self.env.now,
                    "resource": self.resource.data.ID,
                    "event": f"Finished process for {product.product_data.ID}",
                }
            )

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
        input_state.prepare_for_run()
        input_state.state_info.log_product(
            target_product, state.StateTypeEnum.production
        )
        target_product.product_info.log_start_process(
            self.resource,
            target_product,
            self.env.now,
            state.StateTypeEnum.production,
        )
        input_state.process = self.env.process(input_state.process_state())
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
        failure_rate = process.process_data.failure_rate
        if not failure_rate or failure_rate == 0:
            return
        rework_needed = np.random.choice(
            [True, False], p=[failure_rate, 1 - failure_rate]
        )
        if not rework_needed:
            return
        logger.debug(
            {
                "ID": "controller",
                "sim_time": self.env.now,
                "resource": self.resource.data.ID,
                "event": f"Rework needed for {product.product_data.ID}",
            }
        )
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
    ) -> List[events.Event]:
        """
        Get the next product for a process from the output queue of a resource.

        Args:
            resource (product.Locatable): Resource or Source to get the product from.
            product (product.Product): The product that shall be transported.

        Raises:
            ValueError: If the product is not in the queue.
            ValueError: If the resource is not a  ProductionResource or Source.

        Returns:
            List[events.Event]: The event that is triggered when the product is in the queue.
        """
        events = []
        events.append(queue.get(filter=lambda x: x is product.product_data))
        if not events:
            raise ValueError(f"No product in internal queue {queue.data.ID}")
        return events

    def put_product_to_input_queue(
        self, queue: store.Queue, product: product.Product
    ) -> List[events.Event]:
        """
        Put a product to the input queue of a resource.

        Args:
            locatable (product.Locatable): Resource or Sink to put the product to.
            product (product.Product): The product that shall be transported.

        Raises:
            ValueError: If the resource is not a  ProductionResource or Sink.

        Returns:
            List[events.Event]: The event that is triggered when the product is in the queue.
        """
        events = []
        events.append(queue.put(product.product_data))
        return events

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
        product = process_request.get_product()
        origin = process_request.get_origin()
        target = process_request.get_target()

        origin_queue, target_queue = (
            process_request.origin_queue,
            process_request.target_queue,
        )
        route_to_target = process_request.get_route()
        logger.debug(
            {
                "ID": "controller",
                "sim_time": self.env.now,
                "resource": self.resource.data.ID,
                "event": f"Starting setup for process for {product.product_data.ID}",
            }
        )

        yield self.env.process(resource.setup(process))
        if not resource.current_locatable:
            resource.set_location(origin)
        with resource.request() as req:
            yield req
            if origin.get_location() != resource.get_location():
                route_to_origin = self.find_route_to_origin(process_request)
                logger.debug(
                    {
                        "ID": "controller",
                        "sim_time": self.env.now,
                        "resource": self.resource.data.ID,
                        "event": f"Empty transport needed for {product.product_data.ID} from {origin.data.ID} to {target.data.ID}",
                    }
                )
                transport_state: state.State = yield self.env.process(
                    resource.wait_for_free_process(process)
                )
                logger.debug(
                    {
                        "ID": "controller",
                        "sim_time": self.env.now,
                        "resource": self.resource.data.ID,
                        "event": f"Starting transport to pick up {product.product_data.ID} for transport",
                    }
                )
                yield self.env.process(
                    self.run_transport(
                        transport_state, product, route_to_origin, empty_transport=True
                    )
                )

            product_retrieval_events = self.get_next_product_for_process(
                origin_queue, product
            )
            # FIXME: the product is not correctly retrieved from the queue
            logger.debug(
                {
                    "ID": "controller",
                    "sim_time": self.env.now,
                    "resource": self.resource.data.ID,
                    "event": f"Waiting to retrieve product {product.product_data.ID} from queue",
                }
            )
            yield events.AllOf(resource.env, product_retrieval_events)
            product.update_location(self.resource)

            transport_state: state.State = yield self.env.process(
                resource.wait_for_free_process(process)
            )
            logger.debug(
                {
                    "ID": "controller",
                    "sim_time": self.env.now,
                    "resource": self.resource.data.ID,
                    "event": f"Starting transport of {product.product_data.ID}",
                }
            )
            yield self.env.process(
                self.run_transport(
                    transport_state, product, route_to_target, empty_transport=False
                )
            )

            product_put_events = self.put_product_to_input_queue(target_queue, product)
            logger.debug(
                {
                    "ID": "controller",
                    "sim_time": self.env.now,
                    "resource": self.resource.data.ID,
                    "event": f"Waiting to put product {product.product_data.ID} to queue",
                }
            )
            yield events.AllOf(resource.env, product_put_events)
            product.update_location(target)

            # if not resource.got_free.triggered:
            #     resource.got_free.succeed()
            product.product_router.mark_finished_request(process_request)
            logger.debug(
                {
                    "ID": "controller",
                    "sim_time": self.env.now,
                    "resource": self.resource.data.ID,
                    "event": f"Finished transport of {product.product_data.ID}",
                }
            )

    def run_transport(
        self,
        transport_state: state.State,
        product: product.Product,
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
            logger.debug(
                {
                    "ID": "controller",
                    "sim_time": self.env.now,
                    "resource": self.resource.data.ID,
                    "event": f"Moving from {location.data.ID} to {next_location.data.ID}",
                    "empty_transport": True,
                    "initial_transport_step": initial_transport_step,
                    "last_transport_step": last_transport_step,
                }
            )
            yield self.env.process(
                self.run_process(
                    transport_state,
                    product,
                    target=next_location,
                    empty_transport=empty_transport,
                    initial_transport_step=initial_transport_step,
                    last_transport_step=last_transport_step,
                )
            )
            logger.debug(
                {
                    "ID": "controller",
                    "sim_time": self.env.now,
                    "resource": self.resource.data.ID,
                    "event": f"Arrived at {next_location.data.ID}",
                    "empty_transport": True,
                    "initial_transport_step": initial_transport_step,
                    "last_transport_step": last_transport_step,
                }
            )
            transport_state.process = None

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
        if not last_transport_step or not isinstance(
            target, (resources.Resource, store.Store)
        ):
            return target.get_location()
        if empty_transport:
            return target.get_output_location()
        else:
            return target.get_input_location()

    def run_process(
        self,
        input_state: state.TransportState,
        product: product.Product,
        target: product.Locatable,
        empty_transport: bool,
        initial_transport_step: bool,
        last_transport_step: bool,
    ):
        """
        Run the process of a product. The process is started and the product is logged.

        Args:
            input_state (state.State): The transport state of the process.
            product (product.Product): The product that is transported.
            target (product.Locatable): The target of the transport.
            empty_transport (bool): If the transport is empty.
            initial_transport_step (bool): If this is the initial transport step.
            last_transport_step (bool): If this is the last transport step.
        """
        input_state.prepare_for_run()
        if not hasattr(product, "product_info"):
            input_state.state_info.log_auxiliary(product, state.StateTypeEnum.transport)
        else:
            input_state.state_info.log_product(product, state.StateTypeEnum.transport)

        origin = self.resource.current_locatable
        input_state.state_info.log_transport(
            origin,
            target,
            state.StateTypeEnum.transport,
            empty_transport=empty_transport,
        )
        if not hasattr(product, "product_info"):
            product.auxiliary_info.log_start_process(
                input_state.resource,
                product,
                self.env.now,
                state.StateTypeEnum.transport,
            )
        else:
            product.product_info.log_start_process(
                input_state.resource,
                product,
                self.env.now,
                state.StateTypeEnum.transport,
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
                    f"Route to origin for transport of {process_request.product.product_data.ID} could not be found. Router selected a transport resource that can perform the transport but does not reach the origin."
                )
            return route_to_origin
        else:
            return [self.resource.current_locatable, process_request.get_origin()]


class MoveProcessHandler:
    # TODO: implement this class that only performs a move of the transport resource, without adjusting the queues -> TransportProcessHandler can inherit from it
    pass


class AuxiliaryProcessHandler:
    # TODO: this function just waits for the auxiliaried process to be over
    pass


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
    if not isinstance(locatable, (resources.Resource, store.Store)):
        return locatable.get_location()
    if mode == "target":
        return locatable.get_input_location()
    else:
        return locatable.get_output_location()


def SPT_transport_control_policy(
    requests: List[request_module.TransportResquest],
) -> None:
    """
    Sort the requests according to the SPT principle (shortest process time first).

    Args:
        requests (List[request.TransportResquest]): The list of requests.
    """
    requests.sort(
        key=lambda x: x.process.get_expected_process_time(
            get_location(x.origin, "origin"), get_location(x.target, "target")
        )
    )


def nearest_origin_and_longest_target_queues_transport_control_policy(
    requests: List[request_module.TransportResquest],
) -> None:
    """
    Sort the requests according to nearest origin without considering the target location.
    Second order sorting by descending length of the target output queues, to prefer targets where a product can be picked up.
    Args:
        requests (List[request.TransportResquest]): The list of requests.
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
    requests: List[request_module.TransportResquest],
) -> None:
    """
    Sort the requests according to nearest origin without considering the target location.
    Second order sorting by ascending length of the target input queue so that resources with empty input queues get material to process.

    Args:
        requests (List[request.TransportResquest]): The list of requests.
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

    resource: resources.Resource = Field(init=False, default=None)

    def get_batch_size(self, resource: resources.Resource) -> int:
        """
        Get the batch size for the given resource.

        Args:
            resource (resources.Resource): The resource to get the batch size for.

        Returns:
            int: The batch size of the resource.
        """
        if isinstance(resource, resources.Resource):
            return resource.data.batch_size
        else:
            raise ValueError("Resource is not a ProductionResource")

    def get_next_product_for_process(
        self, resource: resources.Resource, process_request: request_module.Request
    ) -> List[events.Event]:
        """
        Get the next batch of products for a process. The products are removed (get) from the input queues of the resource.

        Args:
            resource (resources.Resource): The resource to take the products from.
            process_request (request_module.Request): The request that is requesting the products.

        Returns:
            List[events.Event]: The events that are triggered when the products are taken from the queue.
        """
        events = []
        if isinstance(resource, resources.ProductionResource):
            batch_size = self.get_batch_size(resource)
            internal_input_queues = [
                queue
                for queue in resource.input_queues
                if not isinstance(queue, store.Store)
            ]
            for queue in internal_input_queues:
                while len(events) < batch_size:
                    event = queue.get(
                        filter=lambda item: item.product_type
                        == process_request.get_product().product_data.product_type
                    )
                    if not event:
                        break
                    events.append(event)
            if not events:
                raise ValueError(
                    "No products available in the queue to fulfill the batch size requirement"
                )
            return events
        else:
            raise ValueError("Resource is not a ProductionResource")

    def put_product_to_output_queue(
        self, resource: resources.Resource, products: List[product.Product]
    ) -> List[events.Event]:
        """
        Place a batch of products into the output queue of the resource.

        Args:
            resource (resources.Resource): The resource to place the products to.
            products (List[product.Product]): The products to be placed.

        Returns:
            List[events.Event]: The events that are triggered when the products are placed in the queue.
        """
        events = []
        if isinstance(resource, resources.ProductionResource):
            for product in products:
                internal_output_queues = [
                    queue
                    for queue in resource.output_queues
                    if not isinstance(queue, store.Store)
                ]
                queue_for_product = random.choice(internal_output_queues)
                events.append(queue_for_product.put(product.product_data))
                logger.debug(
                    {
                        "ID": "controller: put_product_to_output_queue",
                        "sim_time": self.env.now,
                        "queue": queue_for_product.data.ID,
                        "event": f"Putting product {product.product_data.ID} into output queue",
                    }
                )
        else:
            raise ValueError("Resource is not a ProductionResource")

        return events

    def wait_for_free_process(
        self, resource: resources.Resource, process: process.Process
    ) -> Generator[List[state.State], None, None]:
        """
        Wait for free processes of a resource.

        Args:
            resource (resources.Resource): The resource.
            process (process.Process): The process.

        Returns:
            Generator: The generator yields when processes are free.

        Yields:
            Generator: The generator yields lists of free states.
        """
        possible_states = resource.get_processes(process)
        while True:
            free_states = resource.get_free_processes(process)
            if free_states:
                return free_states
            logger.debug(
                {
                    "ID": "controller",
                    "sim_time": self.env.now,
                    "resource": resource.data.ID,
                    "event": "Waiting for free process",
                }
            )
            yield events.AnyOf(
                self.env,
                [
                    state.process
                    for state in possible_states
                    if state.process is not None and state.process.is_alive
                ],
            )

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
            batch_size = self.get_batch_size(self.resource)
            logger.debug(
                {
                    "ID": "controller",
                    "sim_time": self.env.now,
                    "resource": self.resource.data.ID,
                    "event": "Waiting for request or process to finish",
                }
            )
            yield events.AnyOf(
                env=self.env, events=self.running_processes + [self.requested]
            )
            if self.requested.triggered:
                self.requested = events.Event(self.env)
            for process in self.running_processes:
                if not process.is_alive:
                    self.running_processes.remove(process)
            if self.resource.full or (
                len(self.requests) < batch_size and len(self.requests) > 0
            ):
                logger.debug(
                    {
                        "ID": "controller",
                        "sim_time": self.env.now,
                        "resource": self.resource.data.ID,
                        "event": f"Not enough requests ({len(self.requests)}) or resource full ({self.resource.full})",
                    }
                )
                continue
            self.control_policy(self.requests)
            self.reserved_requests_count += 1
            running_process = self.env.process(self.start_process())
            self.running_processes.append(running_process)
            if not self.resource.full:
                logger.debug(
                    {
                        "ID": "controller",
                        "sim_time": self.env.now,
                        "resource": self.resource.data.ID,
                        "event": "Triggered requested event after process",
                    }
                )
                self.requested.succeed()

    def start_process(self) -> Generator:
        """
        Start the next process with the following logic:

        1. Setup the resource for the process.
        2. Wait until the resource is free for the process.
        3. Retrieve the products for the batch from the queue.
        4. Run the process and wait until finished.
        5. Place the product in the output queue.

        Yields:
            Generator: The generator yields when the process is finished.
        """
        batch_size = self.get_batch_size(self.resource)
        logger.debug(
            {
                "ID": "controller",
                "sim_time": self.env.now,
                "resource": self.resource.data.ID,
                "event": f"Starting batch process",
            }
        )
        yield self.env.timeout(0)
        process_request = self.requests.pop(0)
        self.reserved_requests_count -= 1
        resource = process_request.get_resource()
        process = process_request.get_process()
        product = process_request.get_product()
        products = []
        production_states = []
        logger.debug(
            {
                "ID": "controller",
                "sim_time": self.env.now,
                "resource": self.resource.data.ID,
                "event": f"Starting setup for process for {product.product_data.ID} with batch size {batch_size}",
            }
        )

        yield self.env.process(resource.setup(process))
        with resource.request() as req:
            yield req
            product_retrieval_events = self.get_next_product_for_process(
                resource, process_request
            )
            logger.debug(
                {
                    "ID": "controller",
                    "sim_time": self.env.now,
                    "resource": self.resource.data.ID,
                    "event": f"Waiting to retrieve products for batch from queue",
                }
            )
            product_data_list = yield events.AllOf(
                resource.env, product_retrieval_events
            )

            for product_data in product_data_list.values():
                simulation_product = product.product_router.product_factory.get_product(
                    product_data.ID
                )
                products.append(simulation_product)

            for simulation_product in products:
                production_states: state.State = yield self.env.process(
                    self.wait_for_free_process(resource, process)
                )

            logger.debug(
                {
                    "ID": "controller",
                    "sim_time": self.env.now,
                    "resource": self.resource.data.ID,
                    "event": f"Starting batch process",
                }
            )
            yield self.env.process(
                self.run_process(production_states, products, process)
            )
            for state in production_states:
                state.process = None

            product_put_events = self.put_product_to_output_queue(resource, products)
            logger.debug(
                {
                    "ID": "controller",
                    "sim_time": self.env.now,
                    "resource": self.resource.data.ID,
                    "event": f"Waiting to put products to queue",
                }
            )
            yield events.AllOf(resource.env, product_put_events)
            resource.adjust_pending_put_of_output_queues(
                batch_size
            )  # output queues do not get reserved, so the pending put has to be adjusted manually

            for product in products:
                for next_product in [product]:
                    # FIXME: resolve as mark process as finished in router as
                    if not resource.got_free.triggered:
                        resource.got_free.succeed()
                    next_product.finished_process.succeed()
                logger.debug(
                    {
                        "ID": "controller",
                        "sim_time": self.env.now,
                        "resource": self.resource.data.ID,
                        "event": f"Finished batch process",
                    }
                )

    def run_process(
        self,
        input_states: List[state.State],
        products: List[product.Product],
        process: process.Process,
    ):
        """
        Run the process of a product. The process is started and the product is logged.

        Args:
            input_state (state.State): The production state of the process.
            target_product (product.Product): The product that is processed.
        """
        states = []
        random_input_state = random.choice(input_states)
        process_time_for_batch = random_input_state.time_model.get_next_time()

        for product, input_state in zip(products, input_states):
            input_state.prepare_for_run()
            input_state.state_info.log_product(product, state.StateTypeEnum.production)
            product.product_info.log_start_process(
                self.resource,
                product,
                self.env.now,
                state.StateTypeEnum.production,
            )
            input_state.process = self.env.process(
                input_state.process_state(process_time_for_batch)
            )
            states.append(input_state.process)

            self.handle_rework_required(product, process)

        yield events.AllOf(self.env, states)

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
        failure_rate = process.process_data.failure_rate
        if not failure_rate or failure_rate == 0:
            return
        rework_needed = np.random.choice(
            [True, False], p=[failure_rate, 1 - failure_rate]
        )
        if not rework_needed:
            return
        logger.debug(
            {
                "ID": "controller",
                "sim_time": self.env.now,
                "resource": self.resource.data.ID,
                "event": f"Rework needed for {product.product_data.ID}",
            }
        )
        product.add_needed_rework(process)


from prodsys.simulation import resources, state, route_finder, sim, store
from prodsys.simulation import request as request_module
from prodsys.simulation.process import LinkTransportProcess
