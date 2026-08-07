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


def test_scheduled_control_policy_skips_completed_schedule_indices():
    """Later visits of the same product+process must not rematch consumed indices."""
    schedule = [
        performance_data.Event(
            time=0.0,
            resource="tr",
            state="tp",
            state_type="Production",
            activity="start state",
            product="p1",
            process="tp",
        ),
        performance_data.Event(
            time=5.0,
            resource="tr",
            state="tp",
            state_type="Production",
            activity="start state",
            product="p1",
            process="tp",
        ),
    ]
    policy = get_scheduled_control_policy(schedule, fallback_policy=lambda reqs: None)
    controller = SimpleNamespace(completed_schedule_indices={0})
    resource = SimpleNamespace(controller=controller)

    class _Req:
        def __init__(self):
            self.request_type = request_module.RequestType.TRANSPORT
            self.entity = SimpleNamespace(data=SimpleNamespace(ID="p1"))
            self.process = SimpleNamespace(data=SimpleNamespace(ID="tp"))
            self.resource = resource
            self.scheduled_control_index = None
            self.scheduled_start_time = None
            self.matched_schedule_event = None

    req = _Req()
    policy([req])
    assert req.scheduled_control_index == 1
    assert req.scheduled_start_time == 5.0


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


class _FakeSetupRequest:
    """Stand-in for SETUP changeover requests."""

    def __init__(self, product_id: str, setup_state_id: str, target_process_id: str = "p2"):
        self.request_type = request_module.RequestType.SETUP
        self.entity = SimpleNamespace(data=SimpleNamespace(ID=product_id))
        self.process = SimpleNamespace(data=SimpleNamespace(ID=target_process_id))
        self.setup_state_id = setup_state_id
        self.scheduled_control_index = None
        self.scheduled_start_time = None
        self.matched_schedule_event = None


def test_scheduled_control_policy_matches_setup_before_production():
    schedule = [
        performance_data.Event(
            time=4.0,
            resource="machine",
            state="S1",
            state_type="Setup",
            activity="start state",
            product="product2_1",
            process="S1",
        ),
        performance_data.Event(
            time=14.0,
            resource="machine",
            state="p2",
            state_type="Production",
            activity="start state",
            product="product2_1",
            process="p2",
        ),
    ]
    policy = get_scheduled_control_policy(schedule, fallback_policy=lambda reqs: None)
    setup_req = _FakeSetupRequest("product2_1", "S1")
    prod_req = _make_request("product2_1", "p2")
    requests = [prod_req, setup_req]
    policy(requests)
    assert requests[0] is setup_req
    assert requests[1] is prod_req
    assert setup_req.scheduled_start_time == 4.0
    assert prod_req.scheduled_start_time == 14.0


def test_scheduled_control_policy_setup_fallback_when_unmatched():
    schedule = [
        _make_event("other", "p2"),
    ]
    fallback_order = []

    def fallback(reqs):
        # Prefer production over unmatched setup
        reqs.sort(key=lambda r: 0 if getattr(r, "request_type", None) is None else 1)
        fallback_order.append([getattr(r, "setup_state_id", None) or r.process.data.ID for r in reqs])

    policy = get_scheduled_control_policy(schedule, fallback_policy=fallback)
    setup_req = _FakeSetupRequest("product2_1", "S1")
    prod_req = _make_request("other", "p2")
    requests = [setup_req, prod_req]
    policy(requests)
    # Matched production first, unmatched setup after (same fallback pattern)
    assert requests[0] is prod_req
    assert requests[1] is setup_req
    assert prod_req.scheduled_start_time == 0.0
    assert setup_req.scheduled_start_time is None


def test_schedule_matches_index_avoids_full_scan():
    key = ("p1", "proc")
    matches = {key: [0, 5, 10]}
    requests = [_make_request("p1", "proc")]
    control.scheduled_control_policy(matches, {}, [], lambda r: None, requests)
    assert len(requests) == 1


def _controller_with_setup(current_process_id: str | None):
    controller = control.Controller(
        control_policy=lambda reqs: None,
        env=SimpleNamespace(),
        lot_handler=SimpleNamespace(),
    )
    if current_process_id is None:
        controller.resource = SimpleNamespace(
            reserved_setup=None,
            current_setup=None,
        )
    else:
        setup = SimpleNamespace(data=SimpleNamespace(ID=current_process_id))
        controller.resource = SimpleNamespace(
            reserved_setup=None,
            current_setup=setup,
        )
    return controller


class _FakeProductionRequest:
    def __init__(self, product_id: str, process_id: str):
        self.request_type = request_module.RequestType.PRODUCTION
        self.entity = SimpleNamespace(data=SimpleNamespace(ID=product_id))
        self.process = SimpleNamespace(data=SimpleNamespace(ID=process_id))
        self.scheduled_control_index = None


def test_request_dependencies_is_idempotent():
    """Production may call request_dependencies twice; second call is a no-op."""
    import simpy

    env = simpy.Environment()
    item = SimpleNamespace(env=env)
    dep = SimpleNamespace(data=SimpleNamespace(ID="d1"))
    req = request_module.Request(
        request_type=request_module.RequestType.PRODUCTION,
        process=SimpleNamespace(data=SimpleNamespace(ID="p2")),
        requesting_item=item,
        entity=SimpleNamespace(data=SimpleNamespace(ID="prod"), size=1, type="product"),
        required_dependencies=[dep],
    )
    first = req.request_dependencies()
    assert req.dependencies_requested.triggered
    assert first is req.dependencies_ready
    # Simulate router fulfilling deps
    req.dependencies_ready.succeed()
    second = req.request_dependencies()
    assert second is req.dependencies_ready
    assert second.triggered


def test_attendance_dependencies_have_free_resource_respects_bound():
    from prodsys.models.dependency_data import DependencyType
    from prodsys.simulation.process_handlers.setup_process_handler import (
        attendance_dependencies_have_free_resource,
    )

    machine = object()
    free_worker = SimpleNamespace(bound=False, full=False, controller=SimpleNamespace(num_running_processes=0), current_dependant=None)
    busy_worker = SimpleNamespace(bound=True, full=False, controller=SimpleNamespace(num_running_processes=1), current_dependant=object())
    attending_worker = SimpleNamespace(
        bound=True,
        full=False,
        controller=SimpleNamespace(num_running_processes=1),
        current_dependant=machine,
    )
    dep = SimpleNamespace(
        data=SimpleNamespace(dependency_type=DependencyType.PROCESS),
        required_process=SimpleNamespace(data=SimpleNamespace(ID="assembly_process")),
    )

    class _Matcher:
        def __init__(self, resources):
            self._resources = resources

        def get_compatible(self, _processes):
            return [(r, None) for r in self._resources]

    assert attendance_dependencies_have_free_resource([dep], _Matcher([free_worker]))
    assert not attendance_dependencies_have_free_resource([dep], _Matcher([busy_worker]))
    assert attendance_dependencies_have_free_resource(
        [dep], _Matcher([busy_worker, free_worker])
    )
    # Already attending at this machine is usable for setup (avoids deadlock).
    assert attendance_dependencies_have_free_resource(
        [dep], _Matcher([attending_worker]), requiring_machine=machine
    )
    assert not attendance_dependencies_have_free_resource(
        [dep], _Matcher([attending_worker]), requiring_machine=object()
    )


def test_setup_handler_does_not_request_on_site_dependencies():
    """Setup waits for free workers but must not succeed dependencies_requested."""
    import simpy

    from prodsys.models.dependency_data import DependencyType
    from prodsys.simulation.process_handlers.setup_process_handler import (
        SetupProcessHandler,
    )

    env = simpy.Environment()
    worker = SimpleNamespace(
        bound=False,
        full=False,
        controller=SimpleNamespace(num_running_processes=0, state_changed=simpy.Event(env)),
    )
    process = SimpleNamespace(data=SimpleNamespace(ID="p2"))
    dep = SimpleNamespace(
        data=SimpleNamespace(dependency_type=DependencyType.PROCESS, ID="assembly_dependency"),
        required_process=SimpleNamespace(data=SimpleNamespace(ID="assembly_process")),
    )

    class _Matcher:
        def get_compatible(self, _processes):
            return [(worker, None)]

    router = SimpleNamespace(
        request_handler=SimpleNamespace(process_matcher=_Matcher())
    )
    product = SimpleNamespace(env=env, router=router, data=SimpleNamespace(ID="product2_0"))
    parent = request_module.Request(
        request_type=request_module.RequestType.PRODUCTION,
        process=process,
        requesting_item=product,
        entity=SimpleNamespace(data=SimpleNamespace(ID="product2_0"), size=1),
        required_dependencies=[dep],
    )
    setup_state = SimpleNamespace(
        data=SimpleNamespace(ID="S1", origin_setup="p1", target_setup="p2"),
        state_info=SimpleNamespace(log_product=lambda *a, **k: None),
    )

    class _SetupGen:
        def __iter__(self):
            return iter(())

    resource = SimpleNamespace(
        setup_states=[setup_state],
        controller=SimpleNamespace(
            mark_started_process=lambda *a, **k: None,
            mark_finished_process=lambda *a, **k: None,
            strict_schedule_timing=False,
        ),
        setup=lambda _p: _SetupGen(),
    )
    setup_req = request_module.Request(
        request_type=request_module.RequestType.SETUP,
        process=process,
        resource=resource,
        requesting_item=product,
        entity=parent.entity,
        setup_state_id="S1",
        required_dependencies=[dep],
        parent_production_request=parent,
        completed=simpy.Event(env),
    )

    handler = SetupProcessHandler(env)
    env.process(handler.handle_request(setup_req))
    env.run()
    assert not parent.dependencies_requested.triggered
    assert setup_req.completed.triggered


def test_maybe_create_setup_request_links_parent_and_deps():
    import simpy

    controller = _controller_with_setup("p1")
    controller.resource_schedule = [
        performance_data.Event(
            time=0.0,
            resource="machine2",
            state="S1",
            state_type="Setup",
            activity="start state",
            product="product2_1",
            process="S1",
        ),
    ]
    setup_state = SimpleNamespace(
        data=SimpleNamespace(ID="S1", origin_setup="p1", target_setup="p2")
    )
    process = SimpleNamespace(data=SimpleNamespace(ID="p2"))
    resource = SimpleNamespace(
        reserved_setup=SimpleNamespace(data=SimpleNamespace(ID="p1")),
        current_setup=None,
        setup_states=[setup_state],
    )
    env = simpy.Environment()
    dep = SimpleNamespace(data=SimpleNamespace(ID="assembly_dependency"))
    parent = request_module.Request(
        request_type=request_module.RequestType.PRODUCTION,
        process=process,
        resource=resource,
        requesting_item=SimpleNamespace(env=env),
        entity=SimpleNamespace(data=SimpleNamespace(ID="product2_1"), size=1),
        required_dependencies=[dep],
    )

    setup_req = controller._maybe_create_setup_request(parent)
    assert setup_req is not None
    assert setup_req.request_type == request_module.RequestType.SETUP
    assert setup_req.setup_state_id == "S1"
    assert setup_req.parent_production_request is parent
    assert setup_req.required_dependencies == [dep]


def test_schedule_next_event_blocks_same_setup_affinity_jump():
    """Same-setup work for product B must not jump ahead of scheduled Setup for A.

    Regression: capacity>1 + ResourceDependency — product3_8 (p2) stole worker2
    while machine2 still owed S2 for product3_9.
    """
    controller = _controller_with_setup("p2")
    controller.resource_schedule = [
        performance_data.Event(
            time=2.0,
            resource="machine2",
            state="p2",
            state_type="Production",
            activity="start state",
            product="product2_2",
            process="p2",
        ),
        performance_data.Event(
            time=4.0,
            resource="machine2",
            state="S2",
            state_type="Setup",
            activity="start state",
            product="product3_9",
            process="S2",
        ),
        performance_data.Event(
            time=14.0,
            resource="machine2",
            state="p1",
            state_type="Production",
            activity="start state",
            product="product3_9",
            process="p1",
        ),
        performance_data.Event(
            time=23.0,
            resource="machine2",
            state="S1",
            state_type="Setup",
            activity="start state",
            product="product3_8",
            process="S1",
        ),
        performance_data.Event(
            time=33.0,
            resource="machine2",
            state="p2",
            state_type="Production",
            activity="start state",
            product="product3_8",
            process="p2",
        ),
    ]
    # product2_2 done → next event is S2 for product3_9
    controller.completed_schedule_indices = {0}
    early_same_setup = _FakeProductionRequest("product3_8", "p2")
    next_setup_prod = _FakeProductionRequest("product3_9", "p1")
    next_setup = _FakeSetupRequest("product3_9", "S2", "p1")

    assert controller._schedule_next_event_blocks_request(early_same_setup)
    assert not controller._schedule_next_event_blocks_request(next_setup_prod)
    assert not controller._schedule_next_event_blocks_request(next_setup)
    # Foreign same-setup in queue must not affinity-block the scheduled changeover
    assert not controller.changeover_blocked(
        next_setup, [early_same_setup, next_setup_prod], lambda r: True
    )


def test_setup_affinity_prefers_current_setup_over_changeover():
    """Queue has p1 and p2; current_setup=p1 → affinity keeps p1, blocks changeover."""
    controller = _controller_with_setup("p1")
    p1 = _FakeProductionRequest("product1_0", "p1")
    p2 = _FakeProductionRequest("product2_0", "p2")
    assert controller._request_matches_current_setup(p1)
    assert controller._request_needs_changeover(p2)
    assert controller.changeover_blocked(p2, [p1, p2], lambda r: True)
    assert not controller.changeover_blocked(p1, [p1, p2], lambda r: True)


def test_schedule_prefix_blocks_setup_while_earlier_same_setup_open():
    """Schedule [p1_a, p1_b, S1(p2), p2]; only p2 in queue → Setup deferred."""
    controller = _controller_with_setup("p1")
    controller.resource_schedule = [
        performance_data.Event(
            time=0.0,
            resource="machine2",
            state="p1",
            state_type="Production",
            activity="start state",
            product="product1_0",
            process="p1",
        ),
        performance_data.Event(
            time=1.0,
            resource="machine2",
            state="p1",
            state_type="Production",
            activity="start state",
            product="product1_1",
            process="p1",
        ),
        performance_data.Event(
            time=2.0,
            resource="machine2",
            state="S1",
            state_type="Setup",
            activity="start state",
            product="product2_0",
            process="S1",
        ),
        performance_data.Event(
            time=12.0,
            resource="machine2",
            state="p2",
            state_type="Production",
            activity="start state",
            product="product2_0",
            process="p2",
        ),
    ]
    setup_req = _FakeSetupRequest("product2_0", "S1", "p2")
    setup_req.scheduled_control_index = 2
    assert controller._schedule_prefix_blocks_changeover(setup_req)

    # After marking earlier p1 productions done, Setup is allowed.
    controller.completed_schedule_indices = {0, 1}
    assert not controller._schedule_prefix_blocks_changeover(setup_req)
    # With a schedule + matching Setup state, opportunistic changeovers are
    # disabled — SETUP requests carry the planned start time instead.
    setup_state = SimpleNamespace(
        data=SimpleNamespace(ID="S1", origin_setup="p1", target_setup="p2")
    )
    prod = _FakeProductionRequest("product2_0", "p2")
    prod.resource = SimpleNamespace(
        reserved_setup=None,
        current_setup=SimpleNamespace(data=SimpleNamespace(ID="p1")),
        setup_states=[setup_state],
    )
    assert not controller.should_allow_opportunistic_setup(prod)


def test_opportunistic_setup_allowed_without_setup_states():
    """Schedule alone must not block soft changeovers on resources without Setups."""
    controller = _controller_with_setup("p_assembly")
    controller.resource_schedule = [
        performance_data.Event(
            time=0.0,
            resource="ws2",
            state="p_assembly",
            state_type="Production",
            activity="start state",
            product="product_b_1",
            process="p_assembly",
        ),
        performance_data.Event(
            time=1.0,
            resource="ws2",
            state="p_finish",
            state_type="Production",
            activity="start state",
            product="product_b_1",
            process="p_finish",
        ),
    ]
    controller.completed_schedule_indices = {0}
    prod = _FakeProductionRequest("product_b_1", "p_finish")
    prod.resource = SimpleNamespace(
        reserved_setup=None,
        current_setup=SimpleNamespace(data=SimpleNamespace(ID="p_assembly")),
        setup_states=[],
    )
    assert controller.should_allow_opportunistic_setup(prod)


def test_scheduled_setup_not_allowed_opportunistically_while_early():
    """Even after prefix is free, opportunistic setup stays off when scheduled."""
    import simpy

    controller = _controller_with_setup("p1")
    controller.resource_schedule = [
        performance_data.Event(
            time=0.0,
            resource="m",
            state="p1",
            state_type="Production",
            activity="start state",
            product="a",
            process="p1",
        ),
        performance_data.Event(
            time=10.0,
            resource="m",
            state="S1",
            state_type="Setup",
            activity="start state",
            product="product2_0",
            process="S1",
        ),
        performance_data.Event(
            time=20.0,
            resource="m",
            state="p2",
            state_type="Production",
            activity="start state",
            product="product2_0",
            process="p2",
        ),
    ]
    controller.completed_schedule_indices = {0}
    setup_state = SimpleNamespace(
        data=SimpleNamespace(ID="S1", origin_setup="p1", target_setup="p2")
    )
    process = SimpleNamespace(data=SimpleNamespace(ID="p2"))
    resource = SimpleNamespace(
        reserved_setup=SimpleNamespace(data=SimpleNamespace(ID="p1")),
        current_setup=None,
        setup_states=[setup_state],
    )
    env = simpy.Environment()
    prod = request_module.Request(
        request_type=request_module.RequestType.PRODUCTION,
        process=process,
        resource=resource,
        requesting_item=SimpleNamespace(env=env),
        entity=SimpleNamespace(data=SimpleNamespace(ID="product2_0"), size=1),
    )
    assert not controller.should_allow_opportunistic_setup(prod)
    setup = controller._maybe_create_setup_request(prod)
    assert setup is not None
    assert setup.scheduled_start_time == 10.0
    assert setup.scheduled_control_index == 1


def test_schedule_prefix_releases_after_prefix_consumed():
    controller = _controller_with_setup("p1")
    controller.resource_schedule = [
        performance_data.Event(
            time=0.0,
            resource="m",
            state="p1",
            state_type="Production",
            activity="start state",
            product="a",
            process="p1",
        ),
        performance_data.Event(
            time=1.0,
            resource="m",
            state="S1",
            state_type="Setup",
            activity="start state",
            product="b",
            process="S1",
        ),
    ]
    setup_req = _FakeSetupRequest("b", "S1", "p2")
    setup_req.scheduled_control_index = 1
    assert controller.changeover_blocked(setup_req)
    # Marking happens when the process actually starts (via mark_started_process).
    controller.reserved_requests_count = 1
    controller.resource.update_idle_logging = lambda: None
    controller.mark_started_process(
        1, SimpleNamespace(scheduled_control_index=0)
    )
    assert not controller.changeover_blocked(setup_req)


def test_mark_started_process_consumes_schedule_index():
    controller = _controller_with_setup("p1")
    controller.reserved_requests_count = 1
    controller.resource.update_idle_logging = lambda: None
    assert controller.completed_schedule_indices == set()
    controller.mark_started_process(
        1, SimpleNamespace(scheduled_control_index=2)
    )
    assert controller.completed_schedule_indices == {2}

def test_maybe_inject_scheduled_setup_before_product_arrives():
    """Plan setups that start before inbound transport must be injectable without a production request."""
    import simpy
    from simpy import events

    controller = _controller_with_setup("p2")
    env = simpy.Environment()
    controller.env = env
    controller.state_changed = events.Event(env)
    setup_state = SimpleNamespace(
        data=SimpleNamespace(ID="S2", origin_setup="p2", target_setup="p1")
    )
    p1 = SimpleNamespace(data=SimpleNamespace(ID="p1"))
    controller.resource = SimpleNamespace(
        reserved_setup=None,
        current_setup=SimpleNamespace(data=SimpleNamespace(ID="p2")),
        setup_states=[setup_state],
        processes=[p1],
        dependencies=[],
        in_setup=False,
        bound=False,
        full=False,
    )
    controller.resource_schedule = [
        performance_data.Event(
            time=84.467,
            resource="machine2",
            state="S2",
            state_type="Setup",
            activity="start state",
            product="product1_2",
            process="S2",
        ),
        performance_data.Event(
            time=94.467,
            resource="machine2",
            state="p1",
            state_type="Production",
            activity="start state",
            product="product1_2",
            process="p1",
        ),
    ]
    assert controller.requests == []
    assert controller._maybe_inject_scheduled_setup()
    assert len(controller.requests) == 1
    setup_req = controller.requests[0]
    assert setup_req.request_type == request_module.RequestType.SETUP
    assert setup_req.setup_state_id == "S2"
    assert setup_req.scheduled_start_time == 84.467
    assert setup_req.scheduled_control_index == 0
    # Idempotent while pending
    assert not controller._maybe_inject_scheduled_setup()
    assert len(controller.requests) == 1


def test_maybe_create_setup_request_adopts_ahead_of_product_setup():
    import simpy
    from simpy import events

    controller = _controller_with_setup("p2")
    env = simpy.Environment()
    controller.env = env
    controller.state_changed = events.Event(env)
    setup_state = SimpleNamespace(
        data=SimpleNamespace(ID="S2", origin_setup="p2", target_setup="p1")
    )
    p1 = SimpleNamespace(data=SimpleNamespace(ID="p1"))
    resource = SimpleNamespace(
        reserved_setup=None,
        current_setup=SimpleNamespace(data=SimpleNamespace(ID="p2")),
        setup_states=[setup_state],
        processes=[p1],
        dependencies=[SimpleNamespace(data=SimpleNamespace(ID="dep_resource"))],
        in_setup=False,
        bound=False,
        full=False,
    )
    controller.resource = resource
    controller.resource_schedule = [
        performance_data.Event(
            time=10.0,
            resource="m",
            state="S2",
            state_type="Setup",
            activity="start state",
            product="product1_2",
            process="S2",
        ),
    ]
    assert controller._maybe_inject_scheduled_setup()
    early = controller.requests[0]

    env = simpy.Environment()
    dep = SimpleNamespace(data=SimpleNamespace(ID="resource_2_dependency"))
    parent = request_module.Request(
        request_type=request_module.RequestType.PRODUCTION,
        process=p1,
        resource=resource,
        requesting_item=SimpleNamespace(env=env),
        entity=SimpleNamespace(data=SimpleNamespace(ID="product1_2"), size=1),
        required_dependencies=[dep],
    )
    adopted = controller._maybe_create_setup_request(parent)
    assert adopted is early
    assert parent._setup_injected is True
    assert early.parent_production_request is parent
    assert early.required_dependencies == [dep]
