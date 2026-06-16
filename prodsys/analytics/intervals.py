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
import numpy as np

from prodsys.simulation.state import StateTypeEnum

import logging

logger = logging.getLogger(__name__)

INTERFACE_STATE_TYPES = frozenset({
    StateTypeEnum.source, StateTypeEnum.sink,
    StateTypeEnum.breakdown, StateTypeEnum.maintenance, StateTypeEnum.setup,
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

_PRIORITY_MAP = {
    ("finished product", False): 1,
    ("finished product", True): 1,
    ("created product", False): 2,
    ("created product", True): 2,
    ("consumed product", False): 2,
    ("consumed product", True): 2,
    ("end state", False): 3,
    ("end interrupt", True): 4,
    ("end state", True): 5,
    ("start state", True): 6,
    ("start interrupt", True): 7,
    ("start state", False): 8,
}

_PROCESS_STATE_CHECK_SET = (
    frozenset(PROCESS_STATE_TYPES)
    | frozenset(st.value for st in PROCESS_STATE_TYPES)
)


def _without_instant_state_pairs(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Drop same-timestamp start+end for ``breakdown_large`` (zero-duration MQTT flip-flop)."""
    if df_raw is None or df_raw.empty or "Activity" not in df_raw.columns:
        return df_raw

    activity = _decategorize(df_raw["Activity"]).fillna("")
    state_type = df_raw["State Type"].astype(str).str.lower()
    state = _decategorize(df_raw["State"]).fillna("").astype(str)
    state_mask = (
        activity.isin(["start state", "end state"])
        & state_type.isin({"breakdown", "ud"})
        & (state == "breakdown_large")
    )
    if not state_mask.any():
        return df_raw

    sub = df_raw.loc[state_mask, ["Resource", "State", "Time", "Activity"]].copy()
    starts = sub.groupby(["Resource", "State", "Time"])["Activity"].apply(
        lambda s: (s == "start state").any()
    )
    ends = sub.groupby(["Resource", "State", "Time"])["Activity"].apply(
        lambda s: (s == "end state").any()
    )
    instant_keys = set(starts[starts & ends].index)
    if not instant_keys:
        return df_raw

    def _is_instant(row: pd.Series) -> bool:
        if row["Activity"] not in ("start state", "end state"):
            return False
        if str(row.get("State Type", "")).lower() not in {"breakdown", "ud"}:
            return False
        if str(row.get("State", "")) != "breakdown_large":
            return False
        return (row.get("Resource"), row.get("State"), row.get("Time")) in instant_keys

    drop_mask = df_raw.apply(_is_instant, axis=1)
    if not drop_mask.any():
        return df_raw
    return df_raw.loc[~drop_mask].reset_index(drop=True)


def _decategorize(series: pd.Series) -> pd.Series:
    """Return ``series`` as plain ``object`` dtype if it is a Categorical.

    Categorical columns are an analytics-layer RAM optimisation; the interval
    state machine works on plain Python values and uses ``fillna`` with a value
    that need not be an existing category. Casting to ``object`` here keeps the
    ingest path dtype-agnostic without changing behaviour for non-categorical
    input (the same Series is returned untouched).
    """
    if isinstance(series.dtype, pd.CategoricalDtype):
        return series.astype(object)
    return series


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

    return (event.get("Time", 0.0), _PRIORITY_MAP.get((activity, is_process), 9))


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
        """Process a single raw event (dict-based public API)."""
        activity = event.get("Activity", "")
        resource = event.get("Resource")
        state_id = event.get("State", "")
        t = event.get("Time", 0.0)
        product_id = event.get("Product")
        if isinstance(product_id, float) and product_id != product_id:
            product_id = None
        product_type = self.derive_product_type(product_id)

        if activity == "start state":
            self._handle_start_state(
                resource, state_id, t, product_id, product_type,
                event.get("State Type", ""),
                event.get("Origin location"),
                event.get("Target location"),
            )
        elif activity == "end state":
            self._handle_end_state(resource, state_id, t, product_id,
                                   event.get("process_ok", True))
        elif activity == "start interrupt":
            self._handle_start_interrupt(resource, state_id, t, product_id)
        elif activity == "end interrupt":
            self._handle_end_interrupt(resource, state_id, t, product_id, product_type)
        elif activity == "created product":
            self._handle_created_product(resource, t, product_id, product_type)
        elif activity == "finished product":
            self._handle_finished_product(resource, t, product_id, product_type)
        elif activity == "consumed product":
            self._handle_consumed_product(resource, t, product_id, product_type)

    def ingest_dataframe(self, df_raw: pd.DataFrame) -> None:
        """
        Ingest a complete raw event DataFrame, sorting events correctly
        before feeding them to the state machine.
        """
        n = len(df_raw)
        if n == 0:
            return

        df_raw = _without_instant_state_pairs(df_raw)
        n = len(df_raw)
        if n == 0:
            return

        # ``Activity`` / ``State`` may arrive as pandas ``category`` dtype when the
        # caller categoricalises the event log to save RAM. ``Series.fillna("")``
        # raises on a Categorical unless ``""`` is already a category, and
        # ``.values`` yields a Categorical (not an ndarray). Decategorise the two
        # text columns we ``fillna`` here so the rest of the routine is dtype-
        # agnostic. Behaviour is identical for plain ``object`` input.
        activity_series = _decategorize(df_raw["Activity"]).fillna("")
        state_series = _decategorize(df_raw["State"]).fillna("")

        # Vectorized sort: compute priorities via numpy instead of
        # per-element Python sort key (avoids 467K _event_sort_key calls).
        act_arr = activity_series.values
        time_arr = df_raw["Time"].fillna(0.0).values
        is_process = df_raw["State Type"].isin(_PROCESS_STATE_CHECK_SET).values

        priorities = np.full(n, 9, dtype=np.int8)
        for (act, ip), prio in _PRIORITY_MAP.items():
            mask = (act_arr == act) & (is_process == ip)
            priorities[mask] = prio

        order = np.lexsort((priorities, time_arr)).tolist()

        # Pre-extract columns as Python lists (avoids to_dict boxing).
        activities = activity_series.tolist()
        times = time_arr.tolist()
        resources = df_raw["Resource"].tolist()
        state_ids = state_series.tolist()
        products = df_raw["Product"].tolist()
        state_types = df_raw["State Type"].tolist()

        pok = df_raw["process_ok"].tolist() if "process_ok" in df_raw.columns else None
        ori = df_raw["Origin location"].tolist() if "Origin location" in df_raw.columns else None
        tgt = df_raw["Target location"].tolist() if "Target location" in df_raw.columns else None

        # Precompute: clean NaN product IDs and derive product types once,
        # avoiding 467K derive_product_type + NaN-check calls inside feed().
        product_types = [None] * n
        for i in range(n):
            p = products[i]
            if p is None:
                pass
            elif isinstance(p, float) and p != p:
                products[i] = None
            else:
                p_str = str(p) if not isinstance(p, str) else p
                parts = p_str.rsplit("_", 1)
                product_types[i] = parts[0] if len(parts) == 2 and parts[1].isdigit() else p_str

        # Direct dispatch — bypasses dict construction (0.17s) and
        # 3.5M dict.get calls (0.18s) that feed() would incur.
        _start = self._handle_start_state
        _end = self._handle_end_state
        _si = self._handle_start_interrupt
        _ei = self._handle_end_interrupt
        _cp = self._handle_created_product
        _fp = self._handle_finished_product
        _consumed = self._handle_consumed_product

        for idx in order:
            act = activities[idx]
            if act == "start state":
                _start(resources[idx], state_ids[idx], times[idx],
                       products[idx], product_types[idx], state_types[idx],
                       ori[idx] if ori is not None else None,
                       tgt[idx] if tgt is not None else None)
            elif act == "end state":
                _end(resources[idx], state_ids[idx], times[idx],
                     products[idx],
                     pok[idx] if pok is not None else True)
            elif act == "start interrupt":
                _si(resources[idx], state_ids[idx], times[idx], products[idx])
            elif act == "end interrupt":
                _ei(resources[idx], state_ids[idx], times[idx],
                    products[idx], product_types[idx])
            elif act == "created product":
                _cp(resources[idx], times[idx], products[idx], product_types[idx])
            elif act == "finished product":
                _fp(resources[idx], times[idx], products[idx], product_types[idx])
            elif act == "consumed product":
                _consumed(resources[idx], times[idx], products[idx], product_types[idx])

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

    def _handle_start_state(self, resource, state_id, t, product_id, product_type,
                            state_type_raw, origin_location, target_location):
        if resource is None:
            return
        key = self._make_key(resource, state_id, product_id)
        # if key in self._open:
        #     logger.debug("Overwriting open interval for %s (defensive)", key)
        state_type = self._normalize_state_type(state_type_raw)
        self._open[key] = _OpenInterval(
            t_start=t,
            entity_id=resource,
            entity_kind="resource",
            state_type=state_type,
            state_id=state_id,
            product_id=product_id,
            product_type=product_type,
            origin_location=origin_location,
            target_location=target_location,
        )

    def _handle_end_state(self, resource, state_id, t, product_id, process_ok=True):
        if resource is None:
            return
        key = self._make_key(resource, state_id, product_id)
        oi = self._open.pop(key, None)
        if oi is None:
            fallback_key = self._make_key(resource, state_id, None)
            oi = self._open.pop(fallback_key, None)
            if oi is None:
                return
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

    def _handle_end_interrupt(self, resource, state_id, t, product_id, product_type):
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

    def _handle_created_product(self, resource, t, product_id, product_type):
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

    def _handle_finished_product(self, resource, t, product_id, product_type):
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

    def _handle_consumed_product(self, resource, t, product_id, product_type):
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
