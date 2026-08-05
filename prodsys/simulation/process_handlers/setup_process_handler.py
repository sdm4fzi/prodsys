from __future__ import annotations

from typing import TYPE_CHECKING, Generator, Iterable, List

import logging

import simpy

from prodsys.models.dependency_data import DependencyType
from prodsys.simulation import sim, state

if TYPE_CHECKING:
    from prodsys.simulation import request as request_module
    from prodsys.simulation import resources as resources_module
    from prodsys.simulation.dependency import Dependency

logger = logging.getLogger(__name__)


def _resource_is_free_for_attendance(
    resource: "resources_module.Resource",
    *,
    requiring_machine: "resources_module.Resource | None" = None,
) -> bool:
    """True if the worker/resource can be claimed later for production attendance.

    A worker already bound to ``requiring_machine`` (on-site for this station's
    production) counts as usable: setup must not deadlock waiting for "free"
    while attendance for the same changeover's parent production is open.
    """
    if getattr(resource, "bound", False):
        if (
            requiring_machine is not None
            and getattr(resource, "current_dependant", None) is requiring_machine
        ):
            return True
        return False
    if getattr(resource, "full", False):
        return False
    controller = getattr(resource, "controller", None)
    if controller is not None and getattr(controller, "num_running_processes", 0) > 0:
        # Already attending at this machine (bound check above can miss if
        # bind_to_dependant has not run yet but the dep process is running).
        if (
            requiring_machine is not None
            and getattr(resource, "current_dependant", None) is requiring_machine
        ):
            return True
        return False
    return True


def _candidate_resources_for_dependency(
    dependency: "Dependency",
    process_matcher,
) -> List["resources_module.Resource"]:
    """Resolve PROCESS/RESOURCE dependency candidates (same as dependency routing)."""
    dep_type = dependency.data.dependency_type
    if dep_type == DependencyType.RESOURCE:
        required = getattr(dependency, "required_resource", None)
        return [required] if required is not None else []
    if dep_type == DependencyType.PROCESS:
        if process_matcher is None:
            return []
        required_process = getattr(dependency, "required_process", None)
        if required_process is None:
            return []
        return [
            resource
            for resource, _ in process_matcher.get_compatible([required_process])
        ]
    return []


def attendance_dependencies_have_free_resource(
    dependencies: Iterable["Dependency"],
    process_matcher,
    *,
    requiring_machine: "resources_module.Resource | None" = None,
) -> bool:
    """Every PROCESS/RESOURCE dep has at least one free candidate resource."""
    for dependency in dependencies:
        if dependency.data.dependency_type not in (
            DependencyType.PROCESS,
            DependencyType.RESOURCE,
        ):
            continue
        candidates = _candidate_resources_for_dependency(dependency, process_matcher)
        if not candidates:
            return False
        if not any(
            _resource_is_free_for_attendance(r, requiring_machine=requiring_machine)
            for r in candidates
        ):
            return False
    return True


class SetupProcessHandler:
    """Execute a scheduled (or fallback) resource changeover as its own request."""

    def __init__(self, env: sim.Environment) -> None:
        self.env = env
        self.resource = None

    def _wait_until_attendance_free(
        self,
        dep_request: "request_module.Request",
        *,
        requiring_machine: "resources_module.Resource | None" = None,
    ) -> Generator:
        """Gate setup on worker *availability*, not on-site attendance.

        Matches the scheduler: setup may start once a required worker is free
        (``free_at``), but the worker is only dispatched to the machine for the
        following production step via ``request_dependencies()``.

        If the worker is already bound to ``requiring_machine`` (attendance
        opened early for the parent production), treat that as usable so setup
        and attendance are not deadlocked.
        """
        dependencies = list(dep_request.required_dependencies or [])
        attendance_deps = [
            d
            for d in dependencies
            if d.data.dependency_type
            in (DependencyType.PROCESS, DependencyType.RESOURCE)
        ]
        # Ahead-of-product setups may only carry resource.dependencies via the
        # SETUP request itself; also fall back to the machine's deps.
        if not attendance_deps and requiring_machine is not None:
            attendance_deps = [
                d
                for d in (getattr(requiring_machine, "dependencies", None) or [])
                if d.data.dependency_type
                in (DependencyType.PROCESS, DependencyType.RESOURCE)
            ]
        if not attendance_deps:
            return

        requesting_item = dep_request.requesting_item
        router = getattr(requesting_item, "router", None) if requesting_item else None
        if router is None and requiring_machine is not None:
            controller = getattr(requiring_machine, "controller", None)
            product_factory = getattr(controller, "product_factory", None) if controller else None
            router = getattr(product_factory, "router", None) if product_factory else None
        if router is None:
            # RESOURCE deps don't need a process matcher; PROCESS deps do.
            process_only = [
                d
                for d in attendance_deps
                if d.data.dependency_type == DependencyType.PROCESS
            ]
            if process_only:
                logger.warning(
                    "Setup attendance free-check skipped for PROCESS deps: no router"
                )
                return
            process_matcher = None
        else:
            process_matcher = router.request_handler.process_matcher

        while not attendance_dependencies_have_free_resource(
            attendance_deps,
            process_matcher,
            requiring_machine=requiring_machine,
        ):
            wait_events: list = []
            seen: set[int] = set()
            for dependency in attendance_deps:
                for candidate in _candidate_resources_for_dependency(
                    dependency, process_matcher
                ):
                    ctrl = getattr(candidate, "controller", None)
                    if ctrl is None:
                        continue
                    key = id(ctrl)
                    if key in seen:
                        continue
                    seen.add(key)
                    state_changed = ctrl.state_changed
                    if state_changed.triggered:
                        wait_events.append(self.env.timeout(0))
                    else:
                        wait_events.append(state_changed)
            if not wait_events:
                # No controllers to wait on — avoid a tight spin.
                yield self.env.timeout(0)
                continue
            yield simpy.AnyOf(self.env, wait_events)

    def handle_request(self, process_request: "request_module.Request") -> Generator:
        resource = process_request.get_resource()
        self.resource = resource
        process = process_request.get_process()

        # Prefer the parent production request so we inspect the same PROCESS /
        # RESOURCE deps production will later request on-site.
        dep_request = (
            getattr(process_request, "parent_production_request", None)
            or process_request
        )
        yield from self._wait_until_attendance_free(
            dep_request, requiring_machine=resource
        )

        scheduled_start = getattr(process_request, "scheduled_start_time", None)
        # Always honor planned setup start when the schedule provided one.
        # (General production/transport ASAP timing stays separate.)
        if (
            scheduled_start is not None
            and self.env.now + 1e-9 < scheduled_start
        ):
            yield self.env.timeout(scheduled_start - self.env.now)
        # Let same-time product creation / arrivals run before we resolve
        # the product for setup logging (ahead-of-product changeovers).
        yield self.env.timeout(0)

        # Attach product to the matching SetupState log when available.
        setup_state_id = getattr(process_request, "setup_state_id", None)
        product = None
        try:
            product = process_request.get_entity()
        except Exception:
            product = None
        if product is None:
            # Ahead-of-product setups: product may appear by planned start.
            pid = getattr(process_request, "_schedule_product_id", None)
            if pid is None:
                ev = getattr(process_request, "matched_schedule_event", None)
                pid = getattr(ev, "product", None) if ev is not None else None
            controller = getattr(resource, "controller", None)
            product_factory = (
                getattr(controller, "product_factory", None) if controller else None
            )
            products = getattr(product_factory, "products", None) or {}
            if pid is not None:
                product = products.get(pid)
            if product is not None:
                process_request.entity = product
                if process_request.requesting_item is None:
                    process_request.requesting_item = product
        if setup_state_id and product is not None:
            for setup_state in resource.setup_states:
                if setup_state.data.ID == setup_state_id:
                    setup_state.state_info.log_product(
                        product, state.StateTypeEnum.setup
                    )
                    break

        resource.controller.mark_started_process(1, process_request)
        try:
            yield from resource.setup(process)
        finally:
            # Clear pre-acceptance lock if setup() exited without reserve/unreserve
            # (e.g. already on the target process).
            clear_pending = getattr(resource, "clear_pending_setup", None)
            if callable(clear_pending):
                clear_pending()
        resource.controller.mark_finished_process()

        if process_request.completed is not None and not process_request.completed.triggered:
            process_request.completed.succeed()
        if (
            process_request.processing_finished is not None
            and not process_request.processing_finished.triggered
        ):
            process_request.processing_finished.succeed()
