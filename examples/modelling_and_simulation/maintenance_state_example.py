"""
Example demonstrating MaintenanceState for planned maintenance downtime.

MaintenanceState behaves like BreakDownState: during maintenance the resource is
unavailable and running production/transport/setup processes are interrupted.

This example uses constant time models so maintenance events are easy to verify:
  - every 50 time units a maintenance event starts
  - each maintenance lasts 5 time units
"""

from __future__ import annotations

import sys

import prodsys
import prodsys.express as psx
from prodsys.analytics.store import AnalyticsStore
from prodsys.simulation.runner import Runner

SIMULATION_TIME = 500.0
MAINTENANCE_INTERVAL = 50.0
MAINTENANCE_DURATION = 5.0
MAINTENANCE_STATE_ID = "maintenance_state"
MACHINE_ID = "machine"


def build_system() -> psx.ProductionSystem:
    process_time = psx.FunctionTimeModel("constant", 2.0, 0.0, ID="process_time")
    transport_time = psx.FunctionTimeModel("constant", 0.5, 0.0, ID="transport_time")

    production = psx.ProductionProcess(process_time, ID="P1")
    transport = psx.TransportProcess(transport_time, ID="TP")

    maintenance_interval = psx.FunctionTimeModel(
        "constant", MAINTENANCE_INTERVAL, 0.0, ID="maintenance_interval"
    )
    maintenance_duration = psx.FunctionTimeModel(
        "constant", MAINTENANCE_DURATION, 0.0, ID="maintenance_duration"
    )
    maintenance = psx.MaintenanceState(
        maintenance_interval,
        maintenance_duration,
        ID=MAINTENANCE_STATE_ID,
    )

    machine = psx.Resource(
        [production],
        [5, 0],
        1,
        states=[maintenance],
        ID=MACHINE_ID,
    )
    agv = psx.Resource([transport], [2, 0], 1, ID="transport")

    product = psx.Product([production], transport, ID="product")
    source = psx.Source(
        product,
        psx.FunctionTimeModel("constant", 4.0, 0.0, ID="arrival"),
        [0, 0],
        ID="source",
    )
    sink = psx.Sink(product, [10, 0], ID="sink")

    return psx.ProductionSystem([machine, agv], [source], [sink])


def verify_maintenance_events(df_raw) -> None:
    """Check that Maintenance events appear as paired start/end intervals."""
    maint = df_raw[df_raw["State Type"] == "Maintenance"].copy()
    if maint.empty:
        raise AssertionError("No Maintenance events found in simulation log.")

    by_state = maint[maint["State"] == MAINTENANCE_STATE_ID]
    if by_state.empty:
        raise AssertionError(
            f"No events for state '{MAINTENANCE_STATE_ID}' found."
        )

    starts = by_state[by_state["Activity"] == "start state"]
    ends = by_state[by_state["Activity"] == "end state"]
    if len(starts) == 0 or len(ends) == 0:
        raise AssertionError(
            f"Expected start/end state pairs, got starts={len(starts)}, ends={len(ends)}."
        )

    if len(starts) != len(ends):
        raise AssertionError(
            f"Unequal start/end counts: starts={len(starts)}, ends={len(ends)}."
        )

    expected_count = int(SIMULATION_TIME // MAINTENANCE_INTERVAL)
    if len(starts) < expected_count - 1:
        raise AssertionError(
            f"Expected at least {expected_count - 1} maintenance cycles, got {len(starts)}."
        )

    durations = (ends["Time"].values - starts["Time"].values)[: len(starts)]
    if not all(abs(d - MAINTENANCE_DURATION) < 1e-6 for d in durations):
        raise AssertionError(
            f"Maintenance duration should be {MAINTENANCE_DURATION}, "
            f"got durations: {durations[:5]}..."
        )

    on_machine = by_state[by_state["Resource"] == MACHINE_ID]
    if on_machine.empty:
        raise AssertionError(f"No maintenance events on resource '{MACHINE_ID}'.")

    print(f"  Maintenance start/end pairs: {len(starts)}")
    print(f"  First maintenance at t={starts['Time'].iloc[0]:.1f}")
    print(f"  Last maintenance at t={starts['Time'].iloc[-1]:.1f}")
    print(f"  Sample durations: {list(durations[:3])}")


def verify_analytics(df_raw) -> None:
    """Check that analytics maps Maintenance to MT time type."""
    store = AnalyticsStore()
    store.ingest_events(df_raw)
    resource_states = store.resource_states()

    mt = resource_states[resource_states["Time_type"] == "MT"]
    if mt.empty:
        raise AssertionError("No MT (maintenance) time in analytics resource_states.")

    total_mt = float(mt["time_increment"].sum())
    if total_mt < MAINTENANCE_DURATION:
        raise AssertionError(f"MT time too low: {total_mt}")

    print(f"  Analytics MT time (total): {total_mt:.1f}")
    print(f"  Analytics MT rows: {len(mt)}")


def main() -> None:
    print("prodsys version:", prodsys.VERSION)
    prodsys.set_logging("WARNING")

    system = build_system()
    adapter = system.to_model()

    maint_states = [s for s in adapter.state_data if s.type.value == "MaintenanceState"]
    if len(maint_states) != 1:
        raise AssertionError("Expected exactly one MaintenanceState in adapter.")

    runner = Runner(production_system_data=adapter)
    runner.initialize_simulation()
    runner.run(SIMULATION_TIME)

    df_raw = runner.get_post_processor().df_raw
    print("\nMaintenance state example – event verification")
    print("-" * 50)
    verify_maintenance_events(df_raw)
    verify_analytics(df_raw)
    print("-" * 50)
    print("All checks passed.\n")

    runner.print_results()
    # runner.plot_results()


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"VERIFICATION FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
