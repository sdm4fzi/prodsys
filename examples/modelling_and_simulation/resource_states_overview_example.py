"""
Resource states overview example.

Demonstrates all resource time types reported by prodsys analytics and how
configured states (breakdown, maintenance, setup, ...) interact with runtime
standby states (blocked, starved, idle, waiting for transport).

Time-type legend (``AnalyticsStore.resource_states()`` column ``Time_type``):

  PR  Productive work (production or transport)
  ST  Setup / changeover between processes
  UD  Unplanned downtime (breakdown)
  MT  Planned maintenance downtime
  CR  Charging (battery-powered transport)
  DP  Dependency (waiting for a required resource or process)
  NS  Non-scheduled period (e.g. shift break)
  BL  Blocked (output queue full)
  SV  Starved (input queue empty while the resource could work)
  ID  Idle (no work requested)
  WT  Waiting for transport (movable resource available, no transport job)

Run with::

    uv run python examples/modelling_and_simulation/resource_states_overview_example.py
"""

from __future__ import annotations

import sys
from typing import Dict, List, Tuple

import pandas as pd
import prodsys
import prodsys.express as psx
from prodsys.analytics.store import AnalyticsStore
from prodsys.models import port_data
from prodsys.simulation.runner import Runner

SIMULATION_TIME = 240.0

TIME_TYPE_LEGEND: Dict[str, str] = {
    "PR": "Production / transport",
    "ST": "Setup",
    "UD": "Breakdown (unplanned downtime)",
    "MT": "Maintenance (planned downtime)",
    "CR": "Charging",
    "DP": "Dependency wait",
    "NS": "Non-scheduled (shift off)",
    "BL": "Blocked (output queue full)",
    "SV": "Starved (input queue empty)",
    "ID": "Idle",
    "WT": "Waiting for transport",
}

# Each time type must appear on at least one resource with duration > 0.
# SV is optional: it only occurs when a process starts loading before the
# product has arrived in the input queue (rare with default scheduling).
REQUIRED_TIME_TYPES: List[str] = [
    "PR",
    "ST",
    "UD",
    "MT",
    "CR",
    "DP",
    "NS",
    "BL",
    "ID",
    "WT",
]

OPTIONAL_TIME_TYPES: List[str] = ["SV"]


def build_system() -> psx.ProductionSystem:
    process_a = psx.ProductionProcess(
        psx.FunctionTimeModel("constant", 2.0, 0.0, ID="process_a_time"),
        ID="p_a",
    )
    process_b = psx.ProductionProcess(
        psx.FunctionTimeModel("constant", 2.5, 0.0, ID="process_b_time"),
        ID="p_b",
    )
    transport_process = psx.TransportProcess(
        psx.DistanceTimeModel(speed=12, reaction_time=1.0, ID="transport_time"),
        ID="tp",
    )
    worker_move = psx.TransportProcess(
        psx.DistanceTimeModel(speed=60, reaction_time=0.2, ID="worker_move_time"),
        ID="worker_move",
    )

    setup_time = psx.FunctionTimeModel("constant", 1.0, 0.0, ID="setup_time")
    setup_a_to_b = psx.SetupState(setup_time, process_a, process_b, ID="setup_a_b")
    setup_b_to_a = psx.SetupState(setup_time, process_b, process_a, ID="setup_b_a")

    breakdown = psx.BreakDownState(
        psx.FunctionTimeModel("constant", 70.0, 0.0, ID="breakdown_interval"),
        psx.FunctionTimeModel("constant", 4.0, 0.0, ID="breakdown_duration"),
        ID="breakdown",
    )
    maintenance = psx.MaintenanceState(
        psx.FunctionTimeModel("constant", 55.0, 0.0, ID="maintenance_interval"),
        psx.FunctionTimeModel("constant", 3.0, 0.0, ID="maintenance_duration"),
        ID="maintenance",
    )
    shift = psx.NonScheduledState(
        time_model=psx.FunctionTimeModel("constant", 35.0, 0.0, ID="shift_on"),
        non_scheduled_time_model=psx.FunctionTimeModel(
            "constant", 12.0, 0.0, ID="shift_off"
        ),
        ID="shift",
    )

    charging = psx.ChargingState(
        time_model=psx.FunctionTimeModel("constant", 4.0, 0.0, ID="charge_time"),
        battery_time_model=psx.FunctionTimeModel("constant", 25.0, 0.0, ID="battery_time"),
        ID="charging",
    )

    worker_node = psx.Node(location=[5.0, 1.5], ID="worker_node")
    helper_process = psx.ProductionProcess(
        psx.FunctionTimeModel("constant", 0.8, 0.0, ID="helper_time"),
        ID="helper",
    )
    worker = psx.Resource(
        [worker_move, helper_process],
        [3.0, 6.0],
        1,
        ID="worker",
    )
    worker_dependency = psx.ProcessDependency(
        ID="worker_dependency",
        required_process=helper_process,
        interaction_node=worker_node,
    )

    machine = psx.Resource(
        [process_a, process_b],
        [5.0, 0.0],
        1,
        states=[setup_a_to_b, setup_b_to_a, breakdown, maintenance, shift],
        dependencies=[worker_dependency],
        ID="machine",
    )
    machine.ports = [
        psx.Queue(
            ID="machine_input",
            capacity=1,
            location=[5.0, 0.0],
            interface_type=port_data.PortInterfaceType.INPUT,
        ),
        psx.Queue(
            ID="machine_output",
            capacity=1,
            location=[5.0, 0.0],
            interface_type=port_data.PortInterfaceType.OUTPUT,
        ),
    ]

    transport = psx.Resource(
        [transport_process],
        [0.0, 0.0],
        1,
        states=[charging],
        ID="transport",
    )

    product_a = psx.Product(
        process=[process_a], transport_process=transport_process, ID="product_a"
    )
    product_b = psx.Product(
        process=[process_b], transport_process=transport_process, ID="product_b"
    )

    source_a = psx.Source(
        product_a,
        psx.FunctionTimeModel("constant", 2.0, 0.0, ID="arrival_a"),
        [0.0, 0.0],
        ID="source_a",
    )
    source_b = psx.Source(
        product_b,
        psx.FunctionTimeModel("constant", 2.5, 0.0, ID="arrival_b"),
        [0.0, 2.0],
        ID="source_b",
    )

    sink_a = psx.Sink(product_a, [10.0, 0.0], ID="sink_a")
    sink_b = psx.Sink(product_b, [10.0, 2.0], ID="sink_b")

    return psx.ProductionSystem(
        [machine, transport, worker],
        [source_a, source_b],
        [sink_a, sink_b],
    )


def print_legend() -> None:
    print("Resource time types")
    print("-" * 60)
    for code, description in TIME_TYPE_LEGEND.items():
        print(f"  {code:3}  {description}")
    print()


def print_state_table(resource_states: pd.DataFrame) -> None:
    pivot = (
        resource_states.groupby(["Resource", "Time_type"])[["time_increment", "percentage"]]
        .sum()
        .reset_index()
        .sort_values(["Resource", "Time_type"])
    )
    print("Observed resource states")
    print("-" * 60)
    for resource in sorted(pivot["Resource"].unique()):
        print(f"\n{resource}")
        rows = pivot[pivot["Resource"] == resource]
        for _, row in rows.iterrows():
            code = row["Time_type"]
            label = TIME_TYPE_LEGEND.get(code, code)
            print(
                f"  {code:3}  {row['time_increment']:8.2f} min  "
                f"({row['percentage']:5.1f}%)  {label}"
            )


def _observed_time_types(resource_states: pd.DataFrame) -> Dict[str, List[str]]:
    by_type: Dict[str, List[str]] = {}
    for _, row in resource_states.iterrows():
        if float(row["time_increment"]) <= 0.0:
            continue
        by_type.setdefault(row["Time_type"], [])
        if row["Resource"] not in by_type[row["Time_type"]]:
            by_type[row["Time_type"]].append(row["Resource"])
    return by_type


def verify_expected_states(resource_states: pd.DataFrame) -> Tuple[List[str], List[str]]:
    observed = _observed_time_types(resource_states)
    missing = [code for code in REQUIRED_TIME_TYPES if code not in observed]
    optional_hit = [code for code in OPTIONAL_TIME_TYPES if code in observed]

    if missing:
        raise AssertionError(
            "Missing required time types: "
            + ", ".join(f"{code} (expected on some resource)" for code in missing)
        )

    return optional_hit, observed


def print_interaction_notes(observed: Dict[str, List[str]]) -> None:
    print("\nWhere each state appears in this run")
    print("-" * 60)
    mapping = {
        "PR": "machine, transport, worker — productive processing and moves",
        "ST": "machine — changeover between p_a and p_b",
        "UD": "machine — breakdown interrupts production",
        "MT": "machine — planned maintenance windows",
        "NS": "machine — shift-off periods",
        "DP": "worker — helper process bound while machine waits",
        "BL": "machine — output queue full (capacity 1)",
        "SV": "machine — only if loading starts before product reaches input queue",
        "ID": "machine — gaps between arrival batches",
        "CR": "transport — battery charging",
        "WT": "transport, worker — movable resources idle with pending demand",
    }
    for code, explanation in mapping.items():
        resources = ", ".join(observed.get(code, [])) or "(not observed)"
        print(f"  {code:3}  {resources:25}  {explanation}")

    print("\nInteraction highlights")
    print("-" * 60)
    notes = [
        "Alternating product types trigger setup (ST) on the shared machine.",
        "Breakdown (UD) and maintenance (MT) interrupt running production (PR).",
        "Shift state (NS) blocks the machine entirely during off periods.",
        "The worker dependency (DP) must finish before the machine can process.",
        "A full output queue (capacity 1) causes blocked time (BL) on the machine.",
        "Slow AGV transport and charging (CR) leave carriers in waiting-for-transport (WT).",
        "Gaps between arrivals leave the machine idle (ID).",
    ]
    for note in notes:
        print(f"  - {note}")
    print()


def main() -> None:
    print("prodsys version:", prodsys.VERSION)
    prodsys.set_logging("WARNING")

    print_legend()

    system = build_system()
    adapter = system.to_model()

    runner = Runner(production_system_data=adapter)
    runner.initialize_simulation()
    runner.run(SIMULATION_TIME)

    df_raw = runner.get_post_processor().df_raw
    store = AnalyticsStore.from_raw(df_raw, time_range=SIMULATION_TIME)
    resource_states = store.resource_states()

    print_state_table(resource_states)
    optional_hit, observed = verify_expected_states(resource_states)
    print_interaction_notes(observed)

    if optional_hit:
        print(f"Optional time types also observed: {', '.join(optional_hit)}")
    else:
        print("Note: SV (starved) did not occur — see interaction notes for when it appears.")
    print("\nAll required resource time types observed.\n")

    runner.print_results()
    runner.plot_results()


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"VERIFICATION FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
