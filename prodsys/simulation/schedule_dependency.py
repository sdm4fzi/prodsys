"""Schedule lookup for dependency worker ``move`` hops (plan ↔ simulation)."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Deque, Optional

from prodsys.models import performance_data
from prodsys.simulation import request as request_module

DependencyMoveKey = tuple[str, str, str | None, str | None]
DependencyMoveRouteKey = tuple[str, str, str | None, str | None, str]
DependencyMoveRoutingKey = DependencyMoveKey


def _move_process_id(event: performance_data.Event) -> str | None:
    if event.process:
        return event.process
    return event.state


def build_dependency_move_schedule_index(
    schedule: list[performance_data.Event] | None,
) -> tuple[
    dict[DependencyMoveKey, Deque[int]],
    dict[DependencyMoveRouteKey, Deque[tuple[float, str]]],
    list[performance_data.Event],
    dict[DependencyMoveRoutingKey, Deque[tuple[float, str]]],
]:
    """Index dependency ``move`` start events for control ordering and routing.

    Returns ``(match_indices_by_key, route_by_key, ordered_events,
    routing_by_key)`` where *match_indices_by_key* maps
    ``(product, move_process, dependency, requesting_item)`` to schedule
    indices, *route_by_key* adds ``resource`` for per-resource routing, and
    *routing_by_key* maps the same key to ``(time, worker_resource)`` deques.
    """
    ordered: list[performance_data.Event] = []
    match_indices: dict[DependencyMoveKey, Deque[int]] = defaultdict(deque)
    route_entries: dict[DependencyMoveRouteKey, Deque[tuple[float, str]]] = defaultdict(
        deque
    )
    routing_by_key: dict[DependencyMoveRoutingKey, Deque[tuple[float, str]]] = (
        defaultdict(deque)
    )
    if not schedule:
        return match_indices, route_entries, ordered, routing_by_key

    for index, event in enumerate(schedule):
        if event.activity != "start state":
            continue
        if event.state_type != "Transport":
            continue
        if not event.empty_transport:
            continue
        move_pid = _move_process_id(event)
        if not move_pid or not event.product:
            continue
        ordered.append(event)
        key: DependencyMoveKey = (
            event.product,
            move_pid,
            event.dependency or None,
            event.requesting_item or None,
        )
        match_indices[key].append(index)
        route_key: DependencyMoveRouteKey = (*key, event.resource)
        route_entries[route_key].append((float(event.time or 0.0), event.resource))
        routing_by_key[key].append((float(event.time or 0.0), event.resource))

    return match_indices, route_entries, ordered, routing_by_key


def dependency_schedule_lookup_keys(
    req: request_module.Request,
) -> list[DependencyMoveKey]:
    """Return lookup keys from most specific to generic."""
    full = dependency_schedule_lookup_key(req)
    if full is None:
        return []
    product_id, move_pid, dep_id, requiring = full
    keys = [full]
    keys.append((product_id, move_pid, dep_id, None))
    keys.append((product_id, move_pid, None, requiring))
    keys.append((product_id, move_pid, None, None))
    return keys


def dependency_schedule_lookup_key(
    req: request_module.Request,
) -> DependencyMoveKey | None:
    product_id = getattr(req, "dependent_product_id", None)
    move_pid = getattr(req, "schedule_dependency_move_process_id", None)
    if not product_id or not move_pid:
        return None
    dep_id = None
    if req.resolved_dependency is not None:
        dep_id = req.resolved_dependency.data.ID
    requiring = getattr(req, "requiring_resource_id", None)
    return (product_id, move_pid, dep_id, requiring)


def worker_move_process_id(resource) -> str | None:
    from prodsys.models.processes_data import ProcessTypeEnum
    from prodsys.simulation.process import TransportProcess

    for proc in getattr(resource, "processes", []) or []:
        if isinstance(proc, TransportProcess):
            return proc.data.ID
        ptype = getattr(getattr(proc, "data", None), "type", None)
        if ptype == ProcessTypeEnum.TransportProcesses:
            return proc.data.ID
    return None


def resolve_dependent_product_id(
    requesting_item,
) -> str | None:
    from prodsys.simulation.entities.entity import EntityType

    if requesting_item is None:
        return None
    entity_type = getattr(requesting_item, "type", None)
    if entity_type == EntityType.PRODUCT:
        return requesting_item.data.ID
    if entity_type == EntityType.LOT:
        primary = requesting_item.get_primary_entity()
        return primary.data.ID if primary is not None else None
    return None


def resolve_dependent_order_id(
    requesting_item,
) -> str | None:
    """Return the order that owns the product driving a dependency request."""
    from prodsys.simulation.entities.entity import EntityType

    if requesting_item is None:
        return None
    entity_type = getattr(requesting_item, "type", None)
    if entity_type == EntityType.PRODUCT:
        return getattr(requesting_item.info, "order_ID", None)
    if entity_type == EntityType.LOT:
        primary = requesting_item.get_primary_entity()
        if primary is not None:
            return getattr(primary.info, "order_ID", None)
    return None


def apply_dependency_move_log_metadata(
    state_info,
    process_request: request_module.Request,
) -> None:
    """Fill transport log fields from a matched schedule event or runtime context."""
    ev: performance_data.Event | None = getattr(
        process_request, "matched_schedule_event", None
    )
    if ev is not None and ev.product:
        state_info._product_ID = ev.product
    elif getattr(process_request, "dependent_product_id", None):
        state_info._product_ID = process_request.dependent_product_id

    if ev is not None and ev.dependency:
        state_info._dependency_ID = ev.dependency
    elif process_request.resolved_dependency is not None:
        state_info._dependency_ID = process_request.resolved_dependency.data.ID

    if ev is not None and ev.requesting_item:
        state_info._requesting_item_ID = ev.requesting_item
    elif getattr(process_request, "requiring_resource_id", None):
        state_info._requesting_item_ID = process_request.requiring_resource_id
