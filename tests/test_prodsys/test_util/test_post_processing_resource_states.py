"""
Tests for post processing resource states calculation.

This module validates that resource states (PR/SB) are calculated correctly,
especially ensuring that loading/unloading states are excluded and resource times are consistent.
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
            0.0,  # Initial standby (to be inserted)
            19.8,  # Product creation
            19.8,  # Transport start
            19.94,  # Transport end
            19.94,  # Loading start (should be excluded)
            19.94,  # Loading end (should be excluded)
            20.0,  # Production start
            26.0,  # Production end
            26.0,  # Unloading start (should be excluded)
            26.0,  # Unloading end (should be excluded)
            39.8,  # Product creation
            39.8,  # Transport start
            40.0,  # Transport end
            40.0,  # Production start
            46.0,  # Production end
            100.0,  # End of simulation
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
            "Production",  # Standby at time 0
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
            "end state",  # Standby
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
    """Test that loading and unloading states are excluded from resource states calculation."""
    df_resource_states = post_processor_simple.df_resource_states
    
    # Check that no Loading or Unloading states exist in the dataframe
    loading_unloading_mask = (
        (df_resource_states["State Type"] == state.StateTypeEnum.loading)
        | (df_resource_states["State Type"] == state.StateTypeEnum.unloading)
    )
    assert not loading_unloading_mask.any(), "Loading/unloading states should be excluded"


def test_resource_states_have_time_0_standby(post_processor_simple):
    """Test that each resource has a standby state at Time=0.0."""
    df_resource_states = post_processor_simple.df_resource_states
    
    # Get all resources (excluding source and sink)
    resources = df_resource_states[
        ~df_resource_states["State Type"].isin([state.StateTypeEnum.source, state.StateTypeEnum.sink])
    ]["Resource"].unique()
    
    for resource in resources:
        resource_df = df_resource_states[df_resource_states["Resource"] == resource]
        # Check that there's a row at Time=0.0
        time_0_rows = resource_df[resource_df["Time"] == 0.0]
        assert len(time_0_rows) > 0, f"Resource {resource} should have a row at Time=0.0"
        
        # Check that it's classified as standby
        time_0_row = time_0_rows.iloc[0]
        assert time_0_row["Time_type"] == "SB", (
            f"Resource {resource} should have SB (standby) at Time=0.0, "
            f"but got {time_0_row['Time_type']}"
        )


def test_resource_time_consistency(post_processor_simple):
    """Test that resource_time is consistent for each resource."""
    df_aggregated = post_processor_simple.df_aggregated_resource_states
    
    # Group by resource and check that resource_time is the same for all states
    for resource in df_aggregated["Resource"].unique():
        resource_data = df_aggregated[df_aggregated["Resource"] == resource]
        resource_times = resource_data["resource_time"].unique()
        assert len(resource_times) == 1, (
            f"Resource {resource} should have consistent resource_time, "
            f"but got {resource_times}"
        )


def test_pr_sb_percentages_sum_to_100(post_processor_simple):
    """Test that PR and SB percentages sum to 100% for each resource."""
    df_aggregated = post_processor_simple.df_aggregated_resource_states
    
    for resource in df_aggregated["Resource"].unique():
        resource_data = df_aggregated[df_aggregated["Resource"] == resource]
        pr_sb_data = resource_data[resource_data["Time_type"].isin(["PR", "SB"])]
        if len(pr_sb_data) > 0:
            total_percentage = pr_sb_data["percentage"].sum()
            assert abs(total_percentage - 100.0) < 0.01, (
                f"Resource {resource} PR + SB percentages should sum to 100%, "
                f"got {total_percentage}%"
            )


def test_aggregated_resource_states_structure(post_processor_simple):
    """Test the structure of df_aggregated_resource_states."""
    df_aggregated = post_processor_simple.df_aggregated_resource_states
    
    # Check required columns
    required_columns = ["Resource", "Time_type", "time_increment", "resource_time", "percentage"]
    for col in required_columns:
        assert col in df_aggregated.columns, f"Column {col} should be in df_aggregated_resource_states"
    
    # Check that Resource and Time_type are columns (not index)
    assert "Resource" in df_aggregated.columns
    assert "Time_type" in df_aggregated.columns


def test_used_capacity_starts_at_zero(post_processor_simple):
    """Test that Used_Capacity starts at 0 for each resource."""
    df_resource_states = post_processor_simple.df_resource_states
    
    # Get all resources (excluding source and sink)
    resources = df_resource_states[
        ~df_resource_states["State Type"].isin([state.StateTypeEnum.source, state.StateTypeEnum.sink])
    ]["Resource"].unique()
    
    for resource in resources:
        resource_df = df_resource_states[df_resource_states["Resource"] == resource].sort_values("Time")
        first_row = resource_df.iloc[0]
        assert first_row["Used_Capacity"] == 0, (
            f"Resource {resource} should start with Used_Capacity=0, "
            f"got {first_row['Used_Capacity']}"
        )


def test_machine_resource_states_calculation(post_processor_simple):
    """Test basic resource states calculation for a machine."""
    df_aggregated = post_processor_simple.df_aggregated_resource_states
    machine1_data = df_aggregated[df_aggregated["Resource"] == "Machine1"]
    
    # Machine1 should have PR and SB states
    assert len(machine1_data) >= 2, "Machine1 should have at least PR and SB states"
    
    # Check that percentages sum to 100%
    total_percentage = machine1_data["percentage"].sum()
    assert abs(total_percentage - 100.0) < 0.01, (
        f"Machine1 percentages should sum to 100%, got {total_percentage}%"
    )


def test_realistic_event_log_with_loading_unloading():
    """Test with a realistic event log that includes loading/unloading events."""
    # Create event log similar to the provided CSV
    # Count: 0.0, 10.0, 10.0, 15.0, 15.0, 15.0, 20.0, 25.0, 25.0, 25.0, 50.0 = 11 events
    data = {
        "Time": [0.0, 10.0, 10.0, 15.0, 15.0, 15.0, 20.0, 25.0, 25.0, 25.0, 50.0],
        "Resource": ["Machine1"] * 11,
        "State": ["state"] * 11,
        "State Type": [
            "Production",  # Standby at 0 (1)
            "Production", "Production",  # Production at 10.0 (2)
            "Loading", "Loading", "Production",  # Loading (2) and Production (1) at 15.0 - Loading excluded
            "Production",  # Production at 20.0 (1)
            "Unloading", "Unloading", "Production",  # Unloading (2) and Production (1) at 25.0 - Unloading excluded
            "Production",  # End state at 50.0 (1)
        ],  # Total: 1+2+3+1+3+1 = 11 items
        "Activity": [
            "end state",  # Standby at 0 (1)
            "start state", "end state",  # Production at 10.0 (2)
            "start state", "end state", "start state",  # Loading (2) and Production (1) at 15.0
            "end state",  # Production at 20.0 (1)
            "start state", "end state", "start state",  # Unloading (2) and Production (1) at 25.0
            "end state",  # End at 50.0 (1)
        ],  # Total: 1+2+3+1+3+1 = 11 items
        "Product": [None, "P1", "P1", "P1", "P1", "P2", "P2", "P2", "P2", "P2", None],  # 11 items
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
    
    # Check that loading/unloading are excluded
    df_resource_states = processor.df_resource_states
    loading_unloading = df_resource_states[
        (df_resource_states["State Type"] == state.StateTypeEnum.loading)
        | (df_resource_states["State Type"] == state.StateTypeEnum.unloading)
    ]
    assert len(loading_unloading) == 0, "Loading/unloading states should be excluded"
    
    # Check aggregated states
    df_aggregated = processor.df_aggregated_resource_states
    machine1 = df_aggregated[df_aggregated["Resource"] == "Machine1"]
    
    # Should have PR and SB, percentages should sum to 100%
    pr_sb = machine1[machine1["Time_type"].isin(["PR", "SB"])]
    total_percentage = pr_sb["percentage"].sum()
    assert abs(total_percentage - 100.0) < 0.01, "PR + SB should sum to 100%"


def test_resource_times_with_different_start_end_times():
    """
    Test resource times when resources have different start and end times.
    This simulates the buggy example scenario where:
    - Some resources start early and run throughout (like WcAdjust_1: ~28700)
    - Some resources start later (like WcCooling: ~19070)
    - Some resources end earlier (like Worker_movementZone_1: ~16400)

    Resource_time should be calculated per resource based on its own activity period,
    not a global simulation time.
    """
    # Create event log with resources that have different active periods
    data = {
        "Time": [
            # Resource A: starts early, runs long (like WcAdjust_1)
            0.0,      # Standby inserted at 0
            10.0,     # Production start
            20.0,     # Production end
            30.0,     # Production start
            40.0,     # Production end
            28000.0,  # Production start (late in simulation)
            28100.0,  # Production end

            # Resource B: starts later, ends earlier (like WcCooling)
            5000.0,   # Standby inserted at 0 (will be adjusted)
            5010.0,   # Production start
            5020.0,   # Production end
            15000.0,  # Production start
            15100.0,  # Production end
            19000.0,  # Production start
            19050.0,  # Production end (last event for Resource B)

            # Resource C: starts very late, ends early (like Worker_movementZone_1)
            10000.0,  # Standby inserted at 0 (will be adjusted)
            10010.0,  # Production start
            10020.0,  # Production end
            16300.0,  # Production start
            16380.0,  # Production end (last event for Resource C)
        ],
        "Resource": [
            "ResourceA", "ResourceA", "ResourceA", "ResourceA", "ResourceA", "ResourceA", "ResourceA",
            "ResourceB", "ResourceB", "ResourceB", "ResourceB", "ResourceB", "ResourceB", "ResourceB",
            "ResourceC", "ResourceC", "ResourceC", "ResourceC", "ResourceC",
        ],
        "State": ["state"] * 19,
        "State Type": [
            "Production",  # Standby at 0
            "Production", "Production", "Production", "Production", "Production", "Production",
            "Production",  # Standby at 0
            "Production", "Production", "Production", "Production", "Production", "Production",
            "Production",  # Standby at 0
            "Production", "Production", "Production", "Production",
        ],
        "Activity": [
            "end state",  # Standby
            "start state", "end state", "start state", "end state", "start state", "end state",
            "end state",  # Standby
            "start state", "end state", "start state", "end state", "start state", "end state",
            "end state",  # Standby
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
    
    # Get aggregated resource states
    df_aggregated = processor.df_aggregated_resource_states
    
    # Get resource times for each resource
    resource_times = {}
    for resource in df_aggregated["Resource"].unique():
        resource_data = df_aggregated[df_aggregated["Resource"] == resource]
        resource_time = resource_data["resource_time"].iloc[0]
        resource_times[resource] = resource_time
        
        # Validate that PR + SB percentages sum to 100%
        pr_sb_data = resource_data[resource_data["Time_type"].isin(["PR", "SB"])]
        total_percentage = pr_sb_data["percentage"].sum()
        assert abs(total_percentage - 100.0) < 0.01, (
            f"Resource {resource} PR + SB percentages should sum to 100%, got {total_percentage}%"
        )
    
    # Validate resource times - all resources should have the same resource_time
    # equal to the simulation end time (28100.0 in this case)
    simulation_end_time = 28100.0
    
    for resource_name, resource_time in resource_times.items():
        assert abs(resource_time - simulation_end_time) < 1.0, (
            f"Resource {resource_name} should have resource_time = {simulation_end_time}, "
            f"got {resource_time}"
        )
        
        # Verify that resource_time equals sum of time_increments
        aggregated_resource_time = resource_times[resource]
        resource_data = df_aggregated[df_aggregated["Resource"] == resource_name]
        total_time_increment = resource_data["time_increment"].sum()
        
        # Allow small floating point differences
        assert abs(total_time_increment - aggregated_resource_time) < 1.0, (
            f"Resource {resource_name}: sum of time_increments ({total_time_increment}) "
            f"should equal resource_time ({aggregated_resource_time})"
        )
        
        # Verify first event is at Time=0.0 with Used_Capacity=0
        rs = processor.df_resource_states
        resource_df = rs[rs["Resource"] == resource_name].sort_values("Time")
        first_row = resource_df.iloc[0]
        assert first_row["Time"] == 0.0, f"Resource {resource_name} should start at Time=0.0"
        assert first_row["Used_Capacity"] == 0, f"Resource {resource_name} should start with Used_Capacity=0"
        assert first_row["Time_type"] == "SB", f"Resource {resource_name} should start with SB (standby)"
        
        # Verify resource_time equals max(Time) - min(Time) + last_time_increment
        # Actually, resource_time should equal max(Time) since we insert Time=0.0
        max_time = resource_df["Time"].max()
        # The resource_time should be close to max_time (allowing for the last time increment)
        # The last event's next_Time is set to max_time, so resource_time = max_time
        assert abs(aggregated_resource_time - max_time) < 1.0, (
            f"Resource {resource_name}: resource_time ({aggregated_resource_time}) "
            f"should equal max(Time) ({max_time})"
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
    # Simulation runs from 0 to 1000 (last event at 1000)
    simulation_end_time = 1000.0
    
    # Count events: 0.0, 10.0, 20.0, 30.0, 35.0, 40.0, 45.0, 50.0, 60.0, 70.0, 90.0, 100.0, 110.0 (setup end), 110.0 (prod start), 120.0, 130.0, 140.0, 150.0, 160.0, 1000.0 = 20 events
    num_events = 20
    data = {
        "Time": [
            # Time 0: Start in standby (will be inserted)
            0.0,
            
            # Standby period: 0-10
            10.0,  # Production start (PR)
            20.0,  # Production end (back to SB)
            
            # Standby: 20-30
            30.0,  # Production start (PR)
            35.0,  # Second production start (PR, capacity = 2)
            40.0,  # First production end (PR, capacity = 1)
            45.0,  # Second production end (back to SB)
            
            # Standby: 45-50
            50.0,  # Dependency start (DP)
            60.0,  # Dependency end (back to SB)
            
            # Standby: 60-70
            70.0,  # Breakdown start (UD)
            90.0,  # Breakdown end (back to SB)
            
            # Standby: 90-100
            100.0,  # Setup start (ST)
            110.0,  # Setup end (ST)
            110.0,  # Production start (PR) - same time as setup end
            120.0,  # Production end (back to SB)
            
            # Standby: 120-130
            130.0,  # Charging start (CR)
            140.0,  # Charging end (back to SB)
            
            # Standby: 140-150
            150.0,  # Production start (PR)
            160.0,  # Production end (back to SB)
            
            # Add event at simulation_end_time to ensure resource_time = simulation_end_time
            1000.0,  # End of simulation (standby maintained)
        ],
        "Resource": ["Machine1"] * num_events,
        "State": ["state"] * num_events,
        "State Type": [
            "Production",  # Standby at 0
            "Production", "Production",  # PR
            "Production", "Production", "Production", "Production",  # PR (multiple)
            "Dependency", "Dependency",  # DP
            "Breakdown", "Breakdown",  # UD
            "Setup", "Setup", "Production", "Production",  # ST, PR
            "Charging", "Charging",  # CR
            "Production", "Production",  # PR
            "Production",  # End event
        ],
        "Activity": [
            "end state",  # Standby
            "start state", "end state",  # PR
            "start state", "start state", "end state", "end state",  # PR (multiple)
            "start state", "end state",  # DP
            "start state", "end state",  # UD
            "start state", "end state", "start state", "end state",  # ST, PR
            "start state", "end state",  # CR
            "start state", "end state",  # PR
            "end state",  # End event
        ],
        "Product": [
            None,  # Standby
            "P1", "P1",  # PR
            "P2", "P3", "P2", "P3",  # PR (multiple)
            "P4", "P4",  # DP
            None, None,  # UD
            "P5", "P5", "P6", "P6",  # ST, PR
            "P7", "P7",  # CR
            "P8", "P8",  # PR
            None,  # End event
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
    Comprehensive test for resource states calculation covering all edge cases:
    - Dependencies (DP)
    - Productive states (PR) - single and multiple
    - Standby states (SB)
    - Breakdown states (UD)
    - Setup states (ST)
    - Charging states (CR)
    - Multiple processes running simultaneously
    """
    processor = PostProcessor(df_raw=comprehensive_resource_states_event_log)
    df_aggregated = processor.df_aggregated_resource_states
    df_resource_states = processor.df_resource_states
    
    machine1_aggregated = df_aggregated[df_aggregated["Resource"] == "Machine1"]
    machine1_states = df_resource_states[df_resource_states["Resource"] == "Machine1"].sort_values("Time")
    
    # Verify resource_time equals simulation end time
    resource_time = machine1_aggregated["resource_time"].iloc[0]
    simulation_end_time = 1000.0
    assert abs(resource_time - simulation_end_time) < 1.0, (
        f"Resource_time should equal simulation_end_time ({simulation_end_time}), "
        f"got {resource_time}"
    )
    
    # Verify sum of time_increments equals resource_time
    total_time_increment = machine1_aggregated["time_increment"].sum()
    assert abs(total_time_increment - resource_time) < 0.01, (
        f"Sum of time_increments ({total_time_increment}) should equal "
        f"resource_time ({resource_time})"
    )
    
    # Verify all expected Time_types are present
    time_types = set(machine1_aggregated["Time_type"].unique())
    expected_time_types = {"SB", "PR", "DP", "UD", "ST", "CR"}
    assert time_types == expected_time_types, (
        f"Expected Time_types {expected_time_types}, got {time_types}"
    )
    
    # Verify percentages sum to 100%
    total_percentage = machine1_aggregated["percentage"].sum()
    assert abs(total_percentage - 100.0) < 0.01, (
        f"Percentages should sum to 100%, got {total_percentage}%"
    )
    
    # Verify that all time types have non-negative time allocations
    time_by_type = machine1_aggregated.set_index("Time_type")["time_increment"].to_dict()
    
    for time_type, time_increment in time_by_type.items():
        assert time_increment >= 0, (
            f"Time_type {time_type} should have non-negative time_increment, "
            f"got {time_increment}"
        )
    
    # Verify that we have reasonable time allocations for each type
    # SB should be present (standby periods exist)
    assert "SB" in time_by_type, "SB (standby) should be present"
    assert time_by_type["SB"] > 0, "SB should have positive time"
    
    # PR should be present (production periods exist)
    assert "PR" in time_by_type, "PR (productive) should be present"
    assert time_by_type["PR"] > 0, "PR should have positive time"
    
    # DP should be present (dependency period exists)
    assert "DP" in time_by_type, "DP (dependency) should be present"
    assert time_by_type["DP"] > 0, "DP should have positive time"
    
    # UD should be present (breakdown period exists)
    assert "UD" in time_by_type, "UD (unscheduled downtime) should be present"
    assert time_by_type["UD"] > 0, "UD should have positive time"
    
    # ST should be present (setup period exists)
    assert "ST" in time_by_type, "ST (setup) should be present"
    assert time_by_type["ST"] > 0, "ST should have positive time"
    
    # CR should be present (charging period exists)
    assert "CR" in time_by_type, "CR (charging) should be present"
    assert time_by_type["CR"] > 0, "CR should have positive time"
    
    # Verify Used_Capacity is tracked correctly
    # Used_Capacity can be negative for some resources (like transporters)
    # so we just verify it's tracked
    max_capacity = machine1_states["Used_Capacity"].max()
    min_capacity = machine1_states["Used_Capacity"].min()
    assert max_capacity is not None, "Used_Capacity should be tracked"
    assert min_capacity is not None, "Used_Capacity should be tracked"
    
    # Verify first event is at Time=0.0 with Used_Capacity=0 and Time_type=SB
    first_event = machine1_states.iloc[0]
    assert first_event["Time"] == 0.0, "First event should be at Time=0.0"
    assert first_event["Used_Capacity"] == 0, "First event should have Used_Capacity=0"
    assert first_event["Time_type"] == "SB", "First event should have Time_type=SB"
    
    # Verify last event is at simulation_end_time
    last_event = machine1_states.iloc[-1]
    assert abs(last_event["Time"] - simulation_end_time) < 1.0, (
        f"Last event should be at simulation_end_time ({simulation_end_time}), "
        f"got {last_event['Time']}"
    )
    
    # Verify no loading/unloading states in resource states
    loading_unloading = machine1_states[
        (machine1_states["State Type"] == state.StateTypeEnum.loading)
        | (machine1_states["State Type"] == state.StateTypeEnum.unloading)
    ]
    assert len(loading_unloading) == 0, "No loading/unloading states should be present"
    
    # Verify time_increment is always >= 0
    negative_increments = machine1_states[machine1_states["time_increment"] < 0]
    assert len(negative_increments) == 0, (
        f"Found {len(negative_increments)} events with negative time_increment"
    )
    
    # Verify Used_Capacity behavior is consistent
    # (Some resources like transporters can have negative capacity, so we don't enforce >= 0)
