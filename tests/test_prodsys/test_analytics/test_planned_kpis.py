"""Tests for schedule-derived planned KPI trajectories."""

import pytest
import prodsys.express as psx
from prodsys.analytics.store import AnalyticsStore
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


def test_planned_output_from_schedule(system_with_valid_schedule):
    store = AnalyticsStore(production_system_data=system_with_valid_schedule)
    df = store.planned_output().sort_values("End_time").reset_index(drop=True)

    assert list(df["End_time"]) == [5.0, 15.0, 25.0]
    assert list(df["Product"]) == ["Product_A_1", "Product_A_2", "Product_A_3"]


def test_post_processor_exposes_planned_trajectories(system_with_valid_schedule):
    pp = PostProcessor(production_system_data=system_with_valid_schedule, df_raw=None)

    assert len(pp.df_planned_WIP_per_resource) > 0
    assert len(pp.df_planned_output) == 3
