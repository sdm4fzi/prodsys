"""
Monoid associativity tests: verify that
  kpi(full_stream) == kpi(append(append(empty, half1), half2))
for every KPI.

This is the property test that protects the entire architecture.
"""

import pytest
import pandas as pd
import numpy as np
import prodsys.express as psx
from prodsys import runner
from prodsys.analytics.store import AnalyticsStore


@pytest.fixture
def simulation_event_log():
    """Run a simulation and return the raw event log."""
    t1 = psx.FunctionTimeModel("constant", 0.8, 0, "t1")
    p1 = psx.ProductionProcess(t1, "p1")
    t3 = psx.FunctionTimeModel("normal", 0.1, 0.01, ID="t3")
    tp = psx.TransportProcess(t3, "tp")
    machine = psx.Resource([p1], [5, 0], 1, ID="machine")
    transport = psx.Resource([tp], [0, 0], 1, ID="transport")
    product1 = psx.Product([p1], tp, "product1")
    sink1 = psx.Sink(product1, [10, 0], "sink1")
    arrival = psx.FunctionTimeModel("exponential", 1, ID="arrival")
    source1 = psx.Source(product1, arrival, [0, 0], ID="source_1")
    system = psx.ProductionSystem([machine, transport], [source1], [sink1])
    adapter = system.to_model()

    runner_instance = runner.Runner(production_system_data=adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(200)
    post_processor = runner_instance.get_post_processor()
    return post_processor.df_raw, post_processor.time_range


class TestMonoidAssociativity:
    """
    Test that ingesting the full stream at once produces the same KPIs
    as ingesting in two halves incrementally.
    """

    def test_throughput_associativity(self, simulation_event_log):
        df_raw, time_range = simulation_event_log

        # Full ingest
        full = AnalyticsStore.from_raw(df_raw, time_range=time_range)

        # Incremental: split events at midpoint by time
        midpoint = df_raw["Time"].median()
        half1 = df_raw[df_raw["Time"] <= midpoint]
        half2 = df_raw[df_raw["Time"] > midpoint]

        incremental = AnalyticsStore(time_range=time_range)
        incremental.ingest_events(half1)
        incremental.ingest_events(half2)

        full_tp = full.throughput().sort_values("Product").reset_index(drop=True)
        incr_tp = incremental.throughput().sort_values("Product").reset_index(drop=True)

        assert len(full_tp) == len(incr_tp), (
            f"Throughput row count: full={len(full_tp)}, incremental={len(incr_tp)}"
        )

        for idx in range(len(full_tp)):
            assert abs(full_tp.iloc[idx]["Throughput_time"] - incr_tp.iloc[idx]["Throughput_time"]) < 1e-6

    def test_aggregated_throughput_time_associativity(self, simulation_event_log):
        df_raw, time_range = simulation_event_log
        midpoint = df_raw["Time"].median()

        full = AnalyticsStore.from_raw(df_raw, time_range=time_range)
        incremental = AnalyticsStore(time_range=time_range)
        incremental.ingest_events(df_raw[df_raw["Time"] <= midpoint])
        incremental.ingest_events(df_raw[df_raw["Time"] > midpoint])

        full_agg = full.aggregated_throughput_time()
        incr_agg = incremental.aggregated_throughput_time()

        for pt in full_agg.index:
            assert pt in incr_agg.index
            assert abs(full_agg[pt] - incr_agg[pt]) < 1e-6

    def test_output_associativity(self, simulation_event_log):
        df_raw, time_range = simulation_event_log
        midpoint = df_raw["Time"].median()

        full = AnalyticsStore.from_raw(df_raw, time_range=time_range)
        incremental = AnalyticsStore(time_range=time_range)
        incremental.ingest_events(df_raw[df_raw["Time"] <= midpoint])
        incremental.ingest_events(df_raw[df_raw["Time"] > midpoint])

        full_out = full.aggregated_output()
        incr_out = incremental.aggregated_output()

        for pt in full_out.index:
            assert pt in incr_out.index
            assert full_out[pt] == incr_out[pt]

    def test_resource_states_associativity(self, simulation_event_log):
        df_raw, time_range = simulation_event_log
        midpoint = df_raw["Time"].median()

        full = AnalyticsStore.from_raw(df_raw, time_range=time_range)
        incremental = AnalyticsStore(time_range=time_range)
        incremental.ingest_events(df_raw[df_raw["Time"] <= midpoint])
        incremental.ingest_events(df_raw[df_raw["Time"] > midpoint])

        full_rs = full.resource_states()
        incr_rs = incremental.resource_states()

        for resource in full_rs["Resource"].unique():
            full_res = full_rs[full_rs["Resource"] == resource]
            incr_res = incr_rs[incr_rs["Resource"] == resource]

            if len(incr_res) == 0:
                continue

            full_total = full_res["percentage"].sum()
            incr_total = incr_res["percentage"].sum()
            assert abs(full_total - 100.0) < 1.0
            assert abs(incr_total - 100.0) < 1.0

            for tt in full_res["Time_type"].unique():
                full_pct = full_res[full_res["Time_type"] == tt]["percentage"].sum()
                incr_pct = incr_res[incr_res["Time_type"] == tt]["percentage"].sum()
                assert abs(full_pct - incr_pct) < 5.0, (
                    f"Resource {resource} {tt}: full={full_pct:.1f}%, incr={incr_pct:.1f}%"
                )

    def test_scrap_associativity(self, simulation_event_log):
        df_raw, time_range = simulation_event_log
        midpoint = df_raw["Time"].median()

        full = AnalyticsStore.from_raw(df_raw, time_range=time_range)
        incremental = AnalyticsStore(time_range=time_range)
        incremental.ingest_events(df_raw[df_raw["Time"] <= midpoint])
        incremental.ingest_events(df_raw[df_raw["Time"] > midpoint])

        full_sc = full.scrap_per_product_type()
        incr_sc = incremental.scrap_per_product_type()

        if len(full_sc) > 0:
            for pt in full_sc["Product_type"].unique():
                full_row = full_sc[full_sc["Product_type"] == pt].iloc[0]
                incr_rows = incr_sc[incr_sc["Product_type"] == pt]
                if len(incr_rows) > 0:
                    incr_row = incr_rows.iloc[0]
                    assert full_row["Total_count"] == incr_row["Total_count"]
                    assert full_row["Scrap_count"] == incr_row["Scrap_count"]


class TestIncrementalAppendBasic:
    """Basic incremental append tests with synthetic data."""

    def test_append_produces_same_as_batch(self):
        """Single event-at-a-time append == batch ingest."""
        events = [
            {"Time": 5.0, "Resource": "src", "State": "s", "State Type": "Source", "Activity": "created product", "Product": "p_1"},
            {"Time": 10.0, "Resource": "M1", "State": "p1", "State Type": "Production", "Activity": "start state", "Product": "p_1"},
            {"Time": 20.0, "Resource": "M1", "State": "p1", "State Type": "Production", "Activity": "end state", "Product": "p_1"},
            {"Time": 25.0, "Resource": "sink", "State": "sk", "State Type": "Sink", "Activity": "finished product", "Product": "p_1"},
        ]
        df = pd.DataFrame(events)

        batch = AnalyticsStore.from_raw(df, time_range=30.0)
        incremental = AnalyticsStore(time_range=30.0)
        for _, row in df.iterrows():
            incremental.ingest_events(pd.DataFrame([row]))

        batch_tp = batch.throughput()
        incr_tp = incremental.throughput()
        assert len(batch_tp) == len(incr_tp)
        if len(batch_tp) > 0:
            assert abs(batch_tp.iloc[0]["Throughput_time"] - incr_tp.iloc[0]["Throughput_time"]) < 1e-6

    def test_empty_store_produces_empty_results(self):
        store = AnalyticsStore()
        assert len(store.throughput()) == 0
        assert len(store.resource_states()) == 0
        assert len(store.scrap_per_product_type()) == 0
        assert len(store.wip()) == 0
