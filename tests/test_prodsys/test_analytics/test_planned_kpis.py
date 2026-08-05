"""Tests for schedule-derived planned KPI trajectories."""

import pytest
import prodsys.express as psx
from prodsys.analytics.store import (
    AnalyticsStore,
    _order_id_from_product,
    _resolve_order_id_for_product,
)
from prodsys.models.order_data import OrderData, OrderedProductData
from prodsys.models.performance_data import Event
from prodsys.models.production_system_data import ProductionSystemData
from prodsys.util.post_processing import PostProcessor


@pytest.fixture
def system_with_valid_schedule() -> ProductionSystemData:
    t1 = psx.FunctionTimeModel("constant", 5.0, 0, "t1")
    p1 = psx.ProductionProcess(t1, "P1")

    t_transport = psx.FunctionTimeModel("constant", 0.5, 0, ID="t_transport")
    tp = psx.TransportProcess(t_transport, "TP")

    resource = psx.Resource([p1], [10, 0], 1, ID="R1")
    transport = psx.Resource([tp], [5, 0], 1, ID="AGV1")

    product = psx.Product([p1], tp, "Product_A")

    sink = psx.Sink(product, [20, 0], "Sink")

    arrival_model = psx.FunctionTimeModel("constant", 10.0, ID="arrival_model")
    source = psx.Source(product, arrival_model, [0, 0], ID="Source")

    system = psx.ProductionSystem([resource, transport], [source], [sink]).to_model()
    system.schedule = [
        Event(
            time=0.0,
            resource="R1",
            state="P1",
            state_type="Production",
            activity="start state",
            product="Product_A_1",
            expected_end_time=5.0,
            process="P1",
        ),
        Event(
            time=10.0,
            resource="R1",
            state="P1",
            state_type="Production",
            activity="start state",
            product="Product_A_2",
            expected_end_time=15.0,
            process="P1",
        ),
        Event(
            time=20.0,
            resource="R1",
            state="P1",
            state_type="Production",
            activity="start state",
            product="Product_A_3",
            expected_end_time=25.0,
            process="P1",
        ),
    ]
    return system


def test_planned_wip_per_resource_from_schedule(system_with_valid_schedule):
    store = AnalyticsStore(production_system_data=system_with_valid_schedule)
    df = store.planned_wip_per_resource()

    r1 = df[df["WIP_resource"] == "R1"].reset_index(drop=True)
    assert list(r1["Time"]) == [0.0, 5.0, 10.0, 15.0, 20.0, 25.0]
    assert list(r1["WIP"]) == [1.0, 0.0, 1.0, 0.0, 1.0, 0.0]


def test_planned_wip_per_resource_excludes_setup_dependency_and_worker_move(
    system_with_valid_schedule,
):
    """Setup/Dependency/worker-move are not product-presence WIP."""
    system = system_with_valid_schedule.model_copy(deep=True)
    # Bypass schedule process-ID validation so we can inject Setup/move labels.
    system.__dict__["schedule"] = [
        Event(
            time=0.0,
            resource="R1",
            state="S1",
            state_type="Setup",
            activity="start state",
            product="Product_A_1",
            expected_end_time=10.0,
            process="S1",
        ),
        Event(
            time=10.0,
            resource="R1",
            state="P1",
            state_type="Production",
            activity="start state",
            product="Product_A_1",
            expected_end_time=15.0,
            process="P1",
        ),
        Event(
            time=10.0,
            resource="AGV1",
            state="attend",
            state_type="Dependency",
            activity="start state",
            product="Product_A_1",
            expected_end_time=15.0,
            process="attend",
        ),
        Event(
            time=8.0,
            resource="AGV1",
            state="move",
            state_type="Transport",
            activity="start state",
            product="Product_A_1",
            expected_end_time=10.0,
            process="move",
        ),
        Event(
            time=0.0,
            resource="AGV1",
            state="TP",
            state_type="Transport",
            activity="start state",
            product="Product_A_1",
            expected_end_time=2.0,
            process="TP",
        ),
    ]

    df = AnalyticsStore(production_system_data=system).planned_wip_per_resource()
    r1 = df[df["WIP_resource"] == "R1"].reset_index(drop=True)
    assert list(r1["Time"]) == [10.0, 15.0]
    assert list(r1["WIP"]) == [1.0, 0.0]
    agv = df[df["WIP_resource"] == "AGV1"].reset_index(drop=True)
    assert list(agv["Time"]) == [0.0, 2.0]
    assert list(agv["WIP"]) == [1.0, 0.0]


def test_planned_output_from_schedule(system_with_valid_schedule):
    store = AnalyticsStore(production_system_data=system_with_valid_schedule)
    df = store.planned_output().sort_values("End_time").reset_index(drop=True)

    assert list(df["End_time"]) == [5.0, 15.0, 25.0]
    assert list(df["Product"]) == ["Product_A_1", "Product_A_2", "Product_A_3"]


def test_post_processor_exposes_planned_trajectories(system_with_valid_schedule):
    pp = PostProcessor(production_system_data=system_with_valid_schedule, df_raw=None)

    assert len(pp.df_planned_WIP_per_resource) > 0
    assert len(pp.df_planned_output) == 3


def test_resolve_order_id_prefers_schedule_event_order_id():
    steps = [
        Event(
            time=5.0,
            resource="R1",
            state="P1",
            state_type="Production",
            activity="start state",
            product="product1_3",
            expected_end_time=10.0,
            process="P1",
            order_id="order_1",
        )
    ]
    assert _resolve_order_id_for_product("product1_3", steps, ["order_1"]) == "order_1"
    assert _order_id_from_product("product1_3", ["order_1"]) is None


def test_resolve_order_id_legacy_product_id_fallback():
    steps = [
        Event(
            time=5.0,
            resource="R1",
            state="P1",
            state_type="Production",
            activity="start state",
            product="Product_J8_VFS_WR024_9",
            expected_end_time=10.0,
            process="P1",
        )
    ]
    assert _resolve_order_id_for_product(
        "Product_J8_VFS_WR024_9", steps, ["WR024"]
    ) == "WR024"


def test_planned_wip_entry_at_first_step_not_order_release_time(system_with_valid_schedule):
    system = system_with_valid_schedule.model_copy(deep=True)
    system.order_data = [
        OrderData(
            ID="order_1",
            ordered_products=[OrderedProductData(product_type="Product_A", quantity=1)],
            order_time=0.0,
            release_time=0.0,
            due_time=100.0,
            priority=1,
        )
    ]
    system.schedule = [
        Event(
            time=5.0,
            resource="R1",
            state="P1",
            state_type="Production",
            activity="start state",
            product="Product_A_1",
            expected_end_time=10.0,
            process="P1",
            order_id="order_1",
        )
    ]

    df = AnalyticsStore(production_system_data=system).planned_wip()
    entry = df[df["WIP_Increment"] == 1].iloc[0]
    assert entry["Time"] == 5.0
    assert entry["Product"] == "Product_A_1"
