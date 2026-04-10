"""
Interval builder: pairing state machine that converts raw prodsys events
into closed intervals.

This is the single place where start/end state and start/end interrupt pairing
logic lives. Everything downstream reads closed intervals and never touches
raw events again.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from prodsys.simulation.state import StateTypeEnum

import logging

logger = logging.getLogger(__name__)

INTERFACE_STATE_TYPES = frozenset({
    StateTypeEnum.source, StateTypeEnum.sink,
    StateTypeEnum.breakdown, StateTypeEnum.setup,
    StateTypeEnum.charging, StateTypeEnum.loading,
    StateTypeEnum.unloading, StateTypeEnum.assembly,
    StateTypeEnum.non_scheduled,
})

PROCESS_STATE_TYPES = frozenset({
    StateTypeEnum.production, StateTypeEnum.transport,
    StateTypeEnum.dependency,
})

INTERVAL_COLUMNS = [
    "entity_id", "entity_kind", "state_type", "state_id",
    "t_start", "t_end", "duration",
    "product_id", "product_type", "process_ok", "interrupted",
    "origin_location", "target_location", "resource",
]


def _event_sort_key(event: dict) -> tuple:
    """
    Sorting key for events at the same simulation time.
    Ensures correct ordering: ends before starts, interface before process.
    Mirrors the State_sorting_Index from the old DataPreparation.
    """
    activity = event.get("Activity", "")
    state_type_raw = event.get("State Type", "")

    if isinstance(state_type_raw, StateTypeEnum):
        is_process = state_type_raw in PROCESS_STATE_TYPES
    else:
        try:
            st = StateTypeEnum(str(state_type_raw))
            is_process = st in PROCESS_STATE_TYPES
        except ValueError:
            is_process = False

    priority_map = {
        ("finished product", False): 1,
        ("finished product", True): 1,
        ("created product", False): 2,
        ("created product", True): 2,
        ("consumed product", False): 2,
        ("consumed product", True): 2,
        ("end state", False): 3,        # interface end state
        ("end interrupt", True): 4,     # process end interrupt
        ("end state", True): 5,         # process end state
        ("start state", True): 6,       # process start state
        ("start interrupt", True): 7,   # process start interrupt
        ("start state", False): 8,      # interface start state
    }
    return (event.get("Time", 0.0), priority_map.get((activity, is_process), 9))


@dataclass
class _OpenInterval:
    """Metadata for an interval that has been opened but not yet closed."""
    t_start: float
    entity_id: str
    entity_kind: str
    state_type: str
    state_id: str
    product_id: Optional[str] = None
    product_type: Optional[str] = None
    origin_location: Optional[str] = None
    target_location: Optional[str] = None


class IntervalBuilder:
    """
    Converts raw prodsys events into closed intervals.

    Invariants:
      - At most one open interval per (entity_id, state_id, product_id).
        For process states on multi-capacity resources, multiple intervals
        can be open simultaneously if they have different product_ids.
      - A 'start interrupt' closes the current interval as interrupted and
        suspends it; 'end interrupt' resumes from the suspension point.
      - On flush(), still-open intervals are emitted with t_end=t_now.
      - Product lifecycle events (created/finished/consumed) produce both
        marker intervals and "in_system" spans for throughput/WIP.
    """

    def __init__(self) -> None:
        self._open: dict[tuple, _OpenInterval] = {}
        self._suspended: dict[tuple, list[_OpenInterval]] = {}
        self._product_creation: dict[str, tuple[float, Optional[str]]] = {}
        self._closed: list[dict] = []

    @staticmethod
    def _make_key(resource: str, state_id: str, product_id: Optional[str] = None) -> tuple:
        return (resource, state_id, product_id)

    @staticmethod
    def derive_product_type(product_id: Optional[str]) -> Optional[str]:
        if product_id is None or (isinstance(product_id, float) and product_id != product_id):
            return None
        product_id = str(product_id)
        parts = product_id.rsplit("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return parts[0]
        return product_id

    def feed(self, event: dict) -> None:
        """Process a single raw event."""
        activity = event.get("Activity", "")
        resource = event.get("Resource")
        state_id = event.get("State", "")
        t = event.get("Time", 0.0)
        product_id = event.get("Product")
        if isinstance(product_id, float) and product_id != product_id:
            product_id = None
        product_type = self.derive_product_type(product_id)

        if activity == "start state":
            self._handle_start_state(resource, state_id, event, t, product_id, product_type)
        elif activity == "end state":
            self._handle_end_state(resource, state_id, t, event)
        elif activity == "start interrupt":
            self._handle_start_interrupt(resource, state_id, t, product_id)
        elif activity == "end interrupt":
            self._handle_end_interrupt(resource, state_id, t, product_id, product_type, event)
        elif activity == "created product":
            self._handle_created_product(resource, t, product_id, product_type, event)
        elif activity == "finished product":
            self._handle_finished_product(resource, t, product_id, product_type, event)
        elif activity == "consumed product":
            self._handle_consumed_product(resource, t, product_id, product_type, event)

    def ingest_dataframe(self, df_raw: pd.DataFrame) -> None:
        """
        Ingest a complete raw event DataFrame, sorting events correctly
        before feeding them to the state machine.
        """
        events = df_raw.to_dict("records")
        events.sort(key=_event_sort_key)
        for event in events:
            self.feed(event)

    # ── State transitions ────────────────────────────────────────────────

    @staticmethod
    def _normalize_state_type(raw) -> str:
        """Convert a StateTypeEnum member or string to its plain string value."""
        if isinstance(raw, StateTypeEnum):
            return raw.value
        s = str(raw) if raw is not None else ""
        if s.startswith("StateTypeEnum."):
            try:
                return StateTypeEnum[s.split(".", 1)[1]].value
            except (KeyError, IndexError):
                pass
        return s

    def _handle_start_state(self, resource, state_id, event, t, product_id, product_type):
        if resource is None:
            return
        key = self._make_key(resource, state_id, product_id)
        if key in self._open:
            logger.debug("Overwriting open interval for %s (defensive)", key)
        state_type = self._normalize_state_type(event.get("State Type", ""))
        self._open[key] = _OpenInterval(
            t_start=t,
            entity_id=resource,
            entity_kind="resource",
            state_type=state_type,
            state_id=state_id,
            product_id=product_id,
            product_type=product_type,
            origin_location=event.get("Origin location"),
            target_location=event.get("Target location"),
        )

    def _handle_end_state(self, resource, state_id, t, event):
        if resource is None:
            return
        product_id = event.get("Product")
        key = self._make_key(resource, state_id, product_id)
        oi = self._open.pop(key, None)
        if oi is None:
            # Fallback: try without product_id for interface states
            fallback_key = self._make_key(resource, state_id, None)
            oi = self._open.pop(fallback_key, None)
            if oi is None:
                return
        process_ok = event.get("process_ok", True)
        self._emit(oi, t, interrupted=False, process_ok=process_ok)

    def _handle_start_interrupt(self, resource, state_id, t, product_id=None):
        if resource is None:
            return
        key = self._make_key(resource, state_id, product_id)
        oi = self._open.pop(key, None)
        if oi is None:
            # Fallback: try without product_id
            fallback_key = self._make_key(resource, state_id, None)
            oi = self._open.pop(fallback_key, None)
            if oi is None:
                return
            key = fallback_key
        self._emit(oi, t, interrupted=True, process_ok=None)
        if key not in self._suspended:
            self._suspended[key] = []
        self._suspended[key].append(_OpenInterval(
            t_start=t,
            entity_id=oi.entity_id,
            entity_kind=oi.entity_kind,
            state_type=oi.state_type,
            state_id=oi.state_id,
            product_id=oi.product_id,
            product_type=oi.product_type,
            origin_location=oi.origin_location,
            target_location=oi.target_location,
        ))

    def _handle_end_interrupt(self, resource, state_id, t, product_id, product_type, event):
        if resource is None:
            return
        key = self._make_key(resource, state_id, product_id)
        stack = self._suspended.get(key)
        if not stack:
            # Fallback: try without product_id
            fallback_key = self._make_key(resource, state_id, None)
            stack = self._suspended.get(fallback_key)
            if not stack:
                return
            key = fallback_key
        oi = stack.pop()
        if not stack:
            del self._suspended[key]
        oi.t_start = t
        self._open[key] = oi

    # ── Product lifecycle ────────────────────────────────────────────────

    def _handle_created_product(self, resource, t, product_id, product_type, event):
        if not product_id:
            return
        self._product_creation[product_id] = (t, product_type)
        self._closed.append({
            "entity_id": product_id,
            "entity_kind": "product",
            "state_type": "created_product",
            "state_id": "",
            "t_start": t, "t_end": t, "duration": 0.0,
            "product_id": product_id,
            "product_type": product_type,
            "process_ok": True, "interrupted": False,
            "origin_location": None, "target_location": None,
            "resource": resource,
        })

    def _handle_finished_product(self, resource, t, product_id, product_type, event):
        if not product_id:
            return
        creation = self._product_creation.pop(product_id, None)
        if creation is not None:
            created_time, pt = creation
            self._closed.append({
                "entity_id": product_id,
                "entity_kind": "product",
                "state_type": "in_system",
                "state_id": "",
                "t_start": created_time, "t_end": t,
                "duration": t - created_time,
                "product_id": product_id,
                "product_type": pt or product_type,
                "process_ok": True, "interrupted": False,
                "origin_location": None, "target_location": None,
                "resource": None,
            })
        self._closed.append({
            "entity_id": product_id,
            "entity_kind": "product",
            "state_type": "finished_product",
            "state_id": "",
            "t_start": t, "t_end": t, "duration": 0.0,
            "product_id": product_id,
            "product_type": product_type,
            "process_ok": True, "interrupted": False,
            "origin_location": None, "target_location": None,
            "resource": resource,
        })

    def _handle_consumed_product(self, resource, t, product_id, product_type, event):
        if not product_id:
            return
        creation = self._product_creation.pop(product_id, None)
        if creation is not None:
            created_time, pt = creation
            self._closed.append({
                "entity_id": product_id,
                "entity_kind": "product",
                "state_type": "in_system",
                "state_id": "",
                "t_start": created_time, "t_end": t,
                "duration": t - created_time,
                "product_id": product_id,
                "product_type": pt or product_type,
                "process_ok": True, "interrupted": False,
                "origin_location": None, "target_location": None,
                "resource": None,
            })
        self._closed.append({
            "entity_id": product_id,
            "entity_kind": "product",
            "state_type": "consumed_product",
            "state_id": "",
            "t_start": t, "t_end": t, "duration": 0.0,
            "product_id": product_id,
            "product_type": product_type,
            "process_ok": True, "interrupted": False,
            "origin_location": None, "target_location": None,
            "resource": resource,
        })

    # ── Emit / drain ─────────────────────────────────────────────────────

    def _emit(self, oi: _OpenInterval, t_end: float, interrupted: bool, process_ok=True):
        duration = t_end - oi.t_start
        if duration < 0:
            duration = 0.0
        self._closed.append({
            "entity_id": oi.entity_id,
            "entity_kind": oi.entity_kind,
            "state_type": oi.state_type,
            "state_id": oi.state_id,
            "t_start": oi.t_start,
            "t_end": t_end,
            "duration": duration,
            "product_id": oi.product_id,
            "product_type": oi.product_type,
            "process_ok": process_ok,
            "interrupted": interrupted,
            "origin_location": oi.origin_location,
            "target_location": oi.target_location,
            "resource": oi.entity_id,
        })

    def drain(self) -> pd.DataFrame:
        """Return closed intervals and clear the buffer. Open intervals remain."""
        if not self._closed:
            return pd.DataFrame(columns=INTERVAL_COLUMNS)
        df = pd.DataFrame(self._closed, columns=INTERVAL_COLUMNS)
        self._closed.clear()
        return df

    def snapshot_open(self, t_now: float) -> pd.DataFrame:
        """Materialize currently-open intervals with t_end=t_now for live queries."""
        rows = []
        for _key, oi in self._open.items():
            duration = max(0.0, t_now - oi.t_start)
            rows.append({
                "entity_id": oi.entity_id,
                "entity_kind": oi.entity_kind,
                "state_type": oi.state_type,
                "state_id": oi.state_id,
                "t_start": oi.t_start,
                "t_end": t_now,
                "duration": duration,
                "product_id": oi.product_id,
                "product_type": oi.product_type,
                "process_ok": True,
                "interrupted": False,
                "origin_location": oi.origin_location,
                "target_location": oi.target_location,
                "resource": oi.entity_id,
            })
        if not rows:
            return pd.DataFrame(columns=INTERVAL_COLUMNS)
        return pd.DataFrame(rows, columns=INTERVAL_COLUMNS)

    @property
    def num_open(self) -> int:
        return len(self._open)

    @property
    def num_suspended(self) -> int:
        return sum(len(v) for v in self._suspended.values())

    @property
    def num_pending_products(self) -> int:
        return len(self._product_creation)
