from __future__ import annotations

import simpy
from dataclasses import dataclass

import resources
import process
import material

@dataclass
class Request:
    _process: process.Process
    _material: material.Material
    _resource: resources.Resource

    def get_process(self) -> process.Process:
        return self._process

    def get_material(self) -> material.Material:
        return self._material
    
    def get_resource(self) -> resources.Resource:
        return self._resource

@dataclass
class TransportResquest(Request):
    origin: resources.Resource
    target: resources.Resource

    def get_origin(self) -> resources.Resource:
        return self.origin

    def get_target(self) -> resources.Resource:
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
        self, resource: resources.Resource, dispatch_criteria: list, preempt: bool = True, time_prio : int = None,
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