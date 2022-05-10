from base2 import Resource, Process, Material
from simpy.resources import resource
from typing import List
from dataclasses import dataclass
from abc import ABC, abstractmethod

class Request(ABC, resource.Request):
    process: Process
    materials: List[Material]
    resource: Resource

    @abstractmethod
    def get_process_time(self):
        return self.process.get_process_time()







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
        self, resource: Resource, dispatch_criteria: list, preempt: bool = True, time_prio : int = None,
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