"""Tests for schedule-indexed control policy matching."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from prodsys.factories.resource_factory import get_scheduled_control_policy
from prodsys.models import performance_data
from prodsys.simulation import control


class _FakeRequest:
    """Hashable stand-in for :class:`prodsys.simulation.request.Request`."""

    def __init__(self, product_id: str, process_id: str):
        self.entity = SimpleNamespace(data=SimpleNamespace(ID=product_id))
        self.process = SimpleNamespace(data=SimpleNamespace(ID=process_id))


def _make_request(product_id: str, process_id: str) -> _FakeRequest:
    return _FakeRequest(product_id, process_id)


def _make_event(product: str, process: str, resource: str = "r1"):
    return performance_data.Event(
        time=0.0,
        resource=resource,
        state=process,
        state_type="Production",
        activity="start state",
        product=product,
        process=process,
    )


def test_scheduled_control_policy_sorts_by_schedule_index():
    schedule = [
        _make_event("p_b", "proc"),
        _make_event("p_a", "proc"),
        _make_event("p_b", "proc"),
    ]
    policy = get_scheduled_control_policy(schedule, fallback_policy=lambda reqs: None)
    requests = [
        _make_request("p_b", "proc"),
        _make_request("p_a", "proc"),
    ]
    policy(requests)
    assert [r.entity.data.ID for r in requests] == ["p_b", "p_a"]


def test_schedule_matches_index_avoids_full_scan():
    key = ("p1", "proc")
    matches = {key: [0, 5, 10]}
    requests = [_make_request("p1", "proc")]
    control.scheduled_control_policy(matches, lambda r: None, requests)
    assert len(requests) == 1
