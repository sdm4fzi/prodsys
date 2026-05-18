"""Schedule-driven simulation completion tracking.

When a :class:`~prodsys.simulation.runner.Runner` is fed a
:attr:`~prodsys.models.production_system_data.ProductionSystemData.schedule`,
the run is logically *finished* the moment every product the schedule
expects to produce has reached its sink.  Plain ``env.run(time_range)``
does not know this and keeps simulating idle time up to the nominal
horizon, which for plan-driven workloads can mean hours of wall-time
spent on a system that has been quiescent for the last 95 % of it.

:class:`ScheduleCompletionTracker` reads the schedule once on
construction and exposes a SimPy :attr:`completion_event` that succeeds
the instant the cumulative number of finished products matches what the
schedule prescribed (per-sink, so partial schedules over only some
product types still terminate cleanly).  Sinks call
:meth:`record_finished` on every successful drop-off, which is enough
for the tracker to detect completion without needing further plumbing
into the simulation graph.

Typical use is via :meth:`Runner.run_until_complete` which wraps this
behind a familiar ``run(time_range)``-style API.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from prodsys.models.production_system_data import ProductionSystemData
    from prodsys.simulation.entities.product import Product
    from prodsys.simulation import sim


logger = logging.getLogger(__name__)


class ScheduleCompletionTracker:
    """Counts finished products against a per-sink expected total.

    The expected total is derived from the active schedule by mapping
    each scheduled ``product_id`` to the sink that accepts its product
    type.  Products whose type has no matching sink in the model fall
    into ``unattributed_expected`` and are still counted toward the
    grand total — they would otherwise escape the completion check.

    Public attributes:

    - :attr:`expected`: total number of products the schedule wants to
      finish.  ``0`` when the model has no schedule, in which case
      :attr:`completion_event` is ``None`` and the tracker is a no-op.
    - :attr:`finished`: running count of finished products that the
      tracker has been notified about.
    - :attr:`expected_per_sink`: dict ``sink_id -> int`` of the per-
      sink expected count.  Useful for diagnostics and for downstream
      consumers that want to break down progress per sink.
    - :attr:`finished_per_sink`: running count, same layout.
    - :attr:`completion_event`: SimPy :class:`~simpy.events.Event`
      that succeeds when ``finished >= expected``.  ``None`` if the
      tracker is inert (no schedule).

    The tracker stays correct under partial schedules (only some
    products / sinks scheduled) and under multi-sink models — every
    sink reports independently and we only fire the completion event
    once **all** sinks have hit their expected target.
    """

    def __init__(
        self,
        env: "sim.Environment",
        ps_data: Optional["ProductionSystemData"],
    ) -> None:
        self.env = env
        self.expected_per_sink: dict[str, int] = {}
        self.finished_per_sink: Counter[str] = Counter()
        self.unattributed_expected = 0
        self.unattributed_finished = 0
        self.expected = 0
        self.finished = 0
        self.completion_event: Optional["sim.Event"] = None

        if ps_data is None or not getattr(ps_data, "schedule", None):
            return

        scheduled_product_ids = {
            event.product
            for event in ps_data.schedule
            if getattr(event, "product", None)
        }
        if not scheduled_product_ids:
            return

        # product_type -> sink_id (a product type lands at the sink that
        # accepts it).  Models with multiple sinks for the same type
        # collapse to the first match — unusual but supported.
        sink_for_type: dict[str, str] = {}
        for sink_data in ps_data.sink_data or []:
            sink_for_type.setdefault(sink_data.product_type, sink_data.ID)

        # Map scheduled product IDs to product types.  Production
        # systems generated from order data carry the product type as a
        # prefix of the id (e.g. ``Product_J8_VFS_Prog_WR014_3``); we
        # match longest-prefix against the registered types so multi-
        # word ids like that resolve correctly.
        type_prefixes = sorted(
            (p.ID for p in ps_data.product_data or []),
            key=len,
            reverse=True,
        )

        def _resolve_type(product_id: str) -> Optional[str]:
            for type_id in type_prefixes:
                if product_id == type_id or product_id.startswith(type_id + "_"):
                    return type_id
            return None

        for pid in scheduled_product_ids:
            ptype = _resolve_type(pid)
            sink_id = sink_for_type.get(ptype) if ptype else None
            if sink_id is None:
                self.unattributed_expected += 1
            else:
                self.expected_per_sink[sink_id] = (
                    self.expected_per_sink.get(sink_id, 0) + 1
                )

        self.expected = (
            sum(self.expected_per_sink.values()) + self.unattributed_expected
        )
        if self.expected > 0:
            self.completion_event = env.event()

    def record_finished(self, product: "Product", sink_id: Optional[str] = None) -> None:
        """Notify the tracker that ``product`` has reached its sink.

        ``sink_id`` is optional — when omitted we attribute the product
        to the first sink whose ``product_type`` matches.  Sinks that
        know their own ID can pass it directly to skip the lookup.
        """
        if self.completion_event is None or self.completion_event.triggered:
            return

        self.finished += 1
        if sink_id is not None and sink_id in self.expected_per_sink:
            self.finished_per_sink[sink_id] += 1
        else:
            self.unattributed_finished += 1

        if self.finished >= self.expected:
            logger.info(
                "Schedule completion: %d/%d products finished at t=%.1f s; "
                "firing completion event.",
                self.finished, self.expected, self.env.now,
            )
            self.completion_event.succeed()

    def progress_summary(self) -> dict[str, object]:
        """Snapshot of progress for logging / summaries."""
        return {
            "expected": self.expected,
            "finished": self.finished,
            "expected_per_sink": dict(self.expected_per_sink),
            "finished_per_sink": dict(self.finished_per_sink),
            "unattributed_expected": self.unattributed_expected,
            "unattributed_finished": self.unattributed_finished,
            "complete": self.completion_event is not None
            and self.completion_event.triggered,
        }
