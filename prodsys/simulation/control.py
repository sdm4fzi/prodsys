from __future__ import annotations

from collections.abc import Callable
from typing import List, Generator, TYPE_CHECKING, Literal, Optional, Union

from simpy import events
import simpy
import logging

from prodsys.models.port_data import StoreData
from prodsys.models.resource_data import ResourceData
from prodsys.models import port_data
from prodsys.simulation.process_handlers.disassembly_process_handler import DisassemblyProcessHandler
from prodsys.simulation.request import Request
from prodsys.simulation.entities.entity import Entity
from prodsys.models.dependency_data import DependencyType
from prodsys.simulation import (
    sim,
    process,
)
from prodsys.simulation.process_handlers.production_process_handler import ProductionProcessHandler
from prodsys.simulation.process_handlers.transport_process_handler import TransportProcessHandler, ConveyorTransportProcessHandler
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
            print("state changed trigger from queue check")
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

            def get_requests_with_available_dependencies(requests: List[request_module.Request]) -> List[request_module.Request]:
                requests_with_available_dependencies = []
                for request in requests:
                    if request.required_dependencies:
                        primitive_dependencies = [dependency for dependency in request.required_dependencies if dependency.data.dependency_type == DependencyType.ASSEMBLY]
                        if primitive_dependencies:
                            router = request.requesting_item.router
                            # Check if all required primitives are available
                            all_primitives_available = True
                            for dependency in primitive_dependencies:
                                required_primitive = dependency.required_entity
                                if required_primitive is None:
                                    all_primitives_available = False
                                    break
                                # Get the type from the required_primitive (can be Product or Primitive)
                                primitive_type = required_primitive.data.type
                                free_primitives = router.free_primitives_by_type.get(primitive_type, [])
                                # Check if there are actually free primitives (list is not empty)
                                if not free_primitives or len(free_primitives) == 0:
                                    all_primitives_available = False
                                    break
                            if not all_primitives_available:
                                continue
                    requests_with_available_dependencies.append(request)
                return requests_with_available_dependencies
            possible_requests = get_requests_with_available_dependencies(self.requests)
            if not possible_requests:
                continue
            self.control_policy(possible_requests)
            def is_request_feasible(request: request_module.Request) -> bool:
                # Check transport requests for target queue availability

                if request.request_type == request_module.RequestType.TRANSPORT:
                    if request.target_queue.is_full:
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
                            return False
                return True

            def get_feasible_request(requests: List[request_module.Request]) -> request_module.Request:
                for i, request in enumerate(requests):
                    if is_request_feasible(request):
                        self.requests.remove(request)
                        return request # If request becomes infeasible (queue full), reroute it back to router
                    # This allows it to be retried later when space becomes available
                    # Only reroute transport requests - production requests should have been validated
                    # before routing and if item is in INPUT_OUTPUT queue, it should be processable
                    if request.request_type == request_module.RequestType.TRANSPORT:
                        self.requests.remove(request)
                        request.requesting_item.router.request_handler.reroute_request(request)
                        # Trigger router to check for new routing opportunities
                        if not request.requesting_item.router.got_requested.triggered:
                            request.requesting_item.router.got_requested.succeed()
                return None
            
            selected_request = get_feasible_request(possible_requests)
            if not selected_request:
                # If there are requests waiting on full output queues, wait for space
                self.env.process(self.free_up_queue_check())
                continue
                            
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
            
    def mark_finished_process_no_sink_transport(self, process_request: Request, entity: Entity) -> None:
        """
        Mark the process as finished, but no transport to sink required.

        Args:
            process_request (Request): The request that is being processed.
        """
        
        self.num_running_processes -= process_request.capacity_required
        self.resource.update_full()
        entity.no_transport_to_sink = True
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
        and any(dependency.data.dependency_type == DependencyType.DISASSEMBLY for dependency in request.required_dependencies)
    ):
        return DisassemblyProcessHandler(request.requesting_item.env) 
    elif (
        request.request_type == request_module.RequestType.PRODUCTION
        or request.request_type == request_module.RequestType.REWORK
    ):
        return ProductionProcessHandler(request.requesting_item.env)
    elif request.request_type == request_module.RequestType.TRANSPORT:
        if request.get_resource().can_move:
            return TransportProcessHandler(request.requesting_item.env)
        else:
            return ConveyorTransportProcessHandler(request.requesting_item.env)
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


def get_location(locatable: Locatable) -> List[float]:
    return locatable.get_location()


def SPT_transport_control_policy(
    requests: List[request_module.Request],
) -> None:
    """
    Sort the requests according to the SPT principle (shortest process time first).

    Args:
        requests (List[request.Request]): The list of requests.
    """
    # for request in requests:
    #     if request.origin_queue is None or request.target_queue is None:
    #         raise ValueError(f"Origin queue or target queue is None for request {request.completed}")

    def get_expected_time(request: request_module.Request) -> float:
        if request.request_type == request_module.RequestType.RESOURCE_DEPENDENCY:
            #  TODO: calculate time based on dependency process time
            return 0.1
        
        return request.process.get_expected_process_time(
            get_location(request.origin_queue), get_location(request.target_queue)
        )
    requests.sort(
        key=get_expected_time
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
                get_location(x.resource), get_location(x.origin_queue)
            ),
            -x.target_queue.free_space(),
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
                get_location(x.resource), get_location(x.origin_queue)
            ),
            x.target_queue.free_space(),
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
        product_id = request_instance.entity.data.ID
        if product_id not in product_sequence_indices:
            non_scheduled_products.append(request_instance)
            continue
        request_priority = product_sequence_indices[product_id]
        request_sequence_indices[request_priority] = request_instance

    if non_scheduled_products:
        request_list_copy = requests[::]
        fallback_policy(request_list_copy)
        if request_list_copy[0].entity.data.ID not in product_sequence_indices:
            fallback_policy(requests)
            return

    sorted_indices = sorted(request_sequence_indices.keys())
    requests.clear()
    requests.extend([request_sequence_indices[index] for index in sorted_indices])


# TODO: add a Controller which starts processes with delays...

