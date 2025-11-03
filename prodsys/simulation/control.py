from __future__ import annotations

from collections.abc import Callable
from typing import List, Generator, TYPE_CHECKING, Literal, Optional, Union

from simpy import events
import simpy
import logging

from prodsys.models.port_data import StoreData
from prodsys.models.resource_data import ResourceData
from prodsys.models import port_data


from prodsys.simulation import (
    sim,
    process,
)
from prodsys.simulation.process_handlers.production_process_handler import ProductionProcessHandler
from prodsys.simulation.process_handlers.transport_process_handler import TransportProcessHandler
from prodsys.simulation.process_handlers.dependency_process_handler import DependencyProcessHandler
from prodsys.simulation.process_handlers.system_process_model_process_handler import SystemProcessModelHandler
from prodsys.simulation.process_handlers.resource_process_model_process_handler import ResourceProcessModelHandler
from prodsys.models.resource_data import ResourceType
from prodsys.simulation import request as request_module

if TYPE_CHECKING:
    from prodsys.simulation import (
        process,
        resources,
    )
    from prodsys.simulation import request as request_module
    from prodsys.control import sequencing_control_env
    from prodsys.simulation.locatable import Locatable
    from prodsys.simulation.lot_handler import LotHandler

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
        lot_handler: LotHandler,
    ) -> None:
        self.control_policy = control_policy
        self.env = env
        self.lot_handler = lot_handler
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

    def free_up_queue_check(self) -> Generator:
        # generator that runs until one output queue is free again, getting to know it from a get from the output queue
        output_queues = [port for port in self.resource.ports if port.data.interface_type == port_data.PortInterfaceType.OUTPUT]
        queue_get_events = [queue.on_space for queue in output_queues]
        yield simpy.AnyOf(self.env, queue_get_events)
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
            logger.debug(f"[CONTROL LOOP] Time={self.env.now:.2f} | Resource={self.resource.data.ID} | Requests={len(self.requests)} | Full={self.resource.full} | In Setup={self.resource.in_setup} | Bound={self.resource.bound}")
            
            # Detailed logging for blocking conditions
            if not self.requests:
                logger.debug(f"[CONTROL BLOCKED] Time={self.env.now:.2f} | Resource={self.resource.data.ID} | Reason=NO_REQUESTS")
            elif self.resource.full:
                logger.debug(f"[CONTROL BLOCKED] Time={self.env.now:.2f} | Resource={self.resource.data.ID} | Reason=FULL | Free Capacity={self.resource.get_free_capacity()} | Running Processes={self.num_running_processes} | Reserved Count={self.reserved_requests_count} | Capacity Current Setup={self.resource.capacity_current_setup} | Capacity={self.resource.capacity}")
                for i, req in enumerate(self.requests):
                    logger.debug(f"[CONTROL BLOCKED] Time={self.env.now:.2f} | Resource={self.resource.data.ID} | Request[{i}]={req.request_type} | Entity={req.entity.data.ID if req.entity else 'None'} | Origin={req.origin_queue.data.ID if req.origin_queue else 'None'} | Target={req.target_queue.data.ID if req.target_queue else 'None'}")
            elif self.resource.in_setup:
                logger.debug(f"[CONTROL BLOCKED] Time={self.env.now:.2f} | Resource={self.resource.data.ID} | Reason=IN_SETUP | Setup={self.resource.reserved_setup}")
            elif self.resource.bound:
                logger.debug(f"[CONTROL BLOCKED] Time={self.env.now:.2f} | Resource={self.resource.data.ID} | Reason=BOUND | Bound To={self.resource.bound_to}")
            
            if (
                self.resource.full
                or self.resource.in_setup
                or self.resource.bound
                or not self.requests
            ):
                continue

            self.control_policy(self.requests)
            def is_request_feasible(request: request_module.Request) -> bool:
                # Check transport requests for target queue availability
                if request.request_type == request_module.RequestType.TRANSPORT:
                    if request.target_queue.is_full:
                        logger.debug(f"[CONTROL FEASIBILITY] Time={self.env.now:.2f} | Transport | Target={request.target_queue.data.ID} | Full=True | NOT FEASIBLE")
                        return False
                # Check production requests for INPUT_OUTPUT queue deadlock prevention
                elif request.request_type in (request_module.RequestType.PRODUCTION, request_module.RequestType.PROCESS_MODEL):
                    # For INPUT_OUTPUT queues, check if output space is available
                    # If origin == target (same INPUT_OUTPUT queue), check if item is in queue
                    if request.origin_queue == request.target_queue:
                        # If item is in queue, we can remove it then put it back
                        item_id = request.entity.data.ID
                        if item_id in request.origin_queue.items:
                            # Item is in queue - feasible (we'll remove then put back)
                            logger.debug(f"[CONTROL FEASIBILITY] Time={self.env.now:.2f} | Production INPUT_OUTPUT | Queue={request.origin_queue.data.ID} | Item={item_id} in queue | FEASIBLE")
                            return True
                        else:
                            raise ValueError(f"Item {item_id} not in queue {request.origin_queue.data.ID}")
                    else:
                        # Separate queues - first check if item is in origin queue
                        item_id = request.entity.data.ID
                        is_in_origin = item_id in request.origin_queue.items
                        if not is_in_origin:
                            raise ValueError(f"Item {item_id} not in origin queue {request.origin_queue.data.ID}")
                        # Item is in origin queue - check if target has space
                        if request.target_queue.is_full:
                            logger.debug(f"[CONTROL FEASIBILITY] Time={self.env.now:.2f} | Production separate queues | Origin={request.origin_queue.data.ID if request.origin_queue else 'None'} | Target={request.target_queue.data.ID} | Item={item_id} | In Origin=True | Target Full=True | NOT FEASIBLE")
                            return False
                        logger.debug(f"[CONTROL FEASIBILITY] Time={self.env.now:.2f} | Production separate queues | Origin={request.origin_queue.data.ID if request.origin_queue else 'None'} | Target={request.target_queue.data.ID} | Item={item_id} | In Origin=True | FEASIBLE")
                return True

            def get_feasible_request(requests: List[request_module.Request]) -> request_module.Request:
                for i, request in enumerate(requests):
                    logger.debug(f"[CONTROL FEASIBILITY CHECK] Time={self.env.now:.2f} | Resource={self.resource.data.ID} | Request[{i}]={request.request_type} | Entity={request.entity.data.ID if request.entity else 'None'} | Origin={request.origin_queue.data.ID if request.origin_queue else 'None'} | Target={request.target_queue.data.ID if request.target_queue else 'None'}")
                    if is_request_feasible(request):
                        logger.debug(f"[CONTROL FEASIBLE] Time={self.env.now:.2f} | Resource={self.resource.data.ID} | Request={request.request_type} | Entity={request.entity.data.ID if request.entity else 'None'}")
                        self.requests.remove(request)
                        return request
                    else:
                        logger.debug(f"[CONTROL NOT FEASIBLE] Time={self.env.now:.2f} | Resource={self.resource.data.ID} | Request[{i}]={request.request_type} | Entity={request.entity.data.ID if request.entity else 'None'} | Reason=CHECK_FAILED")
                    # If request becomes infeasible (queue full), reroute it back to router
                    # This allows it to be retried later when space becomes available
                    # Only reroute transport requests - production requests should have been validated
                    # before routing and if item is in INPUT_OUTPUT queue, it should be processable
                    if request.request_type == request_module.RequestType.TRANSPORT:
                        logger.debug(f"[CONTROL REROUTE] Time={self.env.now:.2f} | Resource={self.resource.data.ID} | Rerouting transport request for Entity={request.entity.data.ID if request.entity else 'None'}")
                        self.requests.remove(request)
                        request.requesting_item.router.request_handler.reroute_request(request)
                        # Trigger router to check for new routing opportunities
                        if not request.requesting_item.router.got_requested.triggered:
                            request.requesting_item.router.got_requested.succeed()
                logger.debug(f"[CONTROL NO FEASIBLE] Time={self.env.now:.2f} | Resource={self.resource.data.ID} | No feasible request found from {len(requests)} requests")
                return None
            
            selected_request = get_feasible_request(self.requests)
            if not selected_request:
                logger.debug(f"[CONTROL] Time={self.env.now:.2f} | Resource={self.resource.data.ID} | No feasible request found | Remaining requests={len(self.requests)}")
                # Log all remaining requests for debugging
                for i, req in enumerate(self.requests):
                    logger.debug(f"[CONTROL REMAINING REQUEST] Time={self.env.now:.2f} | Resource={self.resource.data.ID} | Request[{i}]={req.request_type} | Entity={req.entity.data.ID if req.entity else 'None'} | Origin Queue Full={req.origin_queue.is_full if req.origin_queue else 'N/A'} | Target Queue Full={req.target_queue.is_full if req.target_queue else 'N/A'} | Entity In Origin={req.entity.data.ID in req.origin_queue.items if req.origin_queue and req.entity else 'N/A'}")
                # If there are requests waiting on full output queues, wait for space
                self.env.process(self.free_up_queue_check())
                continue
            
            logger.debug(f"[CONTROL SELECTED] Time={self.env.now:.2f} | Resource={self.resource.data.ID} | Request={selected_request.request_type} | Origin={selected_request.origin_queue.data.ID if selected_request.origin_queue else 'None'} | Target={selected_request.target_queue.data.ID if selected_request.target_queue else 'None'}")
                
            if self._should_form_lot(selected_request):
                lot_request = self._form_lot(selected_request)
                if not lot_request:
                    # Can't form lot yet - move to end and try next request
                    self.requests.append(selected_request)
                    continue
                selected_request = lot_request
                
            # Reserve output queue for transport requests (production requests reserve in their handler)
            if selected_request.request_type == request_module.RequestType.TRANSPORT:
                self.reserve_output_queue(selected_request)
            
            self.reserved_requests_count += selected_request.capacity_required
            # For dependency requests, immediately bind the resource to block other processes
            if selected_request.request_type in (request_module.RequestType.PROCESS_DEPENDENCY, request_module.RequestType.RESOURCE_DEPENDENCY):
                self.resource.bind_to_dependant(selected_request.requesting_item)
            self.resource.update_full()
            process_handler = get_requets_handler(selected_request)
            self.env.process(process_handler.handle_request(selected_request))
            if not self.resource.full and self.requests:
                self.state_changed.succeed()

    def reserve_output_queue(self, process_request: request_module.Request) -> Generator:
        """
        Reserve the output queue for the process.

        Args:
            process_request (request_module.Request): The request to reserve the output queue for.
        """
        if process_request.request_type in (request_module.RequestType.PROCESS_DEPENDENCY, request_module.RequestType.RESOURCE_DEPENDENCY):
            return
        for entity in process_request.get_atomic_entities():
            if process_request.target_queue.is_full:
                raise ValueError(f"Target queue {process_request.target_queue.data.ID} is full for request {process_request.completed}")
            process_request.target_queue.reserve()

    def _should_form_lot(self, process_request: request_module.Request) -> bool:
        return self.lot_handler.lot_required(process_request)

    def _form_lot(self, process_request: request_module.Request) -> Optional[request_module.Request]:
        if not self.lot_handler.is_lot_feasible(process_request):
            return None
        lot_requests = self.lot_handler.get_lot_request(process_request)
        return lot_requests

    def mark_started_process(self, num_processes: int = 1) -> None:
        """
        Mark the process as started.

        Args:
            num_processes (int): The number of processes that are being started.
        """
        self.reserved_requests_count -= num_processes
        self.num_running_processes += num_processes

    def mark_finished_process(self, num_processes: int = 1) -> None:
        """
        Mark the process as finished.

        Args:
            process_request (Request): The request that is being processed.
        """
        self.num_running_processes -= num_processes
        self.resource.update_full()
        if not self.state_changed.triggered:
            self.state_changed.succeed()


def get_requets_handler(
    request: request_module.Request,
) -> Union[ProductionProcessHandler, TransportProcessHandler, DependencyProcessHandler, SystemProcessModelHandler, ResourceProcessModelHandler]:
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
    elif request.request_type == request_module.RequestType.PROCESS_MODEL:
        # Route to SystemProcessModelHandler for system resources, ResourceProcessModelHandler for regular resources
        if request.resource.data.resource_type == ResourceType.SYSTEM:
            return SystemProcessModelHandler(request.requesting_item.env)
        else:
            return ResourceProcessModelHandler(request.requesting_item.env)
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

            # TODO: Adjust BatchController to start all processes at once and stop otherwise!
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
                and req.get_entity().data.type == selected_request.get_entity().data.type
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


def scheduled_control_policy(
    product_sequence_indices: dict[str, str], fallback_policy: Callable, requests: List[request_module.Request]
) -> None:
    """
    A control policy that sequences products based on their scheduled index in the sequence. 
    If the request contains any product which is not in the schedule, the fallback policy is also 
    considered if it would be processed next. 

    Args:
        product_sequence_indices (dict[str, str]): indices in the scheduled sequence of the product ids
        fallback_policy (Callable): fallback control policy
        requests (List[request_module.Request]): list of requests to sequence
    """
    non_scheduled_products = []
    request_sequence_indices = {}
    for request_instance in requests:
        product_id = request_instance.product.product_data.ID
        if product_id not in product_sequence_indices:
            non_scheduled_products.append(request_instance)
            continue
        request_priority = product_sequence_indices[product_id]
        request_sequence_indices[request_priority] = request_instance

    if non_scheduled_products:
        request_list_copy = requests[::]
        fallback_policy(request_list_copy)
        if request_list_copy[0].product.product_data.ID not in product_sequence_indices:
            fallback_policy(requests)
            return

    sorted_indices = sorted(request_sequence_indices.keys())
    requests.clear()
    requests.extend([request_sequence_indices[index] for index in sorted_indices])


# TODO: add a Controller which starts processes with delays...

