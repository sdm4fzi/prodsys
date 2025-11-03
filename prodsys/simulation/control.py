from __future__ import annotations

from collections.abc import Callable
from typing import List, Generator, TYPE_CHECKING, Literal, Optional, Union, Any

from simpy import events
import logging

from prodsys.models.port_data import StoreData
from prodsys.models.resource_data import ResourceData

from prodsys.simulation import (
    sim,
    process,
)
from prodsys.simulation.process_handlers.production_process_handler import ProductionProcessHandler
from prodsys.simulation.process_handlers.transport_process_handler import TransportProcessHandler
from prodsys.simulation.process_handlers.dependency_process_handler import DependencyProcessHandler
from prodsys.simulation.process_handlers.process_model_process_handler import ProcessModelHandler
from prodsys.simulation.process_handlers.disassembly_process_handler import DisassemblyProcessHandler
from prodsys.models.product_data import ProductData
from prodsys.simulation.product import Product, Locatable
from prodsys.models.port_data import PortInterfaceType
from prodsys.models.processes_data import ProcessTypeEnum
from prodsys.simulation.process import Process

if TYPE_CHECKING:
    from prodsys.simulation import (
        process,
        resources,
    )
    from prodsys.simulation import request as request_module
    from prodsys.control import sequencing_control_env
    from prodsys.simulation.product import Locatable

logger = logging.getLogger(__name__)


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
            
    def mark_finished_process_no_sink_transport(self, process: Process, product: Product) -> None:
        """
        Mark the process as finished, but no transport to sink required.

        Args:
            process_request (Request): The request that is being processed.
        """
        self.num_running_processes -= 1
        self.resource.update_full()
        disassembly_map = getattr(getattr(process, "data", None), "product_disassembly_dict", None)
        if isinstance(disassembly_map, dict) and disassembly_map:
            product.no_transport = True
        if not self.state_changed.triggered:
            self.state_changed.succeed()        


def get_requets_handler(
    request: request_module.Request,
) -> Union[ProductionProcessHandler, TransportProcessHandler, DependencyProcessHandler, ProcessModelHandler]:
    """
    Get the process handler for a given process.

    Args:
        process (process.PROCESS_UNION): The process to get the handler for.

    Returns:
        Union[ProductionProcessHandler, TransportProcessHandler]: The process handler for the given process.
    """
    
    if (
        request.request_type == request_module.RequestType.PRODUCTION
        and hasattr(request.process, "data")
        and getattr(request.process.data, "product_disassembly_dict", None)
    ):
        return DisassemblyProcessHandler(request.requesting_item.env)  
    elif (
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
    elif request.request_type == request_module.RequestType.PROCESS_MODEL:
        return ProcessModelHandler(request.requesting_item.env)
    else:
        raise ValueError(f"Unknown process type: {type(process)}")




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


def get_location(locatable: Any, mode: Literal["origin", "target"]):
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
