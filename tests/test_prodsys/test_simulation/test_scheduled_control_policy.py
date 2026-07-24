"""Tests for schedule-indexed control policy matching."""

from __future__ import annotations

from types import SimpleNamespace

from prodsys.factories.resource_factory import get_scheduled_control_policy
from prodsys.models import performance_data
from prodsys.simulation import control, request as request_module


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


class _FakeDependencyRequest:
    """Stand-in for dependency attendance requests."""

    def __init__(
        self,
        product_id: str,
        dependency_id: str,
        requiring_resource_id: str,
    ):
        self.request_type = request_module.RequestType.PROCESS_DEPENDENCY
        self.entity = SimpleNamespace(data=SimpleNamespace(ID="machine"))
        self.process = SimpleNamespace(data=SimpleNamespace(ID="DependencyProcess"))
        self.dependent_product_id = product_id
        self.requiring_resource_id = requiring_resource_id
        self.resolved_dependency = SimpleNamespace(
            data=SimpleNamespace(ID=dependency_id)
        )
        self.scheduled_control_index = None
        self.scheduled_start_time = None
        self.matched_schedule_event = None


def test_scheduled_control_policy_orders_dependency_attendance():
    schedule = [
        performance_data.Event(
            time=1.0,
            resource="worker2",
            state="Dependency",
            state_type="Dependency",
            activity="start state",
            product="product3_0",
            dependency="assembly_dependency",
            requesting_item="machine",
        ),
        performance_data.Event(
            time=5.0,
            resource="worker2",
            state="Dependency",
            state_type="Dependency",
            activity="start state",
            product="product3_1",
            dependency="resource_2_dependency",
            requesting_item="machine2",
        ),
    ]
    policy = get_scheduled_control_policy(schedule, fallback_policy=lambda reqs: None)
    requests = [
        _FakeDependencyRequest("product3_1", "resource_2_dependency", "machine2"),
        _FakeDependencyRequest("product3_0", "assembly_dependency", "machine"),
    ]
    policy(requests)
    assert [r.dependent_product_id for r in requests] == ["product3_0", "product3_1"]
    assert requests[0].scheduled_start_time == 1.0
    assert requests[1].scheduled_start_time == 5.0


def test_controller_defaults_strict_schedule_timing_off():
    controller = control.Controller(
        control_policy=lambda reqs: None,
        env=SimpleNamespace(),
        lot_handler=SimpleNamespace(),
    )
    assert controller.strict_schedule_timing is False


def test_schedule_matches_index_avoids_full_scan():
    key = ("p1", "proc")
    matches = {key: [0, 5, 10]}
    requests = [_make_request("p1", "proc")]
    control.scheduled_control_policy(matches, {}, [], lambda r: None, requests)
    assert len(requests) == 1
