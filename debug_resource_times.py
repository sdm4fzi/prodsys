#!/usr/bin/env python3
"""
Debugging script to analyze resource time calculations.

This script helps identify why some resources have different resource_time values
by examining the step-by-step calculation process.
"""

import pandas as pd
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from prodsys.util.post_processing import PostProcessor
from prodsys.simulation import state


def analyze_resource_times(filepath: str, resource_name: str = "WcAdjust_1"):
    """
    Analyze resource time calculations for a specific resource.
    
    Args:
        filepath: Path to the CSV file with simulation results
        resource_name: Name of the resource to analyze
    """
    print(f"Loading data from: {filepath}")
    processor = PostProcessor(filepath=filepath)
    
    print(f"\n{'='*80}")
    print(f"Analyzing resource: {resource_name}")
    print(f"{'='*80}\n")
    
    # Step 1: Check raw data for this resource
    print("STEP 1: Raw data for resource")
    print("-" * 80)
    df_raw_resource = processor.df_raw[processor.df_raw["Resource"] == resource_name].copy()
    print(f"Total events in raw data: {len(df_raw_resource)}")
    print(f"Time range: {df_raw_resource['Time'].min():.2f} to {df_raw_resource['Time'].max():.2f}")
    print(f"State Types present: {df_raw_resource['State Type'].unique()}")
    
    # Check for loading/unloading states
    loading_unloading = df_raw_resource[
        (df_raw_resource["State Type"] == state.StateTypeEnum.loading) |
        (df_raw_resource["State Type"] == state.StateTypeEnum.unloading) |
        (df_raw_resource["State Type"] == "Loading") |
        (df_raw_resource["State Type"] == "Unloading")
    ]
    print(f"Loading/Unloading events: {len(loading_unloading)}")
    if len(loading_unloading) > 0:
        print("\nLoading/Unloading events:")
        print(loading_unloading[["Time", "State Type", "Activity"]].head(10))
    
    # Step 2: Check prepared data
    print(f"\n\nSTEP 2: Prepared data (df_prepared)")
    print("-" * 80)
    df_prepared_resource = processor.df_prepared[processor.df_prepared["Resource"] == resource_name].copy()
    print(f"Total events after preparation: {len(df_prepared_resource)}")
    print(f"Time range: {df_prepared_resource['Time'].min():.2f} to {df_prepared_resource['Time'].max():.2f}")
    
    # Step 3: Check if loading/unloading are filtered
    print(f"\n\nSTEP 3: Loading/Unloading state filtering")
    print("-" * 80)
    loading_unloading_prepared = df_prepared_resource[
        (df_prepared_resource["State Type"] == state.StateTypeEnum.loading) |
        (df_prepared_resource["State Type"] == state.StateTypeEnum.unloading) |
        (df_prepared_resource["State Type"] == "Loading") |
        (df_prepared_resource["State Type"] == "Unloading")
    ]
    print(f"Loading/Unloading events in prepared data: {len(loading_unloading_prepared)}")
    
    # Step 4: Analyze resource states calculation
    print(f"\n\nSTEP 4: Resource states calculation")
    print("-" * 80)
    df_resource_states = processor.df_resource_states
    df_resource_states_resource = df_resource_states[df_resource_states["Resource"] == resource_name].copy()
    df_resource_states_resource = df_resource_states_resource.sort_values("Time")
    
    print(f"Total events in df_resource_states: {len(df_resource_states_resource)}")
    print(f"Time range: {df_resource_states_resource['Time'].min():.2f} to {df_resource_states_resource['Time'].max():.2f}")
    
    # Check for Time=0.0 event
    time_0_events = df_resource_states_resource[df_resource_states_resource["Time"] == 0.0]
    print(f"\nTime=0.0 events: {len(time_0_events)}")
    if len(time_0_events) > 0:
        print("First event (should be Time=0.0, SB, Used_Capacity=0):")
        print(time_0_events[["Time", "State_sorting_Index", "Used_Capacity", "Time_type", "Increment"]].head(1))
    
    # Check first few events
    print("\nFirst 10 events:")
    print(df_resource_states_resource[["Time", "State Type", "Activity", "State_sorting_Index", "Used_Capacity", "Time_type", "Increment", "time_increment"]].head(10))
    
    # Check last few events
    print("\nLast 10 events:")
    print(df_resource_states_resource[["Time", "State Type", "Activity", "State_sorting_Index", "Used_Capacity", "Time_type", "Increment", "time_increment", "next_Time"]].tail(10))
    
    # Step 5: Analyze time_increment calculations
    print(f"\n\nSTEP 5: Time increment analysis")
    print("-" * 80)
    print(f"Sum of time_increments: {df_resource_states_resource['time_increment'].sum():.2f}")
    print(f"Max Time: {df_resource_states_resource['Time'].max():.2f}")
    print(f"Min Time: {df_resource_states_resource['Time'].min():.2f}")
    
    # Check next_Time calculations
    last_event = df_resource_states_resource.iloc[-1]
    print(f"\nLast event:")
    print(f"  Time: {last_event['Time']:.2f}")
    print(f"  next_Time: {last_event.get('next_Time', 'N/A')}")
    print(f"  time_increment: {last_event['time_increment']:.2f}")
    
    # Step 6: Compare with aggregated results
    print(f"\n\nSTEP 6: Aggregated resource states")
    print("-" * 80)
    df_aggregated = processor.df_aggregated_resource_states
    resource_aggregated = df_aggregated[df_aggregated["Resource"] == resource_name]
    
    print(f"Resource states for {resource_name}:")
    print(resource_aggregated[["Time_type", "time_increment", "resource_time", "percentage"]])
    
    resource_time = resource_aggregated["resource_time"].iloc[0]
    total_time_increment = resource_aggregated["time_increment"].sum()
    print(f"\nTotal resource_time: {resource_time:.2f}")
    print(f"Sum of time_increments: {total_time_increment:.2f}")
    print(f"Difference: {abs(resource_time - total_time_increment):.2f}")
    
    # Step 7: Compare with another resource for reference
    print(f"\n\nSTEP 7: Comparison with reference resource (WcAdjust_2)")
    print("-" * 80)
    ref_resource = "WcAdjust_2"
    df_ref = processor.df_resource_states[processor.df_resource_states["Resource"] == ref_resource].copy()
    df_ref = df_ref.sort_values("Time")
    
    ref_aggregated = df_aggregated[df_aggregated["Resource"] == ref_resource]
    ref_resource_time = ref_aggregated["resource_time"].iloc[0]
    
    print(f"{resource_name}:")
    print(f"  Time range: {df_resource_states_resource['Time'].min():.2f} to {df_resource_states_resource['Time'].max():.2f}")
    print(f"  resource_time: {resource_time:.2f}")
    print(f"  Events: {len(df_resource_states_resource)}")
    
    print(f"\n{ref_resource}:")
    print(f"  Time range: {df_ref['Time'].min():.2f} to {df_ref['Time'].max():.2f}")
    print(f"  resource_time: {ref_resource_time:.2f}")
    print(f"  Events: {len(df_ref)}")
    
    print(f"\nDifference in resource_time: {abs(resource_time - ref_resource_time):.2f}")
    
    # Step 8: Check if the issue is with next_Time calculation
    print(f"\n\nSTEP 8: next_Time calculation analysis")
    print("-" * 80)
    
    # Check if next_Time is calculated per resource
    df_check = processor.df_resource_states.copy()
    
    # For the problematic resource
    df_check_resource = df_check[df_check["Resource"] == resource_name].sort_values("Time")
    max_time_resource = df_check_resource["Time"].max()
    last_event_check = df_check_resource.iloc[-1]
    
    print(f"For {resource_name}:")
    print(f"  Max Time: {max_time_resource:.2f}")
    print(f"  Last event Time: {last_event_check['Time']:.2f}")
    print(f"  Last event next_Time: {last_event_check.get('next_Time', 'N/A')}")
    print(f"  Expected next_Time (should equal max_time): {max_time_resource:.2f}")
    
    # Check if fillna is working correctly
    if 'next_Time' in df_check_resource.columns:
        null_next_times = df_check_resource[df_check_resource["next_Time"].isna()]
        print(f"  Null next_Time values: {len(null_next_times)}")
        if len(null_next_times) > 0:
            print("  WARNING: Found null next_Time values!")
            print(null_next_times[["Time", "next_Time", "time_increment"]])
    
    # For reference resource
    df_check_ref = df_check[df_check["Resource"] == ref_resource].sort_values("Time")
    max_time_ref = df_check_ref["Time"].max()
    last_event_ref = df_check_ref.iloc[-1]
    
    print(f"\nFor {ref_resource}:")
    print(f"  Max Time: {max_time_ref:.2f}")
    print(f"  Last event Time: {last_event_ref['Time']:.2f}")
    print(f"  Last event next_Time: {last_event_ref.get('next_Time', 'N/A')}")
    print(f"  Expected next_Time (should equal max_time): {max_time_ref:.2f}")
    
    # Step 9: Check if loading/unloading filtering is the issue
    print(f"\n\nSTEP 9: Loading/Unloading filtering check")
    print("-" * 80)
    
    # Check if we're filtering loading/unloading in df_resource_states
    loading_unloading_in_resource_states = df_resource_states_resource[
        (df_resource_states_resource["State Type"] == state.StateTypeEnum.loading) |
        (df_resource_states_resource["State Type"] == state.StateTypeEnum.unloading) |
        (df_resource_states_resource["State Type"] == "Loading") |
        (df_resource_states_resource["State Type"] == "Unloading")
    ]
    print(f"Loading/Unloading events in df_resource_states: {len(loading_unloading_in_resource_states)}")
    if len(loading_unloading_in_resource_states) > 0:
        print("WARNING: Loading/Unloading events found in df_resource_states!")
        print("These should be filtered out. Showing first few:")
        print(loading_unloading_in_resource_states[["Time", "State Type", "Activity"]].head(10))


if __name__ == "__main__":
    # Default file path
    default_file = "data/EKx_SKx_SplittedV24_full_20251216-171722.csv"
    
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        filepath = default_file
    
    resource_to_analyze = "WcAdjust_1"
    if len(sys.argv) > 2:
        resource_to_analyze = sys.argv[2]
    
    print(f"Resource Time Analysis Debugging Script")
    print(f"File: {filepath}")
    print(f"Resource: {resource_to_analyze}")
    print()
    
    try:
        analyze_resource_times(filepath, resource_to_analyze)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

