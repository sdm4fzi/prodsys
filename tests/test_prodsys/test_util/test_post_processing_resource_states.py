"""
Tests for post processing resource states calculation.

Validates that:
- Loading/unloading states are excluded from aggregated resource states
- Percentages sum to 100% per resource
- All expected state types are present
- Resource time is consistent
"""

import pytest
import pandas as pd
from prodsys.util.post_processing import PostProcessor
from prodsys.simulation import state


@pytest.fixture
def simplified_event_log_with_loading():
    """
    Creates a simplified event log similar to the provided CSV that includes:
    - Loading/unloading states that should be excluded
    - Production states (PR)
    - Standby states (SB)
    - Transport states
    """
    data = {
        "Time": [
            0.0,
            19.8,
            19.8,
            19.94,
            19.94,
            19.94,
            20.0,
            26.0,
            26.0,
            26.0,
            39.8,
            39.8,
            40.0,
            40.0,
            46.0,
            100.0,
        ],
        "Resource": [
            "Machine1",
            "source",
            "Transport1",
            "Transport1",
            "Machine1",
            "Machine1",
            "Machine1",
            "Machine1",
            "Machine1",
            "Machine1",
            "source",
            "Transport1",
            "Transport1",
            "Machine1",
            "Machine1",
            "Machine1",
        ],
        "State": [
            "State1",
            "source_state",
            "transport_state",
            "transport_state",
            "loading_state",
            "loading_state",
            "production_state",
            "production_state",
            "unloading_state",
            "unloading_state",
            "source_state",
            "transport_state",
            "transport_state",
            "production_state",
            "production_state",
            "State1",
        ],
        "State Type": [
            "Production",
            "Source",
            "Transport",
            "Transport",
            "Loading",
            "Loading",
            "Production",
            "Production",
            "Unloading",
            "Unloading",
            "Source",
            "Transport",
            "Transport",
            "Production",
            "Production",
            "Production",
        ],
        "Activity": [
            "end state",
            "created product",
            "start state",
            "end state",
            "start state",
            "end state",
            "start state",
            "end state",
            "start state",
            "end state",
            "created product",
            "start state",
            "end state",
            "start state",
            "end state",
            "end state",
        ],
        "Product": [
            None,
            "Product_1",
            "Product_1",
            "Product_1",
            "Product_1",
            "Product_1",
            "Product_1",
            "Product_1",
            "Product_1",
            "Product_1",
            "Product_2",
            "Product_2",
            "Product_2",
            "Product_2",
            "Product_2",
            None,
        ],
        "Expected End Time": [None] * 16,
        "Origin location": [None] * 16,
        "Target location": [None] * 16,
        "Empty Transport": [None] * 16,
        "Requesting Item": [None] * 16,
        "Dependency": [None] * 16,
        "process": [None] * 16,
        "Initial Transport Step": [None] * 16,
        "Last Transport Step": [None] * 16,
    }
    return pd.DataFrame(data)


@pytest.fixture
def post_processor_simple(simplified_event_log_with_loading):
    """Creates a PostProcessor instance with the simplified event log."""
    return PostProcessor(df_raw=simplified_event_log_with_loading)


def test_loading_unloading_states_excluded(post_processor_simple):
    """Test that loading and unloading states are excluded from aggregated resource states."""
    df_aggregated = post_processor_simple.df_aggregated_resource_states

    assert "Loading" not in df_aggregated["Time_type"].values, (
        "Loading should be excluded from aggregated resource states"
    )
    assert "Unloading" not in df_aggregated["Time_type"].values, (
        "Unloading should be excluded from aggregated resource states"
    )


def test_resource_states_have_standby(post_processor_simple):
    """Test that each non-source/sink resource has standby time in aggregated states."""
    df_aggregated = post_processor_simple.df_aggregated_resource_states

    resources = df_aggregated["Resource"].unique()
    for resource in resources:
        resource_data = df_aggregated[df_aggregated["Resource"] == resource]
        time_types = set(resource_data["Time_type"].values)
        assert "SB" in time_types, (
            f"Resource {resource} should have SB (standby) in aggregated states"
        )


def test_resource_time_consistency(post_processor_simple):
    """Test that resource_time is consistent for each resource."""
    df_aggregated = post_processor_simple.df_aggregated_resource_states

    for resource in df_aggregated["Resource"].unique():
        resource_data = df_aggregated[df_aggregated["Resource"] == resource]
        resource_times = resource_data["resource_time"].unique()
        assert len(resource_times) == 1, (
            f"Resource {resource} should have consistent resource_time, "
            f"but got {resource_times}"
        )


def test_pr_sb_percentages_sum_to_100(post_processor_simple):
    """Test that all state percentages sum to 100% for each resource."""
    df_aggregated = post_processor_simple.df_aggregated_resource_states

    for resource in df_aggregated["Resource"].unique():
        resource_data = df_aggregated[df_aggregated["Resource"] == resource]
        total_percentage = resource_data["percentage"].sum()
        assert abs(total_percentage - 100.0) < 0.01, (
            f"Resource {resource} percentages should sum to 100%, "
            f"got {total_percentage}%"
        )


def test_aggregated_resource_states_structure(post_processor_simple):
    """Test the structure of df_aggregated_resource_states."""
    df_aggregated = post_processor_simple.df_aggregated_resource_states

    required_columns = ["Resource", "Time_type", "time_increment", "resource_time", "percentage"]
    for col in required_columns:
        assert col in df_aggregated.columns, f"Column {col} should be in df_aggregated_resource_states"


def test_used_capacity_starts_at_zero(post_processor_simple):
    """Test that machine has both PR and SB states (capacity starts at 0 = standby)."""
    df_aggregated = post_processor_simple.df_aggregated_resource_states

    for resource in df_aggregated["Resource"].unique():
        resource_data = df_aggregated[df_aggregated["Resource"] == resource]
        time_types = set(resource_data["Time_type"].values)
        assert "SB" in time_types, (
            f"Resource {resource} should have SB state "
            f"(implying capacity starts at 0)"
        )


def test_machine_resource_states_calculation(post_processor_simple):
    """Test basic resource states calculation for a machine."""
    df_aggregated = post_processor_simple.df_aggregated_resource_states
    machine1_data = df_aggregated[df_aggregated["Resource"] == "Machine1"]

    assert len(machine1_data) >= 2, "Machine1 should have at least PR and SB states"

    total_percentage = machine1_data["percentage"].sum()
    assert abs(total_percentage - 100.0) < 0.01, (
        f"Machine1 percentages should sum to 100%, got {total_percentage}%"
    )


def test_realistic_event_log_with_loading_unloading():
    """Test with a realistic event log that includes loading/unloading events."""
    data = {
        "Time": [0.0, 10.0, 10.0, 15.0, 15.0, 15.0, 20.0, 25.0, 25.0, 25.0, 50.0],
        "Resource": ["Machine1"] * 11,
        "State": ["state"] * 11,
        "State Type": [
            "Production",
            "Production", "Production",
            "Loading", "Loading", "Production",
            "Production",
            "Unloading", "Unloading", "Production",
            "Production",
        ],
        "Activity": [
            "end state",
            "start state", "end state",
            "start state", "end state", "start state",
            "end state",
            "start state", "end state", "start state",
            "end state",
        ],
        "Product": [None, "P1", "P1", "P1", "P1", "P2", "P2", "P2", "P2", "P2", None],
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
    df = pd.DataFrame(data)
    processor = PostProcessor(df_raw=df)

    df_aggregated = processor.df_aggregated_resource_states
    machine1 = df_aggregated[df_aggregated["Resource"] == "Machine1"]

    pr_sb = machine1[machine1["Time_type"].isin(["PR", "SB"])]
    total_percentage = pr_sb["percentage"].sum()
    assert abs(total_percentage - 100.0) < 0.01, "PR + SB should sum to 100%"


def test_resource_times_with_different_start_end_times():
    """
    Test resource times when resources have different start and end times.
    Resource_time should be the simulation end time (max Time across all resources).
    """
    data = {
        "Time": [
            # Resource A: active from 0 to 28100
            0.0, 10.0, 20.0, 30.0, 40.0, 28000.0, 28100.0,
            # Resource B: active from 5000 to 19050
            5000.0, 5010.0, 5020.0, 15000.0, 15100.0, 19000.0, 19050.0,
            # Resource C: active from 10000 to 16380
            10000.0, 10010.0, 10020.0, 16300.0, 16380.0,
        ],
        "Resource": [
            "ResourceA", "ResourceA", "ResourceA", "ResourceA", "ResourceA", "ResourceA", "ResourceA",
            "ResourceB", "ResourceB", "ResourceB", "ResourceB", "ResourceB", "ResourceB", "ResourceB",
            "ResourceC", "ResourceC", "ResourceC", "ResourceC", "ResourceC",
        ],
        "State": ["state"] * 19,
        "State Type": [
            "Production",
            "Production", "Production", "Production", "Production", "Production", "Production",
            "Production",
            "Production", "Production", "Production", "Production", "Production", "Production",
            "Production",
            "Production", "Production", "Production", "Production",
        ],
        "Activity": [
            "end state",
            "start state", "end state", "start state", "end state", "start state", "end state",
            "end state",
            "start state", "end state", "start state", "end state", "start state", "end state",
            "end state",
            "start state", "end state", "start state", "end state",
        ],
        "Product": [None] + ["P1"] * 6 + [None] + ["P2"] * 6 + [None] + ["P3"] * 4,
        "Expected End Time": [None] * 19,
        "Origin location": [None] * 19,
        "Target location": [None] * 19,
        "Empty Transport": [None] * 19,
        "Requesting Item": [None] * 19,
        "Dependency": [None] * 19,
        "process": [None] * 19,
        "Initial Transport Step": [None] * 19,
        "Last Transport Step": [None] * 19,
    }

    df = pd.DataFrame(data)
    processor = PostProcessor(df_raw=df)

    df_aggregated = processor.df_aggregated_resource_states

    resource_times = {}
    for resource in df_aggregated["Resource"].unique():
        resource_data = df_aggregated[df_aggregated["Resource"] == resource]
        resource_time = resource_data["resource_time"].iloc[0]
        resource_times[resource] = resource_time

        pr_sb_data = resource_data[resource_data["Time_type"].isin(["PR", "SB"])]
        total_percentage = pr_sb_data["percentage"].sum()
        assert abs(total_percentage - 100.0) < 0.01, (
            f"Resource {resource} PR + SB percentages should sum to 100%, got {total_percentage}%"
        )

    simulation_end_time = 28100.0
    for resource_name, resource_time in resource_times.items():
        assert abs(resource_time - simulation_end_time) < 1.0, (
            f"Resource {resource_name} should have resource_time = {simulation_end_time}, "
            f"got {resource_time}"
        )

        resource_data = df_aggregated[df_aggregated["Resource"] == resource_name]
        total_time_increment = resource_data["time_increment"].sum()

        assert abs(total_time_increment - resource_time) < 1.0, (
            f"Resource {resource_name}: sum of time_increments ({total_time_increment}) "
            f"should equal resource_time ({resource_time})"
        )


@pytest.fixture
def comprehensive_resource_states_event_log():
    """
    Creates a comprehensive event log for a single resource that tests all edge cases:
    - Standby states (SB)
    - Productive states (PR) - single and multiple processes
    - Dependency states (DP)
    - Breakdown/Unscheduled Downtime (UD)
    - Setup states (ST)
    - Charging states (CR)
    - Multiple processes running simultaneously (capacity > 1)
    - Events at the same time
    - Time gaps
    """
    simulation_end_time = 1000.0
    num_events = 20
    data = {
        "Time": [
            0.0,
            10.0, 20.0,
            30.0, 35.0, 40.0, 45.0,
            50.0, 60.0,
            70.0, 90.0,
            100.0, 110.0, 110.0, 120.0,
            130.0, 140.0,
            150.0, 160.0,
            1000.0,
        ],
        "Resource": ["Machine1"] * num_events,
        "State": ["state"] * num_events,
        "State Type": [
            "Production",
            "Production", "Production",
            "Production", "Production", "Production", "Production",
            "Dependency", "Dependency",
            "Breakdown", "Breakdown",
            "Setup", "Setup", "Production", "Production",
            "Charging", "Charging",
            "Production", "Production",
            "Production",
        ],
        "Activity": [
            "end state",
            "start state", "end state",
            "start state", "start state", "end state", "end state",
            "start state", "end state",
            "start state", "end state",
            "start state", "end state", "start state", "end state",
            "start state", "end state",
            "start state", "end state",
            "end state",
        ],
        "Product": [
            None,
            "P1", "P1",
            "P2", "P3", "P2", "P3",
            "P4", "P4",
            None, None,
            "P5", "P5", "P6", "P6",
            "P7", "P7",
            "P8", "P8",
            None,
        ],
        "Expected End Time": [None] * num_events,
        "Origin location": [None] * num_events,
        "Target location": [None] * num_events,
        "Empty Transport": [None] * num_events,
        "Requesting Item": [None] * num_events,
        "Dependency": [None] * num_events,
        "process": [None] * num_events,
        "Initial Transport Step": [None] * num_events,
        "Last Transport Step": [None] * num_events,
    }
    return pd.DataFrame(data)


def test_comprehensive_resource_states_edge_cases(comprehensive_resource_states_event_log):
    """
    Comprehensive test for resource states calculation covering all edge cases.
    """
    processor = PostProcessor(df_raw=comprehensive_resource_states_event_log)
    df_aggregated = processor.df_aggregated_resource_states

    machine1_aggregated = df_aggregated[df_aggregated["Resource"] == "Machine1"]

    resource_time = machine1_aggregated["resource_time"].iloc[0]
    simulation_end_time = 1000.0
    assert abs(resource_time - simulation_end_time) < 1.0, (
        f"Resource_time should equal simulation_end_time ({simulation_end_time}), "
        f"got {resource_time}"
    )

    total_time_increment = machine1_aggregated["time_increment"].sum()
    assert abs(total_time_increment - resource_time) < 0.01, (
        f"Sum of time_increments ({total_time_increment}) should equal "
        f"resource_time ({resource_time})"
    )

    time_types = set(machine1_aggregated["Time_type"].unique())
    expected_time_types = {"SB", "PR", "DP", "UD", "ST", "CR"}
    assert time_types == expected_time_types, (
        f"Expected Time_types {expected_time_types}, got {time_types}"
    )

    total_percentage = machine1_aggregated["percentage"].sum()
    assert abs(total_percentage - 100.0) < 0.01, (
        f"Percentages should sum to 100%, got {total_percentage}%"
    )

    time_by_type = machine1_aggregated.set_index("Time_type")["time_increment"].to_dict()

    for time_type, time_increment in time_by_type.items():
        assert time_increment >= 0, (
            f"Time_type {time_type} should have non-negative time_increment, "
            f"got {time_increment}"
        )

    assert "SB" in time_by_type, "SB (standby) should be present"
    assert time_by_type["SB"] > 0, "SB should have positive time"

    assert "PR" in time_by_type, "PR (productive) should be present"
    assert time_by_type["PR"] > 0, "PR should have positive time"

    assert "DP" in time_by_type, "DP (dependency) should be present"
    assert time_by_type["DP"] > 0, "DP should have positive time"

    assert "UD" in time_by_type, "UD (unscheduled downtime) should be present"
    assert time_by_type["UD"] > 0, "UD should have positive time"

    assert "ST" in time_by_type, "ST (setup) should be present"
    assert time_by_type["ST"] > 0, "ST should have positive time"

    assert "CR" in time_by_type, "CR (charging) should be present"
    assert time_by_type["CR"] > 0, "CR should have positive time"

    # Verify time_increment is always >= 0
    negative_increments = machine1_aggregated[machine1_aggregated["time_increment"] < 0]
    assert len(negative_increments) == 0, (
        f"Found {len(negative_increments)} rows with negative time_increment"
    )
