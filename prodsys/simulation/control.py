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
from prodsys.simulation.process_handlers.setup_process_handler import SetupProcessHandler
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
        *,
        strict_schedule_timing: bool = False,
    ) -> None:
        self.control_policy = control_policy
        self.env = env
        self.lot_handler = lot_handler
        self.strict_schedule_timing = strict_schedule_timing
        self.requests: List[request_module.Request] = []
        self.state_changed: events.Event = events.Event(env)
        self.resource: resources.Resource = None
        self.num_running_processes = 0
        self.reserved_requests_count = 0
        # Resource-local schedule (Production/Transport/Dependency/Setup start events).
        # Set by resource_factory when a scheduled control policy is used.
        self.resource_schedule: list = []
        # Schedule indices whose Production/Setup has already been started.
        self.completed_schedule_indices: set[int] = set()
        # Optional: set by Runner so ahead-of-product setups can resolve
        # products / routers for dependency free-checks.
        self.product_factory = None

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
        self.resource.update_idle_logging()
        if not self.state_changed.triggered:
            self.state_changed.succeed()

    def _current_setup_process_id(self) -> str | None:
        if self.resource is None:
            return None
        setup = self.resource.reserved_setup or self.resource.current_setup
        if setup is None:
            return None
        return setup.data.ID

    def _request_matches_current_setup(
        self, process_request: request_module.Request
    ) -> bool:
        current = self._current_setup_process_id()
        if current is None:
            return False
        if process_request.request_type not in (
            request_module.RequestType.PRODUCTION,
            request_module.RequestType.PROCESS_MODEL,
        ):
            return False
        process = process_request.process
        return process is not None and process.data.ID == current

    def _request_needs_changeover(
        self, process_request: request_module.Request
    ) -> bool:
        current = self._current_setup_process_id()
        if current is None:
            return False
        if process_request.request_type == request_module.RequestType.SETUP:
            return True
        if process_request.request_type not in (
            request_module.RequestType.PRODUCTION,
            request_module.RequestType.PROCESS_MODEL,
        ):
            return False
        process = process_request.process
        return process is not None and process.data.ID != current

    def _changeover_cutoff_index(
        self, process_request: request_module.Request
    ) -> int | None:
        """Schedule index at which the changeover starts (Setup or Production)."""
        schedule = self.resource_schedule
        if not schedule:
            return None

        idx = getattr(process_request, "scheduled_control_index", None)
        product = (
            process_request.entity.data.ID if process_request.entity else None
        )

        if process_request.request_type == request_module.RequestType.SETUP:
            if idx is not None:
                return idx
            setup_state_id = getattr(process_request, "setup_state_id", None)
            if product and setup_state_id:
                for i, ev in enumerate(schedule):
                    if i in self.completed_schedule_indices:
                        continue
                    proc = getattr(ev, "process", None) or getattr(ev, "state", None)
                    if (
                        getattr(ev, "state_type", None) == "Setup"
                        and getattr(ev, "product", None) == product
                        and proc == setup_state_id
                    ):
                        return i
            return None

        if idx is not None and product is not None:
            for i in range(idx - 1, -1, -1):
                ev = schedule[i]
                if (
                    getattr(ev, "state_type", None) == "Setup"
                    and getattr(ev, "product", None) == product
                ):
                    return i
            return idx

        process_id = (
            process_request.process.data.ID if process_request.process else None
        )
        if not product:
            return None
        for i, ev in enumerate(schedule):
            if i in self.completed_schedule_indices:
                continue
            if (
                getattr(ev, "state_type", None) == "Setup"
                and getattr(ev, "product", None) == product
            ):
                return i
            proc = getattr(ev, "process", None) or getattr(ev, "state", None)
            if (
                getattr(ev, "state_type", None) == "Production"
                and getattr(ev, "product", None) == product
                and proc == process_id
            ):
                return i
        return None

    def _schedule_prefix_blocks_changeover(
        self, process_request: request_module.Request
    ) -> bool:
        """True if earlier unconsumed schedule Production still needs current_setup."""
        schedule = self.resource_schedule
        if not schedule:
            return False
        current = self._current_setup_process_id()
        if current is None:
            return False
        cutoff = self._changeover_cutoff_index(process_request)
        if cutoff is None:
            return False
        for i in range(cutoff):
            if i in self.completed_schedule_indices:
                continue
            ev = schedule[i]
            if getattr(ev, "state_type", None) != "Production":
                continue
            proc = getattr(ev, "process", None) or getattr(ev, "state", None)
            if proc == current:
                return True
        return False

    def _schedule_next_event_blocks_request(
        self, process_request: request_module.Request
    ) -> bool:
        """True if the next unconsumed schedule event is for another product.

        Blocks both foreign changeovers and same-setup affinity jumps that would
        start work ahead of the plan (e.g. product3_8 p2 before S2 for
        product3_9) and steal ResourceDependency workers.
        """
        schedule = self.resource_schedule
        if not schedule:
            return False
        product = (
            process_request.entity.data.ID if process_request.entity else None
        )
        if not product:
            return False
        for i, ev in enumerate(schedule):
            if i in self.completed_schedule_indices:
                continue
            st = getattr(ev, "state_type", None)
            if st not in ("Setup", "Production"):
                continue
            return getattr(ev, "product", None) != product
        return False

    def changeover_blocked(
        self,
        process_request: request_module.Request,
        feasible_requests: List[request_module.Request] | None = None,
        is_feasible: Callable[[request_module.Request], bool] | None = None,
    ) -> bool:
        """True if affinity or schedule-prefix should defer a changeover."""
        if not self._request_needs_changeover(process_request):
            return False
        if feasible_requests is not None and is_feasible is not None:
            for req in feasible_requests:
                if req is process_request:
                    continue
                if not is_feasible(req) or not self._request_matches_current_setup(req):
                    continue
                # Same-setup work that itself jumps the schedule must not block
                # the scheduled changeover (e.g. product3_8 p2 vs S2 product3_9).
                if self._schedule_next_event_blocks_request(req):
                    continue
                return True
        if self._schedule_prefix_blocks_changeover(process_request):
            return True
        return self._schedule_next_event_blocks_request(process_request)

    def _matching_setup_state_id(
        self, process_request: request_module.Request
    ) -> str | None:
        """Setup-state ID for changing from current/reserved setup to target process."""
        resource = getattr(process_request, "resource", None) or self.resource
        process = getattr(process_request, "process", None)
        if resource is None or process is None:
            return None
        setup_to_compare = resource.reserved_setup or resource.current_setup
        if setup_to_compare is None:
            return None
        if setup_to_compare.data.ID == process.data.ID:
            return None
        for setup_state in getattr(resource, "setup_states", None) or ():
            if (
                setup_state.data.origin_setup == setup_to_compare.data.ID
                and setup_state.data.target_setup == process.data.ID
            ):
                return setup_state.data.ID
        return None

    def should_allow_opportunistic_setup(
        self, process_request: request_module.Request
    ) -> bool:
        """Gate for opportunistic ``resource.setup()`` in production handlers."""
        if not self._request_needs_changeover(process_request):
            return True
        if not self.resource_schedule:
            return True
        # With a resource schedule, changeovers go through SETUP requests so
        # planned start times are honored. Soft switches (no setup_states)
        # still need ``resource.setup()`` or production stalls forever.
        if self.resource_schedule:
            if self._matching_setup_state_id(process_request):
                return False
            resource = getattr(process_request, "resource", None) or self.resource
            if resource is not None and not getattr(resource, "setup_states", None):
                return True
            return False

    def _planned_setup_event(
        self,
        *,
        product_id: str | None,
        setup_state_id: str | None,
    ) -> tuple[int | None, float | None]:
        """Return ``(schedule_index, planned_start)`` for the next matching Setup."""
        if not self.resource_schedule or not product_id or not setup_state_id:
            return None, None
        for i, ev in enumerate(self.resource_schedule):
            if i in self.completed_schedule_indices:
                continue
            if getattr(ev, "state_type", None) != "Setup":
                continue
            if getattr(ev, "product", None) != product_id:
                continue
            proc = getattr(ev, "process", None) or getattr(ev, "state", None)
            if proc != setup_state_id:
                continue
            return i, float(ev.time) if ev.time is not None else None
        return None, None

    def _mark_schedule_index_started(
        self, process_request: request_module.Request
    ) -> None:
        idx = getattr(process_request, "scheduled_control_index", None)
        if idx is not None:
            self.completed_schedule_indices.add(idx)

    def _find_pending_setup_request(
        self,
        *,
        setup_state_id: str | None = None,
        schedule_index: int | None = None,
        product_id: str | None = None,
    ) -> request_module.Request | None:
        for req in self.requests:
            if req.request_type != request_module.RequestType.SETUP:
                continue
            if (
                setup_state_id is not None
                and getattr(req, "setup_state_id", None) != setup_state_id
            ):
                continue
            if (
                schedule_index is not None
                and getattr(req, "scheduled_control_index", None) != schedule_index
            ):
                continue
            if product_id is not None:
                entity = getattr(req, "entity", None)
                eid = entity.data.ID if entity is not None else None
                if eid is not None and eid != product_id:
                    continue
            return req
        return None

    def _next_unconsumed_prod_or_setup(
        self,
    ) -> tuple[int | None, object | None]:
        """First unconsumed schedule Setup/Production event for this resource."""
        schedule = self.resource_schedule
        if not schedule:
            return None, None
        for i, ev in enumerate(schedule):
            if i in self.completed_schedule_indices:
                continue
            st = getattr(ev, "state_type", None)
            if st in ("Setup", "Production"):
                return i, ev
        return None, None

    def _process_for_id(self, process_id: str | None):
        if process_id is None or self.resource is None:
            return None
        for proc in getattr(self.resource, "processes", None) or ():
            if proc.data.ID == process_id:
                return proc
        return None

    def _setup_state_by_id(self, setup_state_id: str | None):
        if setup_state_id is None or self.resource is None:
            return None
        for setup_state in getattr(self.resource, "setup_states", None) or ():
            if setup_state.data.ID == setup_state_id:
                return setup_state
        return None

    def _lookup_product(self, product_id: str | None):
        if not product_id or self.product_factory is None:
            return None
        products = getattr(self.product_factory, "products", None) or {}
        return products.get(product_id)

    def _create_scheduled_setup_request(
        self,
        schedule_index: int,
        event,
    ) -> request_module.Request | None:
        """Build a SETUP request from a resource-schedule Setup event.

        Used when the plan starts changeover before the product is at the
        machine (setup overlaps inbound transport).
        """
        if self.resource is None:
            return None
        setup_state_id = getattr(event, "process", None) or getattr(
            event, "state", None
        )
        setup_state = self._setup_state_by_id(setup_state_id)
        if setup_state is None:
            return None
        current = self._current_setup_process_id()
        origin = getattr(setup_state.data, "origin_setup", None)
        # Soft match: only refuse when we know we are already on the target
        # (setup would be a no-op) or on a different origin than planned.
        target_id = getattr(setup_state.data, "target_setup", None)
        if current is not None and current == target_id:
            return None
        if current is not None and origin is not None and current != origin:
            return None
        process = self._process_for_id(target_id)
        if process is None:
            return None
        product_id = getattr(event, "product", None)
        product = self._lookup_product(product_id)
        deps = list(getattr(self.resource, "dependencies", None) or [])
        planned_start = float(event.time) if event.time is not None else None
        setup_req = request_module.Request(
            request_type=request_module.RequestType.SETUP,
            process=process,
            resource=self.resource,
            requesting_item=product,
            entity=product,
            setup_state_id=setup_state_id,
            required_dependencies=deps,
            parent_production_request=None,
        )
        setup_req.scheduled_control_index = schedule_index
        setup_req._schedule_product_id = product_id
        setup_req.matched_schedule_event = event
        if planned_start is not None:
            setup_req.scheduled_start_time = planned_start
        return setup_req

    def _maybe_inject_scheduled_setup(self) -> bool:
        """Queue the next planned Setup even if its product has not arrived yet.

        Schedulers often overlap changeover with inbound transport. Without this,
        sim only creates SETUP when production is selectable (product in queue),
        which delays setups and shifts WIP/output.
        """
        if not self.resource_schedule or self.resource is None:
            return False
        if self.resource.in_setup or self.resource.bound:
            return False
        next_idx, next_ev = self._next_unconsumed_prod_or_setup()
        if next_ev is None or getattr(next_ev, "state_type", None) != "Setup":
            return False
        if self._find_pending_setup_request(schedule_index=next_idx) is not None:
            return False
        setup_req = self._create_scheduled_setup_request(next_idx, next_ev)
        if setup_req is None:
            return False
        self.requests.append(setup_req)
        if not self.state_changed.triggered:
            self.state_changed.succeed()
        return True

    def _maybe_create_setup_request(
        self, process_request: request_module.Request
    ) -> request_module.Request | None:
        """Create a SETUP request when production needs a changeover."""
        if not self.resource_schedule:
            return None
        if process_request.request_type not in (
            request_module.RequestType.PRODUCTION,
            request_module.RequestType.PROCESS_MODEL,
        ):
            return None
        if getattr(process_request, "_setup_injected", False):
            return None
        setup_state_id = self._matching_setup_state_id(process_request)
        if setup_state_id is None:
            return None
        resource = process_request.resource
        process = process_request.process
        product_id = (
            process_request.entity.data.ID if process_request.entity is not None else None
        )
        sched_index, planned_start = self._planned_setup_event(
            product_id=product_id,
            setup_state_id=setup_state_id,
        )
        existing = self._find_pending_setup_request(
            setup_state_id=setup_state_id,
            schedule_index=sched_index,
            product_id=product_id,
        )
        if existing is None and sched_index is None:
            existing = self._find_pending_setup_request(
                setup_state_id=setup_state_id,
                product_id=product_id,
            )
        if existing is not None:
            # Ahead-of-product setup already queued — attach production as parent
            # so free-check / attendance gating use the real request deps.
            existing.parent_production_request = process_request
            if process_request.required_dependencies:
                existing.required_dependencies = list(
                    process_request.required_dependencies
                )
            if existing.entity is None and process_request.entity is not None:
                existing.entity = process_request.entity
            if (
                existing.requesting_item is None
                and process_request.requesting_item is not None
            ):
                existing.requesting_item = process_request.requesting_item
            process_request._setup_injected = True
            return existing
        setup_req = request_module.Request(
            request_type=request_module.RequestType.SETUP,
            process=process,
            resource=resource,
            requesting_item=process_request.requesting_item,
            entity=process_request.entity,
            origin_queue=process_request.origin_queue,
            target_queue=process_request.target_queue,
            setup_state_id=setup_state_id,
            # Reuse production deps so setup can gate on worker *availability*
            # (free, not on-site). On-site attendance stays with production.
            required_dependencies=list(process_request.required_dependencies or []),
            parent_production_request=process_request,
        )
        if sched_index is not None:
            setup_req.scheduled_control_index = sched_index
        if planned_start is not None:
            setup_req.scheduled_start_time = planned_start
        return setup_req

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
            self.resource.update_idle_logging()
            if (
                self.resource.full
                or self.resource.in_setup
                or self.resource.bound
            ):
                continue
            # Schedule may start changeover before the product arrives; inject
            # SETUP from the plan even when the request queue is empty.
            if self._maybe_inject_scheduled_setup():
                continue
            if not self.requests:
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
                        # if request.target_queue.is_full:
                        #     return False
                return True

            def get_feasible_request(requests: List[request_module.Request]) -> request_module.Request:
                if not self.resource_schedule:
                    for request in requests:
                        if is_request_feasible(request):
                            return request
                    return None

                # Setup affinity: prefer feasible work that already matches current_setup
                # over any changeover / SETUP request — but never jump ahead of the
                # next unconsumed schedule Setup/Production for another product.
                def schedule_allows(request: request_module.Request) -> bool:
                    if request.request_type not in (
                        request_module.RequestType.PRODUCTION,
                        request_module.RequestType.PROCESS_MODEL,
                        request_module.RequestType.SETUP,
                    ):
                        return True
                    return not self._schedule_next_event_blocks_request(request)

                current = self._current_setup_process_id()
                if current is not None:
                    for request in requests:
                        if not is_request_feasible(request) or not schedule_allows(request):
                            continue
                        if self._request_matches_current_setup(request):
                            return request
                for request in requests:
                    if not is_request_feasible(request) or not schedule_allows(request):
                        continue
                    if self._request_needs_changeover(request) and self.changeover_blocked(
                        request, requests, is_request_feasible
                    ):
                        continue
                    return request
                return None
            
            selected_request = get_feasible_request(possible_requests)
            if not selected_request:
                # No feasible production/transport yet — still try schedule SETUP
                # (product may arrive during/after changeover).
                if self._maybe_inject_scheduled_setup():
                    continue
                # If there are requests waiting on full output queues, wait for space
                # self.env.process(self.free_up_queue_check())
                continue

            # Defer SETUP start when affinity or schedule-prefix still blocks changeover.
            if (
                selected_request.request_type == request_module.RequestType.SETUP
                and self.changeover_blocked(
                    selected_request, possible_requests, is_request_feasible
                )
            ):
                continue

            # Inject SETUP just before production runs so changeovers follow
            # schedule order (same control_policy + fallback) instead of being
            # created when the product first arrives.
            setup_request = self._maybe_create_setup_request(selected_request)
            if setup_request is not None:
                if self.changeover_blocked(
                    setup_request, possible_requests, is_request_feasible
                ):
                    # Same-setup work missing from queue but still planned, or
                    # affinity already preferred another request — wait.
                    continue
                selected_request._setup_injected = True
                # selected_request is still in possible_requests / self.requests
                # until removed below — put production back and let the next
                # loop iteration order setup vs other pending work.
                if selected_request in self.requests:
                    self.requests.remove(selected_request)
                if setup_request not in self.requests:
                    self.requests.append(setup_request)
                self.requests.append(selected_request)
                if not self.state_changed.triggered:
                    self.state_changed.succeed()
                continue
            # Ahead-of-product SETUP already linked via _setup_injected — keep
            # production queued and prefer the pending SETUP next iteration.
            if (
                getattr(selected_request, "_setup_injected", False)
                and selected_request.request_type
                in (
                    request_module.RequestType.PRODUCTION,
                    request_module.RequestType.PROCESS_MODEL,
                )
                and not self._request_matches_current_setup(selected_request)
                and not self.resource.in_setup
            ):
                if selected_request in self.requests:
                    self.requests.remove(selected_request)
                    self.requests.append(selected_request)
                if not self.state_changed.triggered:
                    self.state_changed.succeed()
                continue

            # Production whose SETUP was injected must wait until the resource
            # is on the target process. Otherwise production can start, bind
            # workers via request_dependencies(), and deadlock with the still-
            # pending SETUP free-check.
            if (
                getattr(selected_request, "_setup_injected", False)
                and selected_request.request_type
                in (
                    request_module.RequestType.PRODUCTION,
                    request_module.RequestType.PROCESS_MODEL,
                )
                and not self._request_matches_current_setup(selected_request)
            ):
                setup_pending = next(
                    (
                        r
                        for r in self.requests
                        if r.request_type == request_module.RequestType.SETUP
                        and getattr(r, "parent_production_request", None)
                        is selected_request
                    ),
                    None,
                )
                if setup_pending is not None and is_request_feasible(setup_pending):
                    selected_request = setup_pending
                elif self.resource.in_setup:
                    if selected_request in self.requests:
                        self.requests.remove(selected_request)
                        self.requests.append(selected_request)
                    yield self.state_changed
                    self.state_changed = events.Event(self.env)
                    continue
                else:
                    # SETUP request missing; clear flag and continue with
                    # opportunistic setup inside the production handler.
                    selected_request._setup_injected = False

            scheduled_start = getattr(selected_request, "scheduled_start_time", None)
            # Scheduled changeovers always wait for their planned start — even
            # when general strict_schedule_timing is off. Otherwise setups jump
            # ahead as soon as same-setup work is done (WIP/output diverge).
            if (
                selected_request.request_type == request_module.RequestType.SETUP
                and scheduled_start is not None
                and self.env.now + 1e-9 < scheduled_start
            ):
                wait = scheduled_start - self.env.now
                if wait > 0:
                    yield self.env.timeout(wait)
                if not self.state_changed.triggered:
                    self.state_changed.succeed()
                continue

            if (
                self.strict_schedule_timing
                and scheduled_start is not None
                and selected_request.request_type
                in (
                    request_module.RequestType.PRODUCTION,
                    request_module.RequestType.PROCESS_MODEL,
                    request_module.RequestType.TRANSPORT,
                    request_module.RequestType.PROCESS_DEPENDENCY,
                    request_module.RequestType.RESOURCE_DEPENDENCY,
                    request_module.RequestType.SETUP,
                )
                and self.env.now + 1e-9 < scheduled_start
            ):
                remaining = [r for r in possible_requests if r is not selected_request]
                alternate = get_feasible_request(remaining) if remaining else None
                # Prefer an alternate that is already due, or that is due sooner
                # than the selected future request (earlier planned_start).
                if alternate is not None:
                    alt_start = getattr(alternate, "scheduled_start_time", None)
                    if alt_start is None or alt_start <= self.env.now + 1e-9:
                        selected_request = alternate
                    elif alt_start + 1e-9 < scheduled_start:
                        selected_request = alternate
                    else:
                        alternate = None
                if alternate is None:
                    # Kick off dependency attendance *before* waiting for the
                    # planned production start. The schedule places worker moves
                    # before production; if we only open deps inside the handler
                    # after the wait, the move starts late and WIP/output drift
                    # by the move duration (~reaction + travel).
                    if (
                        selected_request.request_type
                        in (
                            request_module.RequestType.PRODUCTION,
                            request_module.RequestType.PROCESS_MODEL,
                        )
                        and selected_request.required_dependencies
                    ):
                        deps_flag = getattr(
                            selected_request, "dependencies_requested", None
                        )
                        if deps_flag is not None and not deps_flag.triggered:
                            selected_request.request_dependencies()
                    # Interruptible wait: new due requests (e.g. source pickups)
                    # must wake the controller — otherwise a future ws1→ws2 move
                    # parks the AGV until its planned_start and starves earlier
                    # scheduled transports that appear meanwhile.
                    wait = scheduled_start - self.env.now
                    if wait > 0:
                        timeout_ev = self.env.timeout(wait)
                        yield timeout_ev | self.state_changed
                    if not self.state_changed.triggered:
                        self.state_changed.succeed()
                    continue

            self.requests.remove(selected_request)
            if self._should_form_lot(selected_request):
                lot_request = self._form_lot(selected_request)
                if not lot_request:
                    # Can't form lot yet - move to end and try next request
                    self.requests.append(selected_request)
                    continue
                selected_request = lot_request
                
            # Re-check capacity with live computation: a spawned handler may have
            # called reserve_setup between iterations, reducing capacity_current_setup.
            if selected_request.capacity_required > self.resource.get_free_capacity():
                self.requests.append(selected_request)
                continue

            # Reserve output queue for transport requests (production requests reserve in their handler)
            if selected_request.request_type == request_module.RequestType.TRANSPORT:
                self.reserve_output_queue(selected_request)
            
            self.reserve_resource_capacity(selected_request.capacity_required)
            # For dependency requests, immediately bind the resource to block other processes
            if selected_request.request_type in (request_module.RequestType.PROCESS_DEPENDENCY, request_module.RequestType.RESOURCE_DEPENDENCY):
                self.resource.bind_to_dependant(selected_request.requesting_item)
            # Lock the resource for the whole changeover before spawning the
            # handler. Otherwise capacity>1 resources can start another
            # production in the same instant and steal ResourceDependency workers.
            # Use pending_setup (not reserve_setup): SETUP.request.process is the
            # *target* production process; reserving it early makes resource.setup()
            # think the changeover is already done and skip the real SetupState.
            if (
                selected_request.request_type == request_module.RequestType.SETUP
                and not self.resource.in_setup
            ):
                self.resource.mark_pending_setup()
            self.resource.update_full()
            process_handler = get_requets_handler(selected_request)
            self.env.process(process_handler.handle_request(selected_request))
            if (
                not self.resource.full
                and not self.resource.in_setup
                and self.requests
                and not self.state_changed.triggered
            ):
                self.state_changed.succeed()

    def reserve_output_queue(self, process_request: request_module.Request) -> Generator:
        """
        Reserve the output queue for the process.

        Args:
            process_request (request_module.Request): The request to reserve the output queue for.
        """
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

    def reserve_resource_capacity(self, capacity: int) -> None:
        """
        Reserve the resource capacity for the process.

        Args:
            process_request (request_module.Request): The request to reserve the resource capacity for.
        """
        if capacity > self.resource.get_free_capacity():
            raise ValueError(f"Resource {self.resource.data.ID} has not enough capacity to reserve {capacity}, current capacity: {self.resource.get_free_capacity()}, requested capacity: {capacity}")
        self.reserved_requests_count += capacity

    def unreserve_resource_capacity(self, capacity: int) -> None:
        """
        Unreserve the resource capacity for the process.

        Args:
            process_request (request_module.Request): The request to unreserve the resource capacity for.
        """
        self.reserved_requests_count -= capacity
        if self.reserved_requests_count < 0:
            raise ValueError(f"Resource {self.resource.data.ID} has not enough reserved to unreserve {capacity}, current capacity: {self.resource.get_free_capacity()}, requested capacity: {capacity}")

    def mark_started_process(
        self,
        num_processes: int = 1,
        process_request: request_module.Request | None = None,
    ) -> None:
        """
        Mark the process as started.

        Args:
            num_processes (int): The number of processes that are being started.
            process_request: When provided, the matched schedule index is marked
                consumed for setup-prefix gating (only once work actually starts).
        """
        self.unreserve_resource_capacity(num_processes)
        self.num_running_processes += num_processes
        self.resource.update_idle_logging()
        if process_request is not None:
            self._mark_schedule_index_started(process_request)

    def mark_finished_process(self, num_processes: int = 1) -> None:
        """
        Mark the process as finished.

        Args:
            process_request (Request): The request that is being processed.
        """
        self.num_running_processes -= num_processes
        self.resource.update_full()
        self.resource.update_idle_logging()
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


def _request_env(request: request_module.Request):
    """Resolve simulation env from requesting item, resource, or entity."""
    item = getattr(request, "requesting_item", None)
    if item is not None and getattr(item, "env", None) is not None:
        return item.env
    resource = getattr(request, "resource", None)
    if resource is not None and getattr(resource, "env", None) is not None:
        return resource.env
    entity = getattr(request, "entity", None)
    if entity is not None and getattr(entity, "env", None) is not None:
        return entity.env
    raise ValueError("Request has no env (requesting_item/resource/entity)")


def get_requets_handler(
    request: request_module.Request,
) -> Union[ProductionProcessHandler, TransportProcessHandler, DependencyProcessHandler, SetupProcessHandler, SystemProcessModelHandler, ResourceProcessModelHandler]:
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
    elif request.request_type == request_module.RequestType.SETUP:
        return SetupProcessHandler(_request_env(request))
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
        if request.request_type in (request_module.RequestType.PROCESS_DEPENDENCY, request_module.RequestType.RESOURCE_DEPENDENCY):
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
    schedule_matches_by_key: dict[tuple[str, str], list[int]],
    dependency_attendance_matches_by_key: dict,
    schedule_events: list,
    fallback_policy: Callable,
    requests: List[request_module.Request],
) -> None:
    """
    A control policy that sequences products based on their scheduled index in the sequence. 
    Matches requests based on both product ID and process ID to handle cases where the same
    product visits the resource multiple times with different processes.
    
    Matches each request to the next occurrence in the schedule sequence, ensuring that
    products are processed in the correct order even when they appear multiple times.
    
    If the request contains any product+process combination which is not in the schedule, 
    the fallback policy is also considered if it would be processed next. 

    Args:
        schedule_matches_by_key: For each ``(product_id, process_id)``, the ordered list of
            schedule indices where that pair appears on this resource.
        fallback_policy (Callable): fallback control policy
        requests (List[request_module.Request]): list of requests to sequence
    """

    matched_schedule_indices = set()
    request_to_priority = {}
    non_scheduled_requests = []
    product_next_expected_index = {}
    dependency_next_expected_index: dict[tuple[str, str, str | None], int] = {}

    from prodsys.simulation.schedule_dependency import (
        dependency_attendance_lookup_keys,
        preceding_dependency_move_start_time,
    )

    def _completed_indices_for(request_instance: request_module.Request) -> set[int]:
        resource = getattr(request_instance, "resource", None)
        controller = getattr(resource, "controller", None) if resource is not None else None
        if controller is None:
            return set()
        return set(getattr(controller, "completed_schedule_indices", ()) or ())

    request_matches = {}
    dependency_request_matches = {}
    for request_instance in requests:
        request_type = getattr(request_instance, "request_type", None)
        if request_type in (
            request_module.RequestType.PROCESS_DEPENDENCY,
            request_module.RequestType.RESOURCE_DEPENDENCY,
        ):
            lookup_keys = dependency_attendance_lookup_keys(request_instance)
            possible: list[tuple[int, tuple[str, str, str | None]]] = []
            for key in lookup_keys:
                for sched_index in dependency_attendance_matches_by_key.get(key, ()):
                    possible.append((sched_index, key))
            if possible:
                dependency_request_matches[request_instance] = possible
            else:
                non_scheduled_requests.append(request_instance)
            continue

        if request_type == request_module.RequestType.SETUP:
            product_id = request_instance.entity.data.ID if request_instance.entity else None
            setup_state_id = getattr(request_instance, "setup_state_id", None)
            if not product_id or not setup_state_id:
                non_scheduled_requests.append(request_instance)
                continue
            indices = schedule_matches_by_key.get((product_id, setup_state_id), ())
            if indices:
                request_matches[request_instance] = [
                    (sched_index, product_id, setup_state_id) for sched_index in indices
                ]
            else:
                non_scheduled_requests.append(request_instance)
            continue

        product_id = request_instance.entity.data.ID
        process_id = request_instance.process.data.ID if request_instance.process else None
        
        if not process_id:
            non_scheduled_requests.append(request_instance)
            continue
        
        indices = schedule_matches_by_key.get((product_id, process_id), ())
        if indices:
            request_matches[request_instance] = [
                (sched_index, product_id, process_id) for sched_index in indices
            ]
        else:
            non_scheduled_requests.append(request_instance)
    
    # Second pass: Match requests to schedule entries optimally
    # Strategy: Process schedule entries in order, and match requests as we go
    # This ensures that earlier schedule entries are matched first, maintaining correct order
    
    # Create a list of (request, possible_matches) sorted by earliest possible schedule index
    request_match_list = []
    for request_instance, possible_matches in request_matches.items():
        if possible_matches:
            earliest_index = min(m[0] for m in possible_matches)
            request_match_list.append((earliest_index, request_instance, possible_matches))
    
    # Sort by earliest possible schedule index
    request_match_list.sort(key=lambda x: x[0])

    dependency_match_list = []
    for request_instance, possible_matches in dependency_request_matches.items():
        earliest_index = min(m[0] for m in possible_matches)
        dependency_match_list.append(
            (earliest_index, request_instance, possible_matches)
        )
    dependency_match_list.sort(key=lambda x: x[0])

    for earliest_index, request_instance, possible_matches in dependency_match_list:
        completed = _completed_indices_for(request_instance)
        best_match = None
        for sched_index, key in possible_matches:
            if sched_index in matched_schedule_indices or sched_index in completed:
                continue
            next_expected = dependency_next_expected_index.get(key, 0)
            if sched_index >= next_expected:
                if best_match is None or sched_index < best_match[0]:
                    best_match = (sched_index, key)
        if best_match:
            sched_index, key = best_match
            request_to_priority[request_instance] = sched_index
            matched_schedule_indices.add(sched_index)
            dependency_next_expected_index[key] = sched_index + 1
            request_instance.scheduled_control_index = sched_index
            if sched_index < len(schedule_events):
                attendance_start = schedule_events[sched_index].time
                move_start = preceding_dependency_move_start_time(
                    schedule_events,
                    sched_index,
                    product_id=getattr(
                        request_instance, "dependent_product_id", None
                    ),
                )
                request_instance.scheduled_start_time = (
                    move_start if move_start is not None else attendance_start
                )
                request_instance.matched_schedule_event = schedule_events[sched_index]
        else:
            non_scheduled_requests.append(request_instance)
    
    # Now match requests in order of their earliest possible schedule index
    for earliest_index, request_instance, possible_matches in request_match_list:
        product_id = request_instance.entity.data.ID
        process_id = request_instance.process.data.ID
        completed = _completed_indices_for(request_instance)
        
        # Get the next expected index for this product
        next_expected = product_next_expected_index.get(product_id, 0)
        
        # Find the earliest match that is >= next_expected and not already matched
        # or already consumed by a prior execution on this resource.
        # For transports with a known origin/target, prefer schedule events that
        # bind the same locations so a stale intermediate hop cannot steal the
        # sink-transport slot (and start ASAP under a past scheduled_start).
        req_origin = getattr(request_instance, "origin", None)
        req_target = getattr(request_instance, "target", None)
        req_origin_id = getattr(req_origin, "data", None) and getattr(
            req_origin.data, "ID", None
        )
        if req_origin_id is None and req_origin is not None:
            req_origin_id = getattr(req_origin, "ID", None) or getattr(
                req_origin, "id", None
            )
        req_target_id = getattr(req_target, "data", None) and getattr(
            req_target.data, "ID", None
        )
        if req_target_id is None and req_target is not None:
            req_target_id = getattr(req_target, "ID", None) or getattr(
                req_target, "id", None
            )
        # Also accept queue IDs from the request's origin/target queue.
        if req_origin_id is None:
            oq = getattr(request_instance, "origin_queue", None)
            req_origin_id = getattr(getattr(oq, "data", None), "ID", None)
        if req_target_id is None:
            tq = getattr(request_instance, "target_queue", None)
            req_target_id = getattr(getattr(tq, "data", None), "ID", None)

        candidates = []
        for sched_index, sched_product_id, sched_process_id in possible_matches:
            if (
                sched_index >= next_expected
                and sched_index not in matched_schedule_indices
                and sched_index not in completed
            ):
                candidates.append((sched_index, sched_product_id, sched_process_id))

        best_match = None
        if candidates and (
            getattr(request_instance, "request_type", None)
            == request_module.RequestType.TRANSPORT
            and (req_origin_id or req_target_id)
        ):
            loc_matched = []
            for sched_index, sched_product_id, sched_process_id in candidates:
                if sched_index >= len(schedule_events):
                    continue
                ev = schedule_events[sched_index]
                ev_origin = getattr(ev, "origin_location", None)
                ev_target = getattr(ev, "target_location", None)
                origin_ok = (
                    req_origin_id is None
                    or ev_origin is None
                    or ev_origin == req_origin_id
                )
                target_ok = (
                    req_target_id is None
                    or ev_target is None
                    or ev_target == req_target_id
                )
                # Prefer events that actually bind at least one location and match.
                if (ev_origin is not None or ev_target is not None) and origin_ok and target_ok:
                    loc_matched.append((sched_index, sched_product_id, sched_process_id))
            if loc_matched:
                best_match = min(loc_matched, key=lambda m: m[0])
        if best_match is None and candidates:
            best_match = min(candidates, key=lambda m: m[0])
        
        if best_match:
            sched_index, _, _ = best_match
            request_to_priority[request_instance] = sched_index
            matched_schedule_indices.add(sched_index)
            request_instance.scheduled_control_index = sched_index
            if sched_index < len(schedule_events):
                request_instance.scheduled_start_time = schedule_events[sched_index].time
                request_instance.matched_schedule_event = schedule_events[sched_index]
            # Update next expected index for this product
            product_next_expected_index[product_id] = sched_index + 1
        else:
            # No valid match found - this shouldn't happen if schedule is correct
            non_scheduled_requests.append(request_instance)
    
    if len(non_scheduled_requests) == 0:
        requests.sort(key=lambda r: request_to_priority.get(r, float('inf')))
        return
    
    # Some requests are not scheduled - check if fallback would help
    request_list_copy = requests[::]
    fallback_policy(request_list_copy)
    # If fallback would select a non-scheduled request, use fallback for all
    if request_list_copy[0] in non_scheduled_requests:
        fallback_policy(requests)
        return
    
    # Mix scheduled and non-scheduled: prioritize scheduled ones
    scheduled_requests = [r for r in requests if r in request_to_priority]
    scheduled_requests.sort(key=lambda r: request_to_priority[r])
    
    # Put scheduled requests first, then non-scheduled (sorted by fallback)
    requests.clear()
    requests.extend(scheduled_requests)
    requests.extend(non_scheduled_requests)


# TODO: add a Controller which starts processes with delays...

