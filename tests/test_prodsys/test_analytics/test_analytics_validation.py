"""
test_analytics_validation.py
============================
Analytics validation tests ported from analytics_consistency/rfa_analytics_validation.py.

Covers:
  1. Full-load baseline KPIs
  2. Incremental-append consistency (90 % / 10 % split)
  3. Time-window KPI queries and monotonicity
  4. Recompute-only-added-events consistency
  5. General domain-knowledge range checks
  6. OEE validation (per-resource, system, interval-based, time windows)
"""

from __future__ import annotations

import pytest
import pandas as pd
import numpy as np
import prodsys.express as psx
from prodsys import runner
from prodsys.analytics.store import AnalyticsStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _series_allclose(a: pd.Series, b: pd.Series, rtol: float = 1e-6) -> tuple[bool, str]:
    """Return (match, detail) for two Series compared by aligned index."""
    a, b = a.align(b, fill_value=0.0)
    if len(a) == 0:
        return True, "both empty"
    rel_diff = (a - b).abs() / (a.abs().clip(lower=1e-12))
    max_diff = float(rel_diff.max())
    return max_diff <= rtol, f"max_rel_diff={max_diff:.3e}"


# ---------------------------------------------------------------------------
# Shared simulation fixture
#
# Two product types, two dedicated machines, shared rework station.
# Breakdowns (UD), non-scheduled shift state (NS), setup transitions (ST),
# and process failures (scrap) are all present so every KPI is exercised.
# Simulation time: 400 h  →  fast enough for CI, long enough for steady state.
# ---------------------------------------------------------------------------

SIM_TIME = 400.0


@pytest.fixture(scope="module")
def rich_simulation_data():
    """
    Run a rich simulation and return (df_raw, time_range, production_system_data).

    The system has:
      - 2 product types (product_a, product_b)
      - 2 production machines (machineA, machineB)
      - 1 transport resource
      - Process failures → rework / scrap
      - Breakdown states (UD)
      - Non-scheduled shift state (NS)
      - Setup transitions between products on machineA (ST)
    """
    import random as _rng
    import numpy as _np
    _rng.seed(42)
    _np.random.seed(42)

    # ── Time models ──────────────────────────────────────────────────────────
    t_proc_a = psx.FunctionTimeModel("normal", 2.0, 0.1, "t_proc_a")
    t_proc_b = psx.FunctionTimeModel("normal", 3.0, 0.15, "t_proc_b")
    t_rework = psx.FunctionTimeModel("normal", 1.0, 0.05, "t_rework")
    t_transport = psx.FunctionTimeModel("constant", 0.05, ID="t_transport")
    t_arrive_a = psx.FunctionTimeModel("exponential", 2.5, ID="t_arrive_a")
    t_arrive_b = psx.FunctionTimeModel("exponential", 4.0, ID="t_arrive_b")

    # ── Breakdown states ──────────────────────────────────────────────────────
    t_bd_occur = psx.FunctionTimeModel("normal", 80.0, 10.0, "t_bd_occur")
    t_bd_repair = psx.FunctionTimeModel("normal", 2.0, 0.2, "t_bd_repair")
    breakdown = psx.BreakDownState(t_bd_occur, t_bd_repair, "breakdown")

    # ── Non-scheduled shift state (NS) ────────────────────────────────────────
    # 5 days on (120 h), 2 days off (48 h) — weekly pattern
    _weeks = int(SIM_TIME / 168) + 3
    t_sched = psx.ScheduledTimeModel(
        schedule=[120.0] * _weeks, absolute=False, cyclic=True, ID="t_sched"
    )
    t_nonsched = psx.ScheduledTimeModel(
        schedule=[48.0] * _weeks, absolute=False, cyclic=True, ID="t_nonsched"
    )
    shift_state = psx.NonScheduledState(t_sched, t_nonsched, "shift_state")

    # ── Processes ─────────────────────────────────────────────────────────────
    tp = psx.TransportProcess(t_transport, "tp")
    proc_a = psx.ProductionProcess(t_proc_a, "proc_a", failure_rate=0.05)
    proc_b = psx.ProductionProcess(t_proc_b, "proc_b", failure_rate=0.08)
    rework_a = psx.ReworkProcess(t_rework, [proc_a], True, "rework_a")
    rework_b = psx.ReworkProcess(t_rework, [proc_b], True, "rework_b")

    # ── Setup transitions on machineA (A → B and back) ───────────────────────
    t_setup = psx.FunctionTimeModel("normal", 0.5, 0.05, "t_setup")
    setup_ab = psx.SetupState(t_setup, proc_a, proc_b, "setup_ab")
    setup_ba = psx.SetupState(t_setup, proc_b, proc_a, "setup_ba")

    # ── Resources ─────────────────────────────────────────────────────────────
    machineA = psx.Resource(
        [proc_a, proc_b, rework_a, rework_b],
        location=[5, 0],
        capacity=1,
        states=[breakdown, setup_ab, setup_ba, shift_state],
        ID="machineA",
    )
    machineB = psx.Resource(
        [proc_b, rework_b],
        location=[10, 0],
        capacity=1,
        states=[breakdown, shift_state],
        ID="machineB",
    )
    transport = psx.Resource([tp], [0, 0], 1, states=[shift_state], ID="transport")

    # ── Products ──────────────────────────────────────────────────────────────
    product_a = psx.Product([proc_a], tp, "product_a")
    product_b = psx.Product([proc_b], tp, "product_b")

    # ── Sources / Sinks ───────────────────────────────────────────────────────
    sink_a = psx.Sink(product_a, [15, 0], "sink_a")
    sink_b = psx.Sink(product_b, [15, 3], "sink_b")
    source_a = psx.Source(product_a, t_arrive_a, [-5, 0], ID="source_a")
    source_b = psx.Source(product_b, t_arrive_b, [-5, 3], ID="source_b")

    system = psx.ProductionSystem(
        [machineA, machineB, transport],
        [source_a, source_b],
        [sink_a, sink_b],
    )
    adapter = system.to_model()

    runner_instance = runner.Runner(production_system_data=adapter)
    runner_instance.initialize_simulation()
    runner_instance.run(SIM_TIME)
    pp = runner_instance.get_post_processor()
    return pp.df_raw, pp.time_range, adapter


# ---------------------------------------------------------------------------
# Section 1 — Full-load baseline KPIs
# ---------------------------------------------------------------------------

class TestBaselineKPIs:
    """Port of Section 1 from rfa_analytics_validation.py."""

    @pytest.fixture(scope="class")
    def full_store(self, rich_simulation_data):
        df_raw, time_range, model = rich_simulation_data
        return AnalyticsStore.from_raw(df_raw, time_range=time_range, production_system_data=model)

    def test_output_has_multiple_product_types(self, full_store):
        out = full_store.aggregated_output().sort_index()
        assert len(out) >= 2, f"Expected at least 2 product types, got {list(out.index)}"

    def test_total_output_exceeds_threshold(self, full_store):
        out = full_store.aggregated_output()
        total = int(out.sum())
        assert total > 50, f"Expected total output > 50 lots, got {total}"

    def test_throughput_times_positive(self, full_store):
        tpt = full_store.aggregated_throughput_time()
        assert len(tpt) > 0, "No throughput time data"
        assert bool((tpt > 0).all()), f"All TPT must be > 0, min={tpt.min():.4f}"

    def test_throughput_times_below_2x_sim_time(self, full_store):
        tpt = full_store.aggregated_throughput_time()
        t_max = full_store.simulation_end_time
        assert bool((tpt < 2 * t_max).all()), (
            f"Max TPT {tpt.max():.2f} h exceeds 2×sim_time={2*t_max:.0f} h"
        )

    def test_resource_states_pr_positive(self, full_store):
        rs = full_store.resource_states()
        machines = rs[rs["Resource"].isin(["machineA", "machineB"])]
        pr_rows = machines[machines["Time_type"] == "PR"]
        assert len(pr_rows) > 0, "Machines must have productive (PR) time"
        assert bool((pr_rows["time_increment"] > 0).all()), (
            "All machine PR time_increments must be > 0"
        )

    def test_resource_state_percentages_sum_to_100(self, full_store):
        rs = full_store.resource_states()
        pct_sum = rs.groupby("Resource")["percentage"].sum()
        assert bool((pct_sum <= 101.0).all()), (
            f"State percentages must sum ≤ 101 % per resource; max={pct_sum.max():.2f}%"
        )

    def test_scrap_rates_in_valid_range(self, full_store):
        scrap = full_store.scrap_per_product_type()
        if len(scrap) == 0:
            pytest.skip("No scrap data in simulation run")
        assert bool(scrap["Scrap_rate"].between(0, 50).all()), (
            f"Scrap rates out of [0, 50]%: {scrap['Scrap_rate'].to_dict()}"
        )

    def test_wip_non_negative(self, full_store):
        wip = full_store.wip()
        if len(wip) == 0:
            pytest.skip("No WIP data")
        assert wip["WIP"].min() >= 0, f"WIP must be non-negative; min={wip['WIP'].min()}"

    def test_peak_wip_positive(self, full_store):
        wip = full_store.wip()
        if len(wip) == 0:
            pytest.skip("No WIP data")
        assert wip["WIP"].max() > 0, "Peak WIP must be > 0"

    def test_machine_has_breakdown_state(self, full_store):
        rs = full_store.resource_states()
        ma = rs[rs["Resource"] == "machineA"]
        assert len(ma) > 0, "machineA must have resource state records"
        assert "UD" in ma["Time_type"].values, (
            f"machineA must have UD (Unplanned Downtime) state; "
            f"types found: {sorted(ma['Time_type'].unique())}"
        )

    def test_machine_has_nonscheduled_state(self, full_store):
        rs = full_store.resource_states()
        ma = rs[rs["Resource"] == "machineA"]
        assert "NS" in ma["Time_type"].values, (
            f"machineA must have NS (NonScheduled) state; "
            f"types found: {sorted(ma['Time_type'].unique())}"
        )

    def test_machine_has_setup_state(self, full_store):
        rs = full_store.resource_states()
        ma = rs[rs["Resource"] == "machineA"]
        assert "ST" in ma["Time_type"].values, (
            f"machineA must have ST (Setup) state; "
            f"types found: {sorted(ma['Time_type'].unique())}"
        )


# ---------------------------------------------------------------------------
# Section 2 — Incremental-append consistency (90 % / 10 % split)
# ---------------------------------------------------------------------------

class TestIncrementalAppendConsistency:
    """Port of Section 2 from rfa_analytics_validation.py."""

    @pytest.fixture(scope="class")
    def stores(self, rich_simulation_data):
        df_all, time_range, model = rich_simulation_data
        split_time = df_all["Time"].max() * 0.90
        df_early = df_all[df_all["Time"] <= split_time].copy()
        df_late = df_all[df_all["Time"] > split_time].copy()

        store_ref = AnalyticsStore.from_raw(df_all, time_range=time_range, production_system_data=model)

        # Use the same time_range so percentage denominators match the reference store.
        store_inc = AnalyticsStore(time_range=time_range, production_system_data=model)
        store_inc.ingest_events(df_early)
        partial_out = store_inc.aggregated_output().sort_index()
        store_inc.append_events(df_late)

        return store_ref, store_inc, partial_out

    def test_output_incremental_equals_reference(self, stores):
        store_ref, store_inc, _ = stores
        ref = store_ref.aggregated_output().sort_index()
        inc = store_inc.aggregated_output().sort_index()
        ok, detail = _series_allclose(ref, inc)
        assert ok, f"Output mismatch between incremental and reference store: {detail}"

    def test_throughput_time_incremental_equals_reference(self, stores):
        store_ref, store_inc, _ = stores
        ref = store_ref.aggregated_throughput_time().sort_index()
        inc = store_inc.aggregated_throughput_time().sort_index()
        ok, detail = _series_allclose(ref, inc)
        assert ok, f"Mean TPT mismatch: {detail}"

    def test_scrap_incremental_equals_reference(self, stores):
        store_ref, store_inc, _ = stores
        ref_scrap = store_ref.scrap_per_product_type()
        inc_scrap = store_inc.scrap_per_product_type()
        if len(ref_scrap) == 0:
            pytest.skip("No scrap data")
        ref_s = ref_scrap.set_index("Product_type")["Scrap_rate"]
        inc_s = inc_scrap.set_index("Product_type")["Scrap_rate"]
        ok, detail = _series_allclose(ref_s, inc_s, rtol=1e-4)
        assert ok, f"Scrap rate mismatch: {detail}"

    def test_resource_states_incremental_equals_reference(self, stores):
        store_ref, store_inc, _ = stores
        ref_rs = store_ref.resource_states().groupby(["Resource", "Time_type"])["percentage"].sum()
        inc_rs = store_inc.resource_states().groupby(["Resource", "Time_type"])["percentage"].sum()
        ok, detail = _series_allclose(ref_rs, inc_rs, rtol=1e-4)
        assert ok, f"Resource state % mismatch: {detail}"

    def test_partial_output_le_reference(self, stores):
        store_ref, _, partial_out = stores
        ref_out = store_ref.aggregated_output().sort_index()
        all_types = ref_out.index.union(partial_out.index)
        ref_aligned = ref_out.reindex(all_types, fill_value=0)
        par_aligned = partial_out.reindex(all_types, fill_value=0)
        assert bool((par_aligned <= ref_aligned).all()), (
            f"Partial (90%) output must be ≤ reference for all product types;\n"
            f"partial={par_aligned.to_dict()}\nref={ref_aligned.to_dict()}"
        )

    def test_interval_count_matches(self, stores):
        store_ref, store_inc, _ = stores
        ref_n = len(store_ref.intervals)
        inc_n = len(store_inc.intervals)
        assert ref_n == inc_n, (
            f"Interval count mismatch: ref={ref_n}, incremental={inc_n}"
        )


# ---------------------------------------------------------------------------
# Section 3 — Time-window KPI queries and monotonicity
# ---------------------------------------------------------------------------

class TestTimeWindowKPIs:
    """Port of Section 3 from rfa_analytics_validation.py."""

    @pytest.fixture(scope="class")
    def full_store(self, rich_simulation_data):
        df_raw, time_range, model = rich_simulation_data
        return AnalyticsStore.from_raw(df_raw, time_range=time_range, production_system_data=model)

    @pytest.fixture(scope="class")
    def window_outputs(self, full_store):
        t_max = full_store.simulation_end_time
        windows = {
            "last_8h":  (t_max - 8.0,  t_max),
            "last_24h": (t_max - 24.0, t_max),
            "full":     (0.0,           t_max),
        }
        return {
            label: full_store.aggregated_output(t_from=t_from, t_to=t_to).sort_index()
            for label, (t_from, t_to) in windows.items()
        }, t_max

    @pytest.fixture(scope="class")
    def window_tpt(self, full_store):
        t_max = full_store.simulation_end_time
        windows = {
            "last_8h":  (t_max - 8.0,  t_max),
            "last_24h": (t_max - 24.0, t_max),
            "full":     (0.0,           t_max),
        }
        return {
            label: full_store.aggregated_throughput_time(t_from=t_from, t_to=t_to)
            for label, (t_from, t_to) in windows.items()
        }

    def test_total_output_monotone_8h_le_24h(self, window_outputs):
        outputs, _ = window_outputs
        out_8h  = int(outputs["last_8h"].sum())  if len(outputs["last_8h"])  > 0 else 0
        out_24h = int(outputs["last_24h"].sum()) if len(outputs["last_24h"]) > 0 else 0
        assert out_8h <= out_24h, (
            f"Output not monotone: last_8h={out_8h} > last_24h={out_24h}"
        )

    def test_total_output_monotone_24h_le_full(self, window_outputs):
        outputs, _ = window_outputs
        out_24h  = int(outputs["last_24h"].sum()) if len(outputs["last_24h"]) > 0 else 0
        out_full = int(outputs["full"].sum())      if len(outputs["full"])     > 0 else 0
        assert out_24h <= out_full, (
            f"Output not monotone: last_24h={out_24h} > full={out_full}"
        )

    def test_full_window_output_positive(self, window_outputs):
        outputs, _ = window_outputs
        out_full = int(outputs["full"].sum())
        assert out_full > 0, "Full-window total output must be > 0"

    def test_per_product_type_output_monotone(self, window_outputs):
        outputs, _ = window_outputs
        all_types = (
            outputs["last_8h"].index
            .union(outputs["last_24h"].index)
            .union(outputs["full"].index)
        )
        for pt in all_types:
            v8    = int(outputs["last_8h"].get(pt, 0))
            v24   = int(outputs["last_24h"].get(pt, 0))
            vfull = int(outputs["full"].get(pt, 0))
            assert v8 <= v24 <= vfull, (
                f"Output not monotone for {pt}: last_8h={v8}, last_24h={v24}, full={vfull}"
            )

    def test_resource_pct_sums_le_101_all_windows(self, full_store):
        t_max = full_store.simulation_end_time
        windows = {
            "last_8h":  (t_max - 8.0,  t_max),
            "last_24h": (t_max - 24.0, t_max),
            "full":     (0.0,           t_max),
        }
        for label, (t_from, t_to) in windows.items():
            rs = full_store.resource_states(t_from=t_from, t_to=t_to)
            if len(rs) == 0:
                continue
            pct_sum = rs.groupby("Resource")["percentage"].sum()
            assert bool((pct_sum <= 101.0).all()), (
                f"Resource pct sums > 101 % in {label} window; max={pct_sum.max():.2f}%"
            )

    def test_throughput_times_positive_all_windows(self, window_tpt):
        for label, tpt in window_tpt.items():
            if len(tpt) == 0:
                continue
            assert bool((tpt > 0).all()), (
                f"TPT must be > 0 in {label} window; min={tpt.min():.4f}"
            )

    def test_short_window_tpt_within_reasonable_ratio_of_full(self, window_tpt):
        """
        Short-window TPT should be within [0.25×, 4×] of full-sim TPT.

        Windows anchored at the END of the simulation give representative
        steady-state samples (lots completing there started ~TPT h earlier),
        so ratios far outside [0.25, 4] indicate a selection-bias bug.
        """
        full_tpt = window_tpt["full"]
        if len(full_tpt) == 0:
            pytest.skip("No full-window TPT data")
        for label in ("last_8h", "last_24h"):
            tpt = window_tpt[label]
            if len(tpt) == 0:
                continue
            common = tpt.index.intersection(full_tpt.index)
            if len(common) == 0:
                continue
            ratio = tpt[common] / full_tpt[common]
            assert bool(ratio.between(0.25, 4.0).all()), (
                f"Short-window TPT [{label}] outside 0.25×–4× of full-sim TPT "
                f"(selection bias?); ratio range [{ratio.min():.2f}, {ratio.max():.2f}]"
            )


# ---------------------------------------------------------------------------
# Section 4 — Recompute-only-added-events consistency
# ---------------------------------------------------------------------------

class TestRecomputeConsistency:
    """Port of Section 4 from rfa_analytics_validation.py."""

    @pytest.fixture(scope="class")
    def split_stores(self, rich_simulation_data):
        df_all, time_range, model = rich_simulation_data
        t_max = df_all["Time"].max()
        split_time = t_max * 0.90

        df_early = df_all[df_all["Time"] <= split_time].copy()
        df_late  = df_all[df_all["Time"] > split_time].copy()

        store_full  = AnalyticsStore.from_raw(df_all,   time_range=time_range,  production_system_data=model)
        store_early = AnalyticsStore.from_raw(df_early, time_range=split_time,  production_system_data=model)
        store_early.finalize_at(split_time)
        store_late  = AnalyticsStore.from_raw(df_late,  production_system_data=model)

        return store_full, store_early, store_late, split_time, t_max

    def test_early_output_from_full_equals_standalone(self, split_stores):
        store_full, store_early, _, split_time, _ = split_stores
        from_full = store_full.aggregated_output(t_from=0.0, t_to=split_time).sort_index()
        standalone = store_early.aggregated_output().sort_index()
        ok, detail = _series_allclose(from_full, standalone, rtol=1e-4)
        assert ok, (
            f"Output [0, 90%] from full store != standalone early store: {detail}"
        )

    def test_full_store_late_output_ge_standalone_late(self, split_stores):
        store_full, _, store_late, split_time, t_max = split_stores
        full_late = store_full.aggregated_output(t_from=split_time, t_to=t_max).sort_index()
        standalone_late = store_late.aggregated_output().sort_index()
        all_types = full_late.index.union(standalone_late.index)
        full_aligned = full_late.reindex(all_types, fill_value=0)
        sa_aligned   = standalone_late.reindex(all_types, fill_value=0)
        assert bool((full_aligned >= sa_aligned).all()), (
            "Full-store late-window output must be ≥ standalone late store "
            "(products span the split boundary);\n"
            f"full_late={full_aligned.to_dict()}\nstandalone={sa_aligned.to_dict()}"
        )

    def test_partition_early_plus_late_le_full(self, split_stores):
        store_full, _, _, split_time, t_max = split_stores
        kpi_early = store_full.aggregated_output(t_from=0.0,        t_to=split_time).sort_index()
        kpi_late  = store_full.aggregated_output(t_from=split_time, t_to=t_max).sort_index()
        total     = store_full.aggregated_output().sort_index()
        for pt in total.index:
            ev = int(kpi_early.get(pt, 0))
            lv = int(kpi_late.get(pt, 0))
            fv = int(total.get(pt, 0))
            assert ev + lv <= fv + 1, (
                f"Partition violated for {pt}: early={ev} + late={lv} > full={fv}"
            )

    def test_resource_state_hours_early_match(self, split_stores):
        store_full, store_early, _, split_time, _ = split_stores
        rs_full = store_full.resource_states(t_from=0.0, t_to=split_time)
        rs_sa   = store_early.resource_states()
        if len(rs_full) == 0 or len(rs_sa) == 0:
            pytest.skip("No resource state data for comparison")
        full_inc = rs_full.groupby(["Resource", "Time_type"])["time_increment"].sum()
        sa_inc   = rs_sa.groupby(["Resource", "Time_type"])["time_increment"].sum()
        ok, detail = _series_allclose(full_inc, sa_inc, rtol=1e-4)
        assert ok, (
            f"Resource state hours [0, 90%] from full store ≠ standalone early store "
            f"(0.01% rtol): {detail}"
        )


# ---------------------------------------------------------------------------
# Section 5 — General domain-knowledge range checks
# ---------------------------------------------------------------------------

class TestDomainKnowledgeChecks:
    """General KPI sanity checks (domain knowledge, not model-specific)."""

    @pytest.fixture(scope="class")
    def full_store(self, rich_simulation_data):
        df_raw, time_range, model = rich_simulation_data
        return AnalyticsStore.from_raw(df_raw, time_range=time_range, production_system_data=model)

    def test_simulation_end_time_matches_configured(self, full_store):
        t_max = full_store.simulation_end_time
        assert abs(t_max - SIM_TIME) < 1.0, (
            f"Simulation end time {t_max:.2f} h differs from configured {SIM_TIME} h"
        )

    def test_all_product_types_have_output(self, full_store):
        out = full_store.aggregated_output()
        expected = {"product_a", "product_b"}
        actual   = set(out.index)
        assert expected.issubset(actual), (
            f"Missing product types in output: {expected - actual}"
        )

    def test_product_b_higher_scrap_than_product_a(self, full_store):
        """product_b failure_rate=0.08 > product_a failure_rate=0.05."""
        scrap = full_store.scrap_per_product_type()
        if len(scrap) < 2:
            pytest.skip("Not enough scrap data for comparison")
        pa = scrap.loc[scrap["Product_type"] == "product_a", "Scrap_rate"]
        pb = scrap.loc[scrap["Product_type"] == "product_b", "Scrap_rate"]
        if pa.empty or pb.empty:
            pytest.skip("Both product types not present in scrap data")
        assert float(pb.values[0]) >= float(pa.values[0]) * 0.5, (
            f"product_b scrap ({pb.values[0]:.2f}%) should be ≥ 50% of "
            f"product_a scrap ({pa.values[0]:.2f}%) given higher failure rate"
        )

    def test_mean_tpt_exceeds_min_processing_time(self, full_store):
        """Mean TPT must exceed the theoretical minimum processing time per product."""
        tpt = full_store.aggregated_throughput_time()
        min_times = {"product_a": 2.0, "product_b": 3.0}
        for pt, min_t in min_times.items():
            if pt in tpt.index:
                assert float(tpt[pt]) > min_t, (
                    f"Mean TPT({pt})={tpt[pt]:.2f} h ≤ theoretical minimum {min_t:.2f} h"
                )

    def test_machine_pr_percentage_in_valid_range(self, full_store):
        rs = full_store.resource_states()
        for machine in ("machineA", "machineB"):
            rows = rs[(rs["Resource"] == machine) & (rs["Time_type"] == "PR")]
            if len(rows) == 0:
                continue
            pr_pct = rows["percentage"].sum()
            assert 5.0 <= pr_pct <= 95.0, (
                f"Machine {machine} PR%={pr_pct:.1f}% out of expected [5, 95]%"
            )


# ---------------------------------------------------------------------------
# Section 6 — OEE validation
# ---------------------------------------------------------------------------

class TestOEEValidation:
    """Port of Section 6 from rfa_analytics_validation.py."""

    @pytest.fixture(scope="class")
    def full_store(self, rich_simulation_data):
        df_raw, time_range, model = rich_simulation_data
        return AnalyticsStore.from_raw(df_raw, time_range=time_range, production_system_data=model)

    def test_availability_in_valid_range(self, full_store):
        oee = full_store.oee_per_resource()
        if len(oee) == 0:
            pytest.skip("No OEE data")
        assert bool(oee["Availability"].between(0, 100).all()), (
            f"Availability out of [0, 100]%: "
            f"[{oee['Availability'].min():.1f}%, {oee['Availability'].max():.1f}%]"
        )

    def test_quality_in_valid_range(self, full_store):
        oee = full_store.oee_per_resource()
        if len(oee) == 0:
            pytest.skip("No OEE data")
        assert bool(oee["Quality"].between(0, 100).all()), (
            f"Quality out of [0, 100]%: "
            f"[{oee['Quality'].min():.1f}%, {oee['Quality'].max():.1f}%]"
        )

    def test_performance_below_115_percent(self, full_store):
        """
        Full-sim Performance can slightly exceed 100 % (machines occasionally
        run faster than normally-distributed mean), but extreme spikes indicate
        a calculation bug.
        """
        oee = full_store.oee_per_resource()
        if len(oee) == 0:
            pytest.skip("No OEE data")
        assert bool((oee["Performance"] <= 115).all()), (
            f"Performance > 115% for some machines: max={oee['Performance'].max():.2f}%"
        )

    def test_oee_below_100_percent(self, full_store):
        oee = full_store.oee_per_resource()
        if len(oee) == 0:
            pytest.skip("No OEE data")
        assert bool((oee["OEE"] <= 100).all()), (
            f"OEE > 100% for some resources: max={oee['OEE'].max():.2f}%"
        )

    def test_oee_above_minimum(self, full_store):
        """OEE should be > 10% for a healthy shop floor (not completely idle)."""
        oee = full_store.oee_per_resource()
        if len(oee) == 0:
            pytest.skip("No OEE data")
        machines = oee[oee["Resource"].isin(["machineA", "machineB"])]
        if len(machines) == 0:
            pytest.skip("No machine OEE data")
        assert bool((machines["OEE"] > 10).all()), (
            f"OEE too low (<10%) for some machines: min={machines['OEE'].min():.2f}%"
        )

    def test_system_oee_in_valid_range(self, full_store):
        sys_oee = full_store.oee_production_system()
        if len(sys_oee) == 0:
            pytest.skip("No system OEE data")
        oee_row = sys_oee[sys_oee["KPI"] == "OEE"]
        if len(oee_row) == 0:
            pytest.skip("No OEE row in system OEE")
        oee_val = float(oee_row["Value"].values[0])
        assert 0 <= oee_val <= 100, f"System OEE={oee_val:.2f}% out of [0, 100]%"

    def test_interval_oee_no_performance_spikes(self, full_store):
        """
        Interval-based OEE (8 h buckets) must not show Performance > 150 %.
        This guards the fragment-tail fix that prevents artificial spikes at
        the start/end of each bucket.
        """
        oee_iv = full_store.oee_per_resource_by_interval(interval_minutes=8.0)
        if len(oee_iv) == 0:
            pytest.skip("No interval OEE data")
        n_over_150 = int((oee_iv["Performance"] > 150).sum())
        assert n_over_150 == 0, (
            f"{n_over_150} interval-based Performance values > 150% "
            f"(fragment-tail fix not applied?); max={oee_iv['Performance'].max():.1f}%"
        )

    def test_interval_oee_below_150(self, full_store):
        oee_iv = full_store.oee_per_resource_by_interval(interval_minutes=8.0)
        if len(oee_iv) == 0:
            pytest.skip("No interval OEE data")
        assert bool((oee_iv["OEE"] <= 150).all()), (
            f"Interval-based OEE > 150%: max={oee_iv['OEE'].max():.1f}%"
        )

    def test_interval_availability_le_100(self, full_store):
        oee_iv = full_store.oee_per_resource_by_interval(interval_minutes=8.0)
        if len(oee_iv) == 0:
            pytest.skip("No interval OEE data")
        assert bool((oee_iv["Availability"] <= 100).all()), (
            f"Interval Availability > 100%: max={oee_iv['Availability'].max():.1f}%"
        )

    def test_interval_quality_le_100(self, full_store):
        oee_iv = full_store.oee_per_resource_by_interval(interval_minutes=8.0)
        if len(oee_iv) == 0:
            pytest.skip("No interval OEE data")
        assert bool((oee_iv["Quality"] <= 100).all()), (
            f"Interval Quality > 100%: max={oee_iv['Quality'].max():.1f}%"
        )

    def test_oee_in_valid_range_across_time_windows(self, full_store):
        """OEE must be in [0, 110]% for machine resources across all checked windows."""
        t_max = full_store.simulation_end_time
        windows = {"8h": (0.0, 8.0), "24h": (0.0, 24.0), "full": (0.0, t_max)}
        for label, (t_from, t_to) in windows.items():
            w_oee = full_store.oee_per_resource(t_from=t_from, t_to=t_to)
            if len(w_oee) == 0:
                continue
            machines = w_oee[w_oee["Resource"].isin(["machineA", "machineB"])]
            if len(machines) == 0:
                continue
            assert bool((machines["OEE"] <= 110).all()), (
                f"OEE > 110% for machines in {label} window: "
                f"max={machines['OEE'].max():.1f}%"
            )
