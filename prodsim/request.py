from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import simpy

if TYPE_CHECKING:
    from . import material, process, resources


@dataclass
class Request:
    _process: process.PROCESS_UNION
    _material: material.Material
    _resource: resources.RESOURCE_UNION

    def get_process(self) -> process.PROCESS_UNION:
        return self._process

    def get_material(self) -> material.Material:
        return self._material
    
    def get_resource(self) -> resources.RESOURCE_UNION:
        return self._resource

@dataclass
class TransportResquest(Request):
    origin: resources.Resourcex
    target: resources.Resourcex

    def get_origin(self) -> resources.Resourcex:
        return self.origin

    def get_target(self) -> resources.Resourcex:
        return self.target







class FlexibleRequest(simpy.resources.resource.Request):
    """Request the usage of *resource* based on a given **. If the
    *resource* supports preemption and *preempt* is ``True`` other usage
    requests of the *resource* may be preempted (see
    :class:`PreemptiveResource` for details).

    This event type inherits :class:`Request` and adds some additional
    attributes needed by :class:`PriorityResource` and
    :class:`PreemptiveResource`

    """

    def __init__(
        self, resource: resources.Resourcex, dispatch_criteria: list, preempt: bool = True, time_prio : int = None,
            preempt_prio: int = None
    ):
        self.preempt = preempt
        """Indicates whether the request should preempt a resource user or not
        (:class:`PriorityResource` ignores this flag)."""
        if time_prio is not None:
            self.time = resource._env.now
            dispatch_criteria.insert(time_prio, self.time)
        if preempt_prio is not None:
            dispatch_criteria.insert(preempt_prio, not preempt)

        """The time at which the request was made."""


        self.key = tuple(dispatch_criteria)
        """Key for sorting events (lower values are more important)."""

        super().__init__(resource)