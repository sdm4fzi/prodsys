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


def _resource_is_free_for_attendance(resource: "resources_module.Resource") -> bool:
    """True if the worker/resource can be claimed later for production attendance."""
    if getattr(resource, "bound", False):
        return False
    if getattr(resource, "full", False):
        return False
    controller = getattr(resource, "controller", None)
    if controller is not None and getattr(controller, "num_running_processes", 0) > 0:
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
        if not any(_resource_is_free_for_attendance(r) for r in candidates):
            return False
    return True


class SetupProcessHandler:
    """Execute a scheduled (or fallback) resource changeover as its own request."""

    def __init__(self, env: sim.Environment) -> None:
        self.env = env
        self.resource = None

    def _wait_until_attendance_free(
        self, dep_request: "request_module.Request"
    ) -> Generator:
        """Gate setup on worker *availability*, not on-site attendance.

        Matches the scheduler: setup may start once a required worker is free
        (``free_at``), but the worker is only dispatched to the machine for the
        following production step via ``request_dependencies()``.
        """
        dependencies = list(dep_request.required_dependencies or [])
        attendance_deps = [
            d
            for d in dependencies
            if d.data.dependency_type
            in (DependencyType.PROCESS, DependencyType.RESOURCE)
        ]
        if not attendance_deps:
            return

        requesting_item = dep_request.requesting_item
        router = getattr(requesting_item, "router", None)
        if router is None:
            logger.warning(
                "Setup attendance free-check skipped: no router on requesting_item"
            )
            return
        process_matcher = router.request_handler.process_matcher

        while not attendance_dependencies_have_free_resource(
            attendance_deps, process_matcher
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
        yield from self._wait_until_attendance_free(dep_request)

        scheduled_start = getattr(process_request, "scheduled_start_time", None)
        controller = getattr(resource, "controller", None)
        strict_timing = bool(getattr(controller, "strict_schedule_timing", False))
        if (
            strict_timing
            and scheduled_start is not None
            and self.env.now + 1e-9 < scheduled_start
        ):
            yield self.env.timeout(scheduled_start - self.env.now)

        # Attach product to the matching SetupState log when available.
        setup_state_id = getattr(process_request, "setup_state_id", None)
        product = None
        try:
            product = process_request.get_entity()
        except Exception:
            product = None
        if setup_state_id and product is not None:
            for setup_state in resource.setup_states:
                if setup_state.data.ID == setup_state_id:
                    setup_state.state_info.log_product(
                        product, state.StateTypeEnum.setup
                    )
                    break

        resource.controller.mark_started_process(1, process_request)
        yield from resource.setup(process)
        resource.controller.mark_finished_process()

        if process_request.completed is not None and not process_request.completed.triggered:
            process_request.completed.succeed()
        if (
            process_request.processing_finished is not None
            and not process_request.processing_finished.triggered
        ):
            process_request.processing_finished.succeed()
