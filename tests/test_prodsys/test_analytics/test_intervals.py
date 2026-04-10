"""
Unit tests for IntervalBuilder — the pairing state machine.
"""

import pytest
import pandas as pd
from prodsys.analytics.intervals import IntervalBuilder


class TestBasicPairing:
    """Test basic start/end state pairing."""

    def test_single_production_interval(self):
        builder = IntervalBuilder()
        builder.feed({"Time": 10.0, "Resource": "M1", "State": "p1", "State Type": "Production", "Activity": "start state", "Product": "P_1"})
        builder.feed({"Time": 20.0, "Resource": "M1", "State": "p1", "State Type": "Production", "Activity": "end state", "Product": "P_1", "process_ok": True})

        df = builder.drain()
        assert len(df) == 1
        row = df.iloc[0]
        assert row["entity_id"] == "M1"
        assert row["state_type"] == "Production"
        assert row["t_start"] == 10.0
        assert row["t_end"] == 20.0
        assert row["duration"] == 10.0
        assert row["interrupted"] == False
        assert row["product_type"] == "P"

    def test_multiple_sequential_intervals(self):
        builder = IntervalBuilder()
        for t_start, t_end, state_id in [(0, 10, "p1"), (10, 25, "p2"), (25, 30, "p1")]:
            builder.feed({"Time": t_start, "Resource": "M1", "State": state_id, "State Type": "Production", "Activity": "start state", "Product": "P_1"})
            builder.feed({"Time": t_end, "Resource": "M1", "State": state_id, "State Type": "Production", "Activity": "end state", "Product": "P_1"})

        df = builder.drain()
        assert len(df) == 3
        assert df["duration"].tolist() == [10.0, 15.0, 5.0]

    def test_different_resources(self):
        builder = IntervalBuilder()
        builder.feed({"Time": 0.0, "Resource": "M1", "State": "p1", "State Type": "Production", "Activity": "start state"})
        builder.feed({"Time": 0.0, "Resource": "M2", "State": "p2", "State Type": "Production", "Activity": "start state"})
        builder.feed({"Time": 10.0, "Resource": "M1", "State": "p1", "State Type": "Production", "Activity": "end state"})
        builder.feed({"Time": 15.0, "Resource": "M2", "State": "p2", "State Type": "Production", "Activity": "end state"})

        df = builder.drain()
        assert len(df) == 2
        m1 = df[df["entity_id"] == "M1"].iloc[0]
        m2 = df[df["entity_id"] == "M2"].iloc[0]
        assert m1["duration"] == 10.0
        assert m2["duration"] == 15.0

    def test_unmatched_end_is_dropped(self):
        builder = IntervalBuilder()
        builder.feed({"Time": 20.0, "Resource": "M1", "State": "p1", "State Type": "Production", "Activity": "end state"})
        df = builder.drain()
        assert len(df) == 0

    def test_process_ok_captured(self):
        builder = IntervalBuilder()
        builder.feed({"Time": 0.0, "Resource": "M1", "State": "p1", "State Type": "Production", "Activity": "start state", "Product": "P_1"})
        builder.feed({"Time": 10.0, "Resource": "M1", "State": "p1", "State Type": "Production", "Activity": "end state", "Product": "P_1", "process_ok": False})

        df = builder.drain()
        assert df.iloc[0]["process_ok"] == False


class TestInterrupts:
    """Test interrupt handling."""

    def test_simple_interrupt(self):
        builder = IntervalBuilder()
        # Production starts
        builder.feed({"Time": 10.0, "Resource": "M1", "State": "p1", "State Type": "Production", "Activity": "start state", "Product": "P_1"})
        # Breakdown starts (its own state)
        builder.feed({"Time": 15.0, "Resource": "M1", "State": "bd1", "State Type": "Breakdown", "Activity": "start state"})
        # Production is interrupted
        builder.feed({"Time": 15.0, "Resource": "M1", "State": "p1", "State Type": "Production", "Activity": "start interrupt", "Product": "P_1"})
        # Breakdown ends
        builder.feed({"Time": 25.0, "Resource": "M1", "State": "bd1", "State Type": "Breakdown", "Activity": "end state"})
        # Production resumes
        builder.feed({"Time": 25.0, "Resource": "M1", "State": "p1", "State Type": "Production", "Activity": "end interrupt", "Product": "P_1"})
        # Production completes
        builder.feed({"Time": 35.0, "Resource": "M1", "State": "p1", "State Type": "Production", "Activity": "end state", "Product": "P_1"})

        df = builder.drain()
        # Should have: production(10-15, interrupted), breakdown(15-25), production(25-35)
        assert len(df) == 3

        prod_intervals = df[df["state_type"] == "Production"].sort_values("t_start")
        assert len(prod_intervals) == 2
        assert prod_intervals.iloc[0]["t_start"] == 10.0
        assert prod_intervals.iloc[0]["t_end"] == 15.0
        assert prod_intervals.iloc[0]["interrupted"] == True
        assert prod_intervals.iloc[0]["duration"] == 5.0

        assert prod_intervals.iloc[1]["t_start"] == 25.0
        assert prod_intervals.iloc[1]["t_end"] == 35.0
        assert prod_intervals.iloc[1]["interrupted"] == False
        assert prod_intervals.iloc[1]["duration"] == 10.0

        bd_interval = df[df["state_type"] == "Breakdown"].iloc[0]
        assert bd_interval["t_start"] == 15.0
        assert bd_interval["t_end"] == 25.0
        assert bd_interval["duration"] == 10.0

    def test_interrupt_total_time_correct(self):
        """Verify that production segments + breakdown = total time span."""
        builder = IntervalBuilder()
        builder.feed({"Time": 10.0, "Resource": "M1", "State": "p1", "State Type": "Production", "Activity": "start state"})
        builder.feed({"Time": 15.0, "Resource": "M1", "State": "bd1", "State Type": "Breakdown", "Activity": "start state"})
        builder.feed({"Time": 15.0, "Resource": "M1", "State": "p1", "State Type": "Production", "Activity": "start interrupt"})
        builder.feed({"Time": 25.0, "Resource": "M1", "State": "bd1", "State Type": "Breakdown", "Activity": "end state"})
        builder.feed({"Time": 25.0, "Resource": "M1", "State": "p1", "State Type": "Production", "Activity": "end interrupt"})
        builder.feed({"Time": 35.0, "Resource": "M1", "State": "p1", "State Type": "Production", "Activity": "end state"})

        df = builder.drain()
        total_duration = df["duration"].sum()
        assert abs(total_duration - 25.0) < 1e-9  # 35 - 10


class TestProductLifecycle:
    """Test product lifecycle event handling."""

    def test_created_and_finished(self):
        builder = IntervalBuilder()
        builder.feed({"Time": 5.0, "Resource": "source1", "State": "s1", "State Type": "Source", "Activity": "created product", "Product": "product1_1"})
        builder.feed({"Time": 50.0, "Resource": "sink1", "State": "sk1", "State Type": "Sink", "Activity": "finished product", "Product": "product1_1"})

        df = builder.drain()

        # Should have: created marker, in_system interval, finished marker
        assert len(df) == 3

        in_system = df[df["state_type"] == "in_system"]
        assert len(in_system) == 1
        assert in_system.iloc[0]["t_start"] == 5.0
        assert in_system.iloc[0]["t_end"] == 50.0
        assert in_system.iloc[0]["duration"] == 45.0
        assert in_system.iloc[0]["product_type"] == "product1"

    def test_consumed_product(self):
        builder = IntervalBuilder()
        builder.feed({"Time": 5.0, "Resource": "source1", "State": "s1", "State Type": "Source", "Activity": "created product", "Product": "prim_1"})
        builder.feed({"Time": 30.0, "Resource": "M1", "State": "d1", "State Type": "Production", "Activity": "consumed product", "Product": "prim_1"})

        df = builder.drain()
        in_system = df[df["state_type"] == "in_system"]
        assert len(in_system) == 1
        assert in_system.iloc[0]["duration"] == 25.0

    def test_multiple_products(self):
        builder = IntervalBuilder()
        for i, (ct, ft) in enumerate([(5, 50), (10, 60), (15, 55)]):
            pid = f"p_{i}"
            builder.feed({"Time": ct, "Resource": "src", "State": "s", "State Type": "Source", "Activity": "created product", "Product": pid})
            builder.feed({"Time": ft, "Resource": "sink", "State": "sk", "State Type": "Sink", "Activity": "finished product", "Product": pid})

        df = builder.drain()
        in_system = df[df["state_type"] == "in_system"].sort_values("t_start")
        assert len(in_system) == 3
        assert in_system["duration"].tolist() == [45.0, 50.0, 40.0]

    def test_product_type_derivation(self):
        assert IntervalBuilder.derive_product_type("product1_42") == "product1"
        assert IntervalBuilder.derive_product_type("my_product_0") == "my_product"
        assert IntervalBuilder.derive_product_type(None) is None
        assert IntervalBuilder.derive_product_type("no_number_suffix") == "no_number_suffix"


class TestOpenIntervals:
    """Test snapshot_open and open interval tracking."""

    def test_snapshot_open(self):
        builder = IntervalBuilder()
        builder.feed({"Time": 10.0, "Resource": "M1", "State": "p1", "State Type": "Production", "Activity": "start state"})

        assert builder.num_open == 1
        snap = builder.snapshot_open(20.0)
        assert len(snap) == 1
        assert snap.iloc[0]["t_end"] == 20.0
        assert snap.iloc[0]["duration"] == 10.0

    def test_pending_products(self):
        builder = IntervalBuilder()
        builder.feed({"Time": 5.0, "Resource": "src", "State": "s", "State Type": "Source", "Activity": "created product", "Product": "p_1"})
        assert builder.num_pending_products == 1

        builder.feed({"Time": 50.0, "Resource": "sink", "State": "sk", "State Type": "Sink", "Activity": "finished product", "Product": "p_1"})
        assert builder.num_pending_products == 0


class TestIngestDataFrame:
    """Test batch ingestion from DataFrame."""

    def test_ingest_sorts_correctly(self):
        """Events at the same time should be processed in correct order:
        end states before start states."""
        data = {
            "Time": [0.0, 10.0, 10.0, 20.0],
            "Resource": ["M1", "M1", "M1", "M1"],
            "State": ["p1", "p1", "p2", "p2"],
            "State Type": ["Production", "Production", "Production", "Production"],
            "Activity": ["start state", "end state", "start state", "end state"],
            "Product": [None, None, None, None],
        }
        df = pd.DataFrame(data)
        builder = IntervalBuilder()
        builder.ingest_dataframe(df)
        result = builder.drain()
        # p1: 0→10, p2: 10→20
        assert len(result) == 2
        p1 = result[result["state_id"] == "p1"].iloc[0]
        p2 = result[result["state_id"] == "p2"].iloc[0]
        assert p1["t_start"] == 0.0 and p1["t_end"] == 10.0
        assert p2["t_start"] == 10.0 and p2["t_end"] == 20.0

    def test_ingest_realistic_event_log(self):
        """Test with event log similar to existing test fixtures."""
        data = {
            "Time": [19.8, 19.8, 19.94, 20.0, 26.0],
            "Resource": ["source", "Transport1", "Transport1", "Machine1", "Machine1"],
            "State": ["source_state", "transport_state", "transport_state", "production_state", "production_state"],
            "State Type": ["Source", "Transport", "Transport", "Production", "Production"],
            "Activity": ["created product", "start state", "end state", "start state", "end state"],
            "Product": ["Product_1", "Product_1", "Product_1", "Product_1", "Product_1"],
            "Origin location": [None] * 5,
            "Target location": [None] * 5,
        }
        df = pd.DataFrame(data)
        builder = IntervalBuilder()
        builder.ingest_dataframe(df)
        result = builder.drain()

        resource_intervals = result[result["entity_kind"] == "resource"]
        assert len(resource_intervals) == 2  # transport + production

        transport = resource_intervals[resource_intervals["state_type"] == "Transport"]
        assert len(transport) == 1
        assert abs(transport.iloc[0]["duration"] - 0.14) < 0.01

        production = resource_intervals[resource_intervals["state_type"] == "Production"]
        assert len(production) == 1
        assert production.iloc[0]["duration"] == 6.0


class TestAllStateTypes:
    """Test that all state types are handled correctly."""

    def test_breakdown_interval(self):
        builder = IntervalBuilder()
        builder.feed({"Time": 70.0, "Resource": "M1", "State": "bd1", "State Type": "Breakdown", "Activity": "start state"})
        builder.feed({"Time": 90.0, "Resource": "M1", "State": "bd1", "State Type": "Breakdown", "Activity": "end state"})

        df = builder.drain()
        assert len(df) == 1
        assert df.iloc[0]["state_type"] == "Breakdown"
        assert df.iloc[0]["duration"] == 20.0

    def test_setup_interval(self):
        builder = IntervalBuilder()
        builder.feed({"Time": 100.0, "Resource": "M1", "State": "s1", "State Type": "Setup", "Activity": "start state"})
        builder.feed({"Time": 110.0, "Resource": "M1", "State": "s1", "State Type": "Setup", "Activity": "end state"})

        df = builder.drain()
        assert len(df) == 1
        assert df.iloc[0]["state_type"] == "Setup"
        assert df.iloc[0]["duration"] == 10.0

    def test_charging_interval(self):
        builder = IntervalBuilder()
        builder.feed({"Time": 130.0, "Resource": "M1", "State": "c1", "State Type": "Charging", "Activity": "start state"})
        builder.feed({"Time": 140.0, "Resource": "M1", "State": "c1", "State Type": "Charging", "Activity": "end state"})

        df = builder.drain()
        assert len(df) == 1
        assert df.iloc[0]["state_type"] == "Charging"

    def test_dependency_interval(self):
        builder = IntervalBuilder()
        builder.feed({"Time": 50.0, "Resource": "M1", "State": "d1", "State Type": "Dependency", "Activity": "start state"})
        builder.feed({"Time": 60.0, "Resource": "M1", "State": "d1", "State Type": "Dependency", "Activity": "end state"})

        df = builder.drain()
        assert len(df) == 1
        assert df.iloc[0]["state_type"] == "Dependency"

    def test_non_scheduled_interval(self):
        builder = IntervalBuilder()
        builder.feed({"Time": 200.0, "Resource": "M1", "State": "ns1", "State Type": "NonScheduled", "Activity": "start state"})
        builder.feed({"Time": 300.0, "Resource": "M1", "State": "ns1", "State Type": "NonScheduled", "Activity": "end state"})

        df = builder.drain()
        assert len(df) == 1
        assert df.iloc[0]["state_type"] == "NonScheduled"
        assert df.iloc[0]["duration"] == 100.0
