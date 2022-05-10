import simpy
from simpy.core import BoundClass, Environment
from simpy import Resource
from simpy.resources.resource import Request, SortedQueue, Release, Preempted
from typing import TYPE_CHECKING, Any, List, Optional, Type


class FlexibleRequest(Request):
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

class FlexibleResource(Resource):
    """A :class:`~simpy.resources.resource.Resource` supporting prioritized
    requests.

    Pending requests in the :attr:`~Resource.queue` are sorted in ascending
    order by their *priority* (that means lower values are more important).

    """
    users: List[FlexibleRequest]  # type: ignore

    PutQueue = SortedQueue
    """Type of the put queue. See
    :attr:`~simpy.resources.base.BaseResource.put_queue` for details."""

    GetQueue = list
    """Type of the get queue. See
    :attr:`~simpy.resources.base.BaseResource.get_queue` for details."""

    def __init__(self, env: Environment, capacity: int = 1):
        super().__init__(env, capacity)

    if TYPE_CHECKING:

        def request(
                self, dispatch_criteria: list, preempt: bool = True, time_prio: int = None,
                preempt_prio: int = None
        ) -> FlexibleRequest:
            """Request a usage slot with the given *priority*."""
            return FlexibleRequest(
                self, dispatch_criteria, preempt, time_prio, preempt_prio
            )

        def release(  # type: ignore[override] # noqa: F821
            self, request: FlexibleRequest
        ) -> Release:
            """Release a usage slot."""
            return Release(self, request)

    else:
        request = BoundClass(FlexibleRequest)
        release = BoundClass(Release)

    def _do_put(  # type: ignore[override] # noqa: F821
        self, event: FlexibleRequest
    ) -> None:
        if len(self.users) >= self.capacity and event.preempt:
            # Check if we can preempt another process
            preempt = sorted(self.users, key=lambda e: e.key)[-1]
            if preempt.key > event.key:
                self.users.remove(preempt)
                preempt.proc.interrupt(  # type: ignore
                    Preempted(
                        by=event.proc,
                        usage_since=preempt.usage_since,
                        resource=self,
                    )
                )

        return super()._do_put(event)



class ManufacturingResource(Resource):
    def __init__(self, env: Environment, capacity: int = 1):
        super().__init__(env=env, capacity=capacity)

        self.env = env
        self.state = None

    def process(self) -> None:
        pass

    def setup(self) -> None:
        pass









