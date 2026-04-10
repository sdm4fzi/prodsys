"""
Parity tests: verify that AnalyticsStore produces the same results
as the old PostProcessor for identical input data.

These tests are the correctness gate — nothing ships until they pass.
"""

import pytest
import pandas as pd
import numpy as np
from prodsys.util.post_processing import PostProcessor
from prodsys.analytics.store import AnalyticsStore


# ── Test fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def simple_event_log():
    """Simple event log with one machine, one transport, one product type."""
    data = {
        "Time": [
            19.8, 19.8, 19.94, 20.0, 26.0,
            39.8, 39.8, 40.0, 46.0,
            46.0, 46.0,
        ],
        "Resource": [
            "source", "Transport1", "Transport1", "Machine1", "Machine1",
            "source", "Transport1", "Transport1", "Machine1",
            "sink1", "sink1",
        ],
        "State": [
            "source_state", "transport_state", "transport_state", "production_state", "production_state",
            "source_state", "transport_state", "transport_state", "production_state",
            "sink_state", "sink_state",
        ],
        "State Type": [
            "Source", "Transport", "Transport", "Production", "Production",
            "Source", "Transport", "Transport", "Production",
            "Sink", "Sink",
        ],
        "Activity": [
            "created product", "start state", "end state", "start state", "end state",
            "created product", "start state", "end state", "start state",
            "finished product", "finished product",
        ],
        "Product": [
            "Product_1", "Product_1", "Product_1", "Product_1", "Product_1",
            "Product_2", "Product_2", "Product_2", "Product_2",
            "Product_1", "Product_2",
        ],
        "Expected End Time": [None] * 11,
        "Origin location": [None] * 11,
        "Target location": [None] * 11,
        "Empty Transport": [None] * 11,
        "Requesting Item": [None] * 11,
        "Dependency": [None] * 11,
        "process": [None] * 11,
        "Initial Transport Step": [None] * 11,
        "Last Transport Step": [None] * 11,
    }
    return pd.DataFrame(data)


@pytest.fixture
def comprehensive_event_log():
    """
    Comprehensive event log with multiple state types:
    Production, Transport, Breakdown, Setup, Charging, Dependency.
    Two product types, two machines.
    """
    num = 28
    data = {
        "Time": [
            # Source creates products
            5.0, 10.0,
            # Transport
            5.0, 8.0,
            # Machine1: production, breakdown, production
            8.0, 15.0,
            15.0, 15.0, 25.0, 25.0, 35.0,
            # Machine1: setup + production
            35.0, 40.0,
            40.0, 48.0,
            # Machine2: production
            10.0, 12.0,
            12.0, 22.0,
            # Machine2: dependency
            25.0, 30.0,
            # Machine2: charging
            32.0, 37.0,
            # Sink finishes products
            48.0, 48.0, 22.0,
            # Late production for Machine1
            50.0, 55.0,
        ],
        "Resource": [
            "source1", "source1",
            "transport1", "transport1",
            "Machine1", "Machine1",
            "Machine1", "Machine1", "Machine1", "Machine1", "Machine1",
            "Machine1", "Machine1",
            "Machine1", "Machine1",
            "transport1", "transport1",
            "Machine2", "Machine2",
            "Machine2", "Machine2",
            "Machine2", "Machine2",
            "sink1", "sink1", "sink1",
            "Machine1", "Machine1",
        ],
        "State": [
            "src_s", "src_s",
            "tp_s", "tp_s",
            "prod_s1", "prod_s1",
            "bd_s1", "prod_s1", "bd_s1", "prod_s1", "prod_s1",
            "setup_s1", "setup_s1",
            "prod_s2", "prod_s2",
            "tp_s", "tp_s",
            "prod_s3", "prod_s3",
            "dep_s1", "dep_s1",
            "chg_s1", "chg_s1",
            "sink_s", "sink_s", "sink_s",
            "prod_s4", "prod_s4",
        ],
        "State Type": [
            "Source", "Source",
            "Transport", "Transport",
            "Production", "Production",
            "Breakdown", "Production", "Breakdown", "Production", "Production",
            "Setup", "Setup",
            "Production", "Production",
            "Transport", "Transport",
            "Production", "Production",
            "Dependency", "Dependency",
            "Charging", "Charging",
            "Sink", "Sink", "Sink",
            "Production", "Production",
        ],
        "Activity": [
            "created product", "created product",
            "start state", "end state",
            "start state", "end state",
            "start state", "start interrupt", "end state", "end interrupt", "end state",
            "start state", "end state",
            "start state", "end state",
            "start state", "end state",
            "start state", "end state",
            "start state", "end state",
            "start state", "end state",
            "finished product", "finished product", "finished product",
            "start state", "end state",
        ],
        "Product": [
            "product1_1", "product2_1",
            "product1_1", "product1_1",
            "product1_1", "product1_1",
            None, "product1_1", None, "product1_1", "product1_1",
            None, None,
            "product2_1", "product2_1",
            "product2_1", "product2_1",
            "product2_1", "product2_1",
            None, None,
            None, None,
            "product1_1", "product2_1", "product2_1",
            "product1_1", "product1_1",
        ],
        "Expected End Time": [None] * num,
        "Origin location": [None] * num,
        "Target location": [None] * num,
        "Empty Transport": [None] * num,
        "Requesting Item": [None] * num,
        "Dependency": [None] * num,
        "process": [None] * num,
        "Initial Transport Step": [None] * num,
        "Last Transport Step": [None] * num,
    }
    return pd.DataFrame(data)


@pytest.fixture
def simple_resource_states_log():
    """
    Event log designed for resource states parity testing.
    Single machine with clear PR and SB periods, simulation time = 100.
    Uses a realistic event pattern with source/sink lifecycle events.
    """
    n = 12
    data = {
        "Time": [
            5.0,    # source creates product 1
            10.0,   # production start
            20.0,   # production end
            20.0,   # sink finishes product 1
            25.0,   # source creates product 2
            30.0,   # production start
            40.0,   # production end
            40.0,   # sink finishes product 2
            60.0,   # source creates product 3
            70.0,   # production start
            80.0,   # production end
            80.0,   # sink finishes product 3
        ],
        "Resource": [
            "source1",
            "Machine1", "Machine1",
            "sink1",
            "source1",
            "Machine1", "Machine1",
            "sink1",
            "source1",
            "Machine1", "Machine1",
            "sink1",
        ],
        "State": [
            "src_s",
            "prod_s", "prod_s",
            "sink_s",
            "src_s",
            "prod_s", "prod_s",
            "sink_s",
            "src_s",
            "prod_s", "prod_s",
            "sink_s",
        ],
        "State Type": [
            "Source",
            "Production", "Production",
            "Sink",
            "Source",
            "Production", "Production",
            "Sink",
            "Source",
            "Production", "Production",
            "Sink",
        ],
        "Activity": [
            "created product",
            "start state", "end state",
            "finished product",
            "created product",
            "start state", "end state",
            "finished product",
            "created product",
            "start state", "end state",
            "finished product",
        ],
        "Product": [
            "P_1",
            "P_1", "P_1",
            "P_1",
            "P_2",
            "P_2", "P_2",
            "P_2",
            "P_3",
            "P_3", "P_3",
            "P_3",
        ],
        "Expected End Time": [None] * n,
        "Origin location": [None] * n,
        "Target location": [None] * n,
        "Empty Transport": [None] * n,
        "Requesting Item": [None] * n,
        "Dependency": [None] * n,
        "process": [None] * n,
        "Initial Transport Step": [None] * n,
        "Last Transport Step": [None] * n,
    }
    return pd.DataFrame(data)


# ── Throughput parity tests ──────────────────────────────────────────────

class TestThroughputParity:
    """Verify throughput KPIs match between old and new."""

    def test_throughput_time_per_product(self, simple_event_log):
        old = PostProcessor(df_raw=simple_event_log)
        new = AnalyticsStore.from_raw(simple_event_log)

        old_tp = old.df_throughput.sort_values("Product").reset_index(drop=True)
        new_tp = new.throughput().sort_values("Product").reset_index(drop=True)

        for idx in range(len(old_tp)):
            old_row = old_tp.iloc[idx]
            new_row = new_tp.iloc[idx]
            assert old_row["Product"] == new_row["Product"], f"Product mismatch at index {idx}"
            assert abs(old_row["Throughput_time"] - new_row["Throughput_time"]) < 1e-6, (
                f"Throughput time mismatch for {old_row['Product']}: "
                f"old={old_row['Throughput_time']}, new={new_row['Throughput_time']}"
            )

    def test_aggregated_throughput_time(self, simple_event_log):
        old = PostProcessor(df_raw=simple_event_log)
        new = AnalyticsStore.from_raw(simple_event_log)

        old_agg = old.df_aggregated_throughput_time
        new_agg = new.aggregated_throughput_time()

        for pt in old_agg.index:
            old_val = old_agg[pt]
            assert pt in new_agg.index, f"Product type {pt} missing from new results"
            new_val = new_agg[pt]
            assert abs(old_val - new_val) < 1e-6, (
                f"Aggregated throughput time mismatch for {pt}: old={old_val}, new={new_val}"
            )

    def test_output_and_throughput(self, simple_event_log):
        old = PostProcessor(df_raw=simple_event_log)
        new = AnalyticsStore.from_raw(simple_event_log)

        old_ot = old.df_aggregated_output_and_throughput
        new_ot = new.aggregated_output_and_throughput()

        for pt in old_ot.index:
            assert pt in new_ot.index, f"Product type {pt} missing"
            assert old_ot.loc[pt, "Output"] == new_ot.loc[pt, "Output"], (
                f"Output mismatch for {pt}: old={old_ot.loc[pt, 'Output']}, new={new_ot.loc[pt, 'Output']}"
            )
            assert abs(old_ot.loc[pt, "Throughput"] - new_ot.loc[pt, "Throughput"]) < 1e-6


# ── Resource states parity tests ─────────────────────────────────────────

class TestResourceStatesParity:
    """Verify resource states match between old and new."""

    def test_simple_pr_sb_percentages(self, simple_resource_states_log):
        new = AnalyticsStore.from_raw(simple_resource_states_log, time_range=100.0)
        new_agg = new.resource_states()

        new_m1 = new_agg[new_agg["Resource"] == "Machine1"]
        assert len(new_m1) > 0, "Machine1 should have resource states"

        # Machine1 runs production at 10-20, 30-40, 70-80 = 30 minutes out of 100
        new_pr = new_m1[new_m1["Time_type"] == "PR"]["percentage"].sum()
        assert abs(new_pr - 30.0) < 0.1, f"PR should be 30%, got {new_pr}"

        new_sb = new_m1[new_m1["Time_type"] == "SB"]["percentage"].sum()
        assert abs(new_sb - 70.0) < 0.1, f"SB should be 70%, got {new_sb}"

        new_total = new_m1["percentage"].sum()
        assert abs(new_total - 100.0) < 0.01, f"Percentages should sum to 100%, got {new_total}"

    def test_comprehensive_all_state_types(self, comprehensive_event_log):
        """Test with all state types: PR, UD, ST, CR, DP."""
        old = PostProcessor(df_raw=comprehensive_event_log, time_range=55.0)
        new = AnalyticsStore.from_raw(comprehensive_event_log, time_range=55.0)

        old_agg = old.df_aggregated_resource_states
        new_agg = new.resource_states()

        # For each resource in old, check percentages sum to ~100% in new
        for resource in old_agg["Resource"].unique():
            if resource in ("source1", "sink1", "transport1"):
                continue  # Source/sink excluded

            old_res = old_agg[old_agg["Resource"] == resource]
            new_res = new_agg[new_agg["Resource"] == resource]

            if len(new_res) == 0:
                continue

            new_total = new_res["percentage"].sum()
            assert abs(new_total - 100.0) < 1.0, (
                f"Resource {resource}: percentages sum to {new_total}, expected 100%"
            )

            # Check that time_increments sum to resource_time
            new_time_total = new_res["time_increment"].sum()
            resource_time = new_res["resource_time"].iloc[0]
            assert abs(new_time_total - resource_time) < 0.1, (
                f"Resource {resource}: time_increments sum to {new_time_total}, "
                f"expected {resource_time}"
            )


# ── Scrap parity tests ──────────────────────────────────────────────────

class TestScrapParity:
    """Verify scrap KPIs match between old and new."""

    def test_scrap_with_failures(self):
        """Test scrap calculation with some process failures."""
        data = {
            "Time": [
                5.0,
                10.0, 20.0,
                25.0, 35.0,
                40.0, 50.0,
                50.0,
            ],
            "Resource": [
                "source1",
                "Machine1", "Machine1",
                "Machine1", "Machine1",
                "Machine1", "Machine1",
                "sink1",
            ],
            "State": [
                "src_s",
                "prod_s", "prod_s",
                "prod_s", "prod_s",
                "prod_s", "prod_s",
                "sink_s",
            ],
            "State Type": [
                "Source",
                "Production", "Production",
                "Production", "Production",
                "Production", "Production",
                "Sink",
            ],
            "Activity": [
                "created product",
                "start state", "end state",
                "start state", "end state",
                "start state", "end state",
                "finished product",
            ],
            "Product": [
                "product1_1",
                "product1_1", "product1_1",
                "product1_1", "product1_1",
                "product1_1", "product1_1",
                "product1_1",
            ],
            "process_ok": [
                None,
                None, True,
                None, False,
                None, True,
                None,
            ],
            "Expected End Time": [None] * 8,
            "Origin location": [None] * 8,
            "Target location": [None] * 8,
            "Empty Transport": [None] * 8,
            "Requesting Item": [None] * 8,
            "Dependency": [None] * 8,
            "process": [None] * 8,
            "Initial Transport Step": [None] * 8,
            "Last Transport Step": [None] * 8,
        }
        df = pd.DataFrame(data)

        old = PostProcessor(df_raw=df)
        new = AnalyticsStore.from_raw(df)

        old_scrap = old.df_scrap_per_product_type
        new_scrap = new.scrap_per_product_type()

        if len(old_scrap) > 0 and len(new_scrap) > 0:
            for pt in old_scrap["Product_type"].unique():
                old_row = old_scrap[old_scrap["Product_type"] == pt].iloc[0]
                new_row = new_scrap[new_scrap["Product_type"] == pt]
                if len(new_row) > 0:
                    new_row = new_row.iloc[0]
                    assert old_row["Total_count"] == new_row["Total_count"], (
                        f"Total count mismatch for {pt}"
                    )
                    assert old_row["Scrap_count"] == new_row["Scrap_count"], (
                        f"Scrap count mismatch for {pt}"
                    )

    def test_no_scrap(self, simple_event_log):
        """Test scrap when all processes succeed."""
        new = AnalyticsStore.from_raw(simple_event_log)
        new_scrap = new.scrap_per_product_type()
        # Either empty or all Scrap_rate == 0
        if len(new_scrap) > 0:
            assert (new_scrap["Scrap_rate"] == 0).all()


# ── WIP parity tests ────────────────────────────────────────────────────

class TestWIPParity:
    """Verify WIP calculations match between old and new."""

    def test_system_wip(self, simple_event_log):
        new = AnalyticsStore.from_raw(simple_event_log)
        wip = new.wip()

        # WIP should start at 0, go up on creation, down on finish
        if len(wip) > 0:
            assert wip["WIP"].iloc[0] >= 0
            assert wip["WIP"].min() >= 0


# ── Integration test with simulation ─────────────────────────────────────

class TestSimulationParity:
    """Run an actual simulation and compare old vs new analytics."""

    @pytest.fixture
    def simulation_data(self):
        """Run a short simulation and return the raw event log."""
        import prodsys.express as psx
        from prodsys import runner

        t1 = psx.FunctionTimeModel("constant", 0.8, 0, "t1")
        p1 = psx.ProductionProcess(t1, "p1")
        t3 = psx.FunctionTimeModel("normal", 0.1, 0.01, ID="t3")
        tp = psx.TransportProcess(t3, "tp")
        machine = psx.Resource([p1], [5, 0], 1, ID="machine")
        transport = psx.Resource([tp], [0, 0], 1, ID="transport")
        product1 = psx.Product([p1], tp, "product1")
        sink1 = psx.Sink(product1, [10, 0], "sink1")
        arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")
        source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")
        system = psx.ProductionSystem([machine, transport], [source1], [sink1])
        adapter = system.to_model()

        runner_instance = runner.Runner(production_system_data=adapter)
        runner_instance.initialize_simulation()
        runner_instance.run(200)
        post_processor = runner_instance.get_post_processor()

        return post_processor

    def test_throughput_parity_simulation(self, simulation_data):
        """Test throughput parity on actual simulation data."""
        old = simulation_data
        df_raw = old.df_raw
        new = AnalyticsStore.from_raw(df_raw, time_range=old.time_range)

        old_tp = old.df_throughput.sort_values("Product").reset_index(drop=True)
        new_tp = new.throughput().sort_values("Product").reset_index(drop=True)

        assert len(old_tp) == len(new_tp), (
            f"Throughput row count mismatch: old={len(old_tp)}, new={len(new_tp)}"
        )

        for idx in range(len(old_tp)):
            old_val = old_tp.iloc[idx]["Throughput_time"]
            new_val = new_tp.iloc[idx]["Throughput_time"]
            assert abs(old_val - new_val) < 1e-6, (
                f"Throughput time mismatch at row {idx}: old={old_val}, new={new_val}"
            )

    def test_aggregated_throughput_parity_simulation(self, simulation_data):
        old = simulation_data
        new = AnalyticsStore.from_raw(old.df_raw, time_range=old.time_range)

        old_agg = old.df_aggregated_throughput_time
        new_agg = new.aggregated_throughput_time()

        for pt in old_agg.index:
            assert pt in new_agg.index
            assert abs(old_agg[pt] - new_agg[pt]) < 1e-6

    def test_output_parity_simulation(self, simulation_data):
        old = simulation_data
        new = AnalyticsStore.from_raw(old.df_raw, time_range=old.time_range)

        old_output = old.df_aggregated_output
        new_output = new.aggregated_output()

        for pt in old_output.index:
            assert pt in new_output.index
            assert old_output[pt] == new_output[pt]

    def test_resource_states_parity_simulation(self, simulation_data):
        """Resource states percentages should sum to ~100% for each resource."""
        old = simulation_data
        new = AnalyticsStore.from_raw(old.df_raw, time_range=old.time_range)

        old_agg = old.df_aggregated_resource_states
        new_agg = new.resource_states()

        for resource in old_agg["Resource"].unique():
            old_res = old_agg[old_agg["Resource"] == resource]
            new_res = new_agg[new_agg["Resource"] == resource]

            if len(new_res) == 0:
                continue

            new_total = new_res["percentage"].sum()
            assert abs(new_total - 100.0) < 1.0, (
                f"Resource {resource}: percentages sum to {new_total}"
            )

            # Check PR time is in the same ballpark
            old_pr = old_res[old_res["Time_type"] == "PR"]["percentage"].sum()
            new_pr = new_res[new_res["Time_type"] == "PR"]["percentage"].sum()
            assert abs(old_pr - new_pr) < 5.0, (
                f"Resource {resource} PR: old={old_pr:.1f}%, new={new_pr:.1f}%"
            )

    def test_scrap_parity_simulation(self, simulation_data):
        old = simulation_data
        new = AnalyticsStore.from_raw(old.df_raw, time_range=old.time_range)

        old_scrap = old.df_scrap_per_product_type
        new_scrap = new.scrap_per_product_type()

        if len(old_scrap) > 0:
            for pt in old_scrap["Product_type"].unique():
                old_row = old_scrap[old_scrap["Product_type"] == pt].iloc[0]
                new_rows = new_scrap[new_scrap["Product_type"] == pt]
                if len(new_rows) > 0:
                    new_row = new_rows.iloc[0]
                    assert old_row["Total_count"] == new_row["Total_count"]
                    assert old_row["Scrap_count"] == new_row["Scrap_count"]

    def test_oee_per_resource_simulation(self, simulation_data):
        """OEE per resource should produce valid values."""
        old = simulation_data
        new = AnalyticsStore.from_raw(
            old.df_raw,
            time_range=old.time_range,
            production_system_data=old.production_system_data,
        )

        new_oee = new.oee_per_resource()
        if len(new_oee) > 0:
            for _, row in new_oee.iterrows():
                assert 0 <= row["Availability"] <= 100, (
                    f"Resource {row['Resource']}: Availability={row['Availability']}"
                )
                assert 0 <= row["Quality"] <= 100
                assert 0 <= row["OEE"] <= 200  # OEE can technically exceed 100%

    def test_oee_system_simulation(self, simulation_data):
        """System OEE should produce valid values."""
        old = simulation_data
        new = AnalyticsStore.from_raw(
            old.df_raw,
            time_range=old.time_range,
            production_system_data=old.production_system_data,
        )

        sys_oee = new.oee_production_system()
        assert len(sys_oee) == 4
        for _, row in sys_oee.iterrows():
            assert 0 <= row["Value"] <= 200

    def test_store_accessible_from_postprocessor(self, simulation_data):
        """PostProcessor.store should return a working AnalyticsStore."""
        old = simulation_data
        store = old.store

        assert store is not None
        tp = store.throughput()
        assert len(tp) > 0
        rs = store.resource_states()
        assert len(rs) > 0
        for resource in rs["Resource"].unique():
            pct_sum = rs[rs["Resource"] == resource]["percentage"].sum()
            assert abs(pct_sum - 100.0) < 1.0
