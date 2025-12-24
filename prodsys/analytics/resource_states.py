"""
Resource states analytics module.

This module handles resource state calculations and aggregations.
"""

from __future__ import annotations

from functools import cached_property

import pandas as pd
import numpy as np

from prodsys.simulation import state
from prodsys.analytics.base import (
    AnalyticsContext,
    get_conditions_for_interface_state,
    get_conditions_for_process_state,
)
from prodsys.analytics.data_preparation import DataPreparation
from prodsys.analytics.throughput import ThroughputAnalytics

import logging

logger = logging.getLogger(__name__)


class ResourceStatesAnalytics:
    """
    Handles resource state calculations and aggregations.
    """
    
    def __init__(
        self,
        context: AnalyticsContext,
        data_prep: DataPreparation,
        throughput_analytics: ThroughputAnalytics,
    ):
        """
        Initialize resource states analytics.
        
        Args:
            context: Analytics context containing raw data and configuration.
            data_prep: Data preparation instance.
            throughput_analytics: Throughput analytics instance (for warm_up_cutoff_time).
        """
        self.context = context
        self.data_prep = data_prep
        self.throughput_analytics = throughput_analytics
    
    def _get_simulation_end_time(self) -> float:
        """Get simulation end time."""
        if self.context.time_range is not None:
            return self.context.time_range
        return self.data_prep.df_prepared["Time"].max()
    
    def _get_sink_source_queue_names(self) -> tuple[set, set]:
        """Get sink input queues and source output queues."""
        return self.context.get_sink_source_queue_names()
    
    def _get_system_resource_mapping(self) -> dict:
        """Get system resource mapping."""
        return self.context.get_system_resource_mapping()
    
    @cached_property
    def df_resource_states(self) -> pd.DataFrame:
        """
        Returns a data frame with the machine states and the time spent in each state.
        There are 5 different states a resource can spend its time:
            -SB: A resource is in standby state, could process but no product is available
            -PR: A resource is in productive state and performs a process
            -UD: A resource is in unscheduled downtime state due to a breakdown
            -ST: A resource is in setup state
            -CR: A resource is in charging state

        Returns:
            pd.DataFrame: Data frame with the machine states and the time spent in each state.
        """
        df = self.data_prep.df_prepared.copy()
        # Get the global simulation end time - use time_range if provided, otherwise use max Time
        simulation_end_time = self._get_simulation_end_time()
        
        # Exclude loading and unloading states from resource states calculation
        df = df.loc[
            (df["State Type"] != state.StateTypeEnum.loading)
            & (df["State Type"] != state.StateTypeEnum.unloading)
        ]
        
        # Get sink input queues and source output queues from production_system_data if available
        sink_input_queues, source_output_queues = self._get_sink_source_queue_names()
        
        # Identify source and sink resources and exclude all their events
        source_sink_resources = df.loc[
            (df["State Type"] == state.StateTypeEnum.source)
            | (df["State Type"] == state.StateTypeEnum.sink),
            "Resource"
        ].unique()
        
        # Combine sink/source resources and their queues (from production_system_data)
        # Fallback to pattern matching if production_system_data not available
        if len(sink_input_queues) == 0 and len(source_output_queues) == 0:
            # Also exclude sink input queues and source output queues by name pattern
            queue_resources_to_exclude = df.loc[
                df["Resource"].str.contains("Sink.*input.*queue|source.*output.*queue", case=False, na=False, regex=True),
                "Resource"
            ].unique()
            resources_to_exclude = set(source_sink_resources) | set(queue_resources_to_exclude)
        else:
            resources_to_exclude = set(source_sink_resources) | sink_input_queues | source_output_queues
        
        # Exclude all events for source, sink, and their associated queue resources
        if len(resources_to_exclude) > 0:
            df = df.loc[~df["Resource"].isin(resources_to_exclude)]
        
        positive_condition = (
            (df["State_type"] == "Process State")
            & (df["Activity"] == "start state")
            & (df["State Type"] != state.StateTypeEnum.setup)
            & (df["State Type"] != state.StateTypeEnum.breakdown)
            & (df["State Type"] != state.StateTypeEnum.charging)
        )
        negative_condition = (
            (df["State_type"] == "Process State")
            & (df["Activity"] == "end state")
            & (df["State Type"] != state.StateTypeEnum.setup)
            & (df["State Type"] != state.StateTypeEnum.breakdown)
            & (df["State Type"] != state.StateTypeEnum.charging)
        )

        df["Increment"] = 0
        df.loc[positive_condition, "Increment"] = 1
        df.loc[negative_condition, "Increment"] = -1

        # Insert Time=0.0 start events BEFORE calculating Used_Capacity
        df_resource_types = df[["Resource", "State Type"]].drop_duplicates().copy()
        resource_types_dict = pd.Series(
            df_resource_types["State Type"].values,
            index=df_resource_types["Resource"].values,
        ).to_dict()
        
        rows_to_insert = []
        for resource in df["Resource"].unique():
            if resource_types_dict[resource] in {
                state.StateTypeEnum.source,
                state.StateTypeEnum.sink,
            }:
                continue
            
            # Find any row for this resource to use as template
            resource_rows = df.loc[df["Resource"] == resource]
            if resource_rows.empty:
                continue
            
            example_row = resource_rows.head(1).copy()
            # Set properties for standby state at time 0
            example_row["Time"] = 0.0
            example_row["Increment"] = 0
            example_row["State_sorting_Index"] = 3  # Interface State, end state -> standby
            example_row["State_type"] = "Interface State"
            example_row["Activity"] = "end state"
            rows_to_insert.append(example_row)
        
        # Insert all start events at once
        if rows_to_insert:
            df_start_events = pd.concat(rows_to_insert, ignore_index=True)
            df = pd.concat([df_start_events, df]).reset_index(drop=True)
            # Sort by Resource and Time to ensure Time=0.0 events come first
            df = df.sort_values(by=["Resource", "Time"]).reset_index(drop=True)

        df["Used_Capacity"] = df.groupby(by="Resource")["Increment"].cumsum()

        # Use the global simulation end time (all resources should end at this time)
        
        # Insert end events at simulation end time for each resource
        # This ensures all resources have the same resource_time (0 to simulation_end_time)
        df_resource_types = df[["Resource", "State Type"]].drop_duplicates().copy()
        resource_types_dict = pd.Series(
            df_resource_types["State Type"].values,
            index=df_resource_types["Resource"].values,
        ).to_dict()
        
        end_rows_to_insert = []
        for resource in df["Resource"].unique():
            if resource_types_dict[resource] in {
                state.StateTypeEnum.source,
                state.StateTypeEnum.sink,
            }:
                continue
            
            resource_df = df[df["Resource"] == resource]
            if resource_df.empty:
                continue
            
            # Check if there's already an event at simulation_end_time
            events_at_end = resource_df[resource_df["Time"] == simulation_end_time]
            
            # Only insert if there's no event at simulation_end_time
            if len(events_at_end) == 0:
                # Use the last event as template to maintain the status of the last event
                example_row = resource_df.iloc[-1:].copy()
                
                # Set properties for end event at simulation end time
                # Maintain the state of the last event (don't force to standby)
                example_row["Time"] = simulation_end_time
                example_row["Increment"] = 0  # No change in capacity at end
                # Keep the same State_sorting_Index, State_type, Activity, and Used_Capacity
                # from the last event to maintain the resource's status
                end_rows_to_insert.append(example_row)
        
        # Insert all end events
        if end_rows_to_insert:
            df_end_events = pd.concat(end_rows_to_insert, ignore_index=True)
            df = pd.concat([df, df_end_events]).reset_index(drop=True)
            # Sort by Resource and Time to ensure proper order
            df = df.sort_values(by=["Resource", "Time"]).reset_index(drop=True)
            # Recalculate Used_Capacity after inserting end events
            df["Used_Capacity"] = df.groupby(by="Resource")["Increment"].cumsum()

        df["next_Time"] = df.groupby("Resource")["Time"].shift(-1)
        # For the last event of each resource, next_Time should equal its own Time
        # Fill NaN with the resource's own Time (since we inserted end events at simulation_end_time)
        df["next_Time"] = df["next_Time"].fillna(df["Time"])
        
        # For breakdown start events, use the breakdown end event time instead of next chronological event
        # This ensures breakdown downtime is calculated correctly even when there are other events at the same time
        breakdown_start_mask = (
            (df["State Type"] == state.StateTypeEnum.breakdown) 
            & (df["Activity"] == "start state")
        )
        if breakdown_start_mask.any():
            # Store original next_Time for comparison
            original_next_time = df["next_Time"].copy()
            
            # First, try to use Expected End Time if available
            if "Expected End Time" in df.columns:
                expected_end_times = df.loc[breakdown_start_mask, "Expected End Time"]
                valid_expected = expected_end_times.notna() & (expected_end_times > df.loc[breakdown_start_mask, "Time"])
                if valid_expected.any():
                    df.loc[valid_expected.index, "next_Time"] = expected_end_times[valid_expected]
            
            # For any remaining breakdown starts without valid Expected End Time, find the corresponding end event
            # Check which breakdown starts still have the original next_Time (meaning Expected End Time wasn't used)
            remaining_breakdown_starts = df[breakdown_start_mask].copy()
            if len(remaining_breakdown_starts) > 0:
                # Find breakdown starts that still need matching (those where next_Time wasn't updated)
                needs_matching = remaining_breakdown_starts[
                    df.loc[remaining_breakdown_starts.index, "next_Time"] == original_next_time[remaining_breakdown_starts.index]
                ]
                
                if len(needs_matching) > 0:
                    breakdown_ends = df[
                        (df["State Type"] == state.StateTypeEnum.breakdown) 
                        & (df["Activity"] == "end state")
                    ].copy()
                    
                    # Vectorized matching: Match breakdown start and end events by Resource and State
                    if len(breakdown_ends) > 0:
                        # Prepare start events for merging
                        starts = needs_matching[["Resource", "State", "Time"]].copy()
                        starts.index = needs_matching.index
                        starts = starts.reset_index()  # Reset to have a clean index for merge
                        
                        # Prepare end events for merging
                        ends = breakdown_ends[["Resource", "State", "Time"]].copy()
                        ends = ends.rename(columns={"Time": "end_Time"})
                        
                        # Merge to find all matching end events (where end_Time >= start Time)
                        merged = starts.merge(
                            ends,
                            on=["Resource", "State"],
                            how="left"
                        )
                        # Filter to only end events that occur after or at the start time
                        merged = merged[merged["end_Time"] >= merged["Time"]]
                        
                        # For each start event, find the minimum matching end time
                        if len(merged) > 0:
                            min_end_times = merged.groupby("index")["end_Time"].min()
                            # Update next_Time for rows that have a matching end event
                            df.loc[min_end_times.index, "next_Time"] = min_end_times.values
        
        # For non-scheduled start events, use the non-scheduled end event time instead of next chronological event
        # This ensures non-scheduled downtime is calculated correctly even when there are other events at the same time
        non_scheduled_start_mask = (
            (df["State Type"] == state.StateTypeEnum.non_scheduled) 
            & (df["Activity"] == "start state")
        )
        if non_scheduled_start_mask.any():
            # Store original next_Time for comparison
            original_next_time = df["next_Time"].copy()
            
            # First, try to use Expected End Time if available
            if "Expected End Time" in df.columns:
                expected_end_times = df.loc[non_scheduled_start_mask, "Expected End Time"]
                valid_expected = expected_end_times.notna() & (expected_end_times > df.loc[non_scheduled_start_mask, "Time"])
                if valid_expected.any():
                    df.loc[valid_expected.index, "next_Time"] = expected_end_times[valid_expected]
            
            # For any remaining non-scheduled starts without valid Expected End Time, find the corresponding end event
            # Check which non-scheduled starts still have the original next_Time (meaning Expected End Time wasn't used)
            remaining_non_scheduled_starts = df[non_scheduled_start_mask].copy()
            if len(remaining_non_scheduled_starts) > 0:
                # Find non-scheduled starts that still need matching (those where next_Time wasn't updated)
                needs_matching = remaining_non_scheduled_starts[
                    df.loc[remaining_non_scheduled_starts.index, "next_Time"] == original_next_time[remaining_non_scheduled_starts.index]
                ]
                
                if len(needs_matching) > 0:
                    non_scheduled_ends = df[
                        (df["State Type"] == state.StateTypeEnum.non_scheduled) 
                        & (df["Activity"] == "end state")
                    ].copy()
                    
                    # Vectorized matching: Match non-scheduled start and end events by Resource and State
                    if len(non_scheduled_ends) > 0:
                        # Prepare start events for merging
                        starts = needs_matching[["Resource", "State", "Time"]].copy()
                        starts.index = needs_matching.index
                        starts = starts.reset_index()  # Reset to have a clean index for merge
                        
                        # Prepare end events for merging
                        ends = non_scheduled_ends[["Resource", "State", "Time"]].copy()
                        ends = ends.rename(columns={"Time": "end_Time"})
                        
                        # Merge to find all matching end events (where end_Time >= start Time)
                        merged = starts.merge(
                            ends,
                            on=["Resource", "State"],
                            how="left"
                        )
                        # Filter to only end events that occur after or at the start time
                        merged = merged[merged["end_Time"] >= merged["Time"]]
                        
                        # For each start event, find the minimum matching end time
                        if len(merged) > 0:
                            min_end_times = merged.groupby("index")["end_Time"].min()
                            # Update next_Time for rows that have a matching end event
                            df.loc[min_end_times.index, "next_Time"] = min_end_times.values
        
        # For production/transport/setup states that are interrupted, match start state to start interrupt
        # This ensures the time_increment stops at the interruption, not at the end of the state
        # Only match if there's actually a start interrupt event (not for resumed states after interruption)
        for state_type in [state.StateTypeEnum.production, state.StateTypeEnum.transport, state.StateTypeEnum.setup]:
            interrupted_start_mask = (
                (df["State Type"] == state_type)
                & (df["Activity"] == "start state")
            )
            if interrupted_start_mask.any():
                # Vectorized matching: Find corresponding start interrupt events for these states
                interrupted_starts = df[interrupted_start_mask].copy()
                
                # Get all start interrupt events for this state type
                start_interrupts = df[
                    (df["State Type"] == state_type)
                    & (df["Activity"] == "start interrupt")
                ].copy()
                
                # Get all end interrupt events for this state type
                end_interrupts = df[
                    (df["State Type"] == state_type)
                    & (df["Activity"] == "end interrupt")
                ].copy()
                
                if len(start_interrupts) > 0:
                    # Prepare start events for merging
                    starts = interrupted_starts[["Resource", "State", "Time", "next_Time"]].copy()
                    starts.index = interrupted_starts.index
                    starts = starts.reset_index()  # Reset to have a clean index for merge
                    
                    # Prepare start interrupt events for merging
                    interrupts = start_interrupts[["Resource", "State", "Time"]].copy()
                    interrupts = interrupts.rename(columns={"Time": "interrupt_Time"})
                    
                    # Merge to find all matching start interrupt events (where interrupt_Time > start Time)
                    merged = starts.merge(
                        interrupts,
                        on=["Resource", "State"],
                        how="left"
                    )
                    merged = merged[merged["interrupt_Time"] > merged["Time"]]
                    
                    # For each start event, find the earliest matching interrupt time
                    if len(merged) > 0:
                        min_interrupt_times = merged.groupby("index")["interrupt_Time"].min()
                        
                        # Vectorized check for end interrupts between start and interrupt
                        if len(end_interrupts) > 0:
                            end_ints = end_interrupts[["Resource", "State", "Time"]].copy()
                            end_ints = end_ints.rename(columns={"Time": "end_int_Time"})
                            
                            # Prepare starts with their interrupt times for merging
                            # min_interrupt_times.index contains the original indices from interrupted_starts
                            # Map back to the original starts dataframe using the "index" column
                            starts_with_interrupts = starts[starts["index"].isin(min_interrupt_times.index)].copy()
                            if len(starts_with_interrupts) > 0:
                                # Map interrupt times back using the index column
                                starts_with_interrupts["interrupt_Time"] = starts_with_interrupts["index"].map(min_interrupt_times)
                                
                                # Merge with end interrupts to find any that fall between start and interrupt
                                end_int_check = starts_with_interrupts.merge(
                                    end_ints,
                                    on=["Resource", "State"],
                                    how="left"
                                )
                                # Filter to only end interrupts between start and interrupt
                                end_int_between = end_int_check[
                                    (end_int_check["end_int_Time"] > end_int_check["Time"])
                                    & (end_int_check["end_int_Time"] < end_int_check["interrupt_Time"])
                                ]
                                
                                # Find which start events have an end interrupt between start and interrupt
                                indices_with_end_int = end_int_between["index"].unique()
                                
                                # Filter out indices that have end interrupts between
                                valid_indices = min_interrupt_times.index.difference(indices_with_end_int)
                                
                                # Update next_Time for valid indices where interrupt is before next_Time
                                if len(valid_indices) > 0:
                                    # Get the original next_Time values for these indices
                                    original_next_times = df.loc[valid_indices, "next_Time"]
                                    valid_mask = min_interrupt_times.loc[valid_indices] < original_next_times
                                    update_indices = valid_indices[valid_mask]
                                    if len(update_indices) > 0:
                                        df.loc[update_indices, "next_Time"] = min_interrupt_times.loc[update_indices].values
                        else:
                            # No end interrupts exist, so just check if interrupt is before next_Time
                            # min_interrupt_times.index contains the original indices from interrupted_starts
                            if len(min_interrupt_times) > 0:
                                original_next_times = df.loc[min_interrupt_times.index, "next_Time"]
                                valid_mask = min_interrupt_times < original_next_times
                                update_indices = min_interrupt_times.index[valid_mask]
                                if len(update_indices) > 0:
                                    df.loc[update_indices, "next_Time"] = min_interrupt_times.loc[update_indices].values
        
        df["time_increment"] = df["next_Time"] - df["Time"]
        
        # Set time_increment to 0 for interrupt events - they are just markers, not actual time periods
        # Interrupt events should not contribute to time calculations
        interrupt_mask = (
            (df["State_sorting_Index"] == 4)  # end interrupt
            | (df["State_sorting_Index"] == 7)  # start interrupt
        )
        df.loc[interrupt_mask, "time_increment"] = 0

        # Initialize Time_type column
        df["Time_type"] = "na"

        STANDBY_CONDITION = (
            (df["State_sorting_Index"] == 5) & (df["Used_Capacity"] == 0)
        ) | (
            (df["State_sorting_Index"] == 3) 
            & (df["State Type"] != state.StateTypeEnum.breakdown)
            & (df["State Type"] != state.StateTypeEnum.setup)
            & (df["State Type"] != state.StateTypeEnum.charging)
            & (df["State Type"] != state.StateTypeEnum.non_scheduled)
        )
        # Exclude interrupt events from PRODUCTIVE_CONDITION - they are just markers, not productive time
        PRODUCTIVE_CONDITION = (
            (
                (df["State_sorting_Index"] == 6)  # start state
                | ((df["State_sorting_Index"] == 5) & (df["Used_Capacity"] != 0))  # end state with capacity
            )
            & (df["State Type"] != state.StateTypeEnum.dependency)
            & (df["State_sorting_Index"] != 4)  # exclude end interrupt
            & (df["State_sorting_Index"] != 7)  # exclude start interrupt
        )
        DEPENDENCY_CONDITION = (
            (df["State Type"] == state.StateTypeEnum.dependency)
        )
        DOWN_CONDITION = (
            (df["State_sorting_Index"] == 7) | (df["State_sorting_Index"] == 8)
        ) & (df["State Type"] == state.StateTypeEnum.breakdown)
        SETUP_CONDITION = ((df["State_sorting_Index"] == 8)) & (
            df["State Type"] == state.StateTypeEnum.setup
        )
        CHARGING_CONDITION = ((df["State_sorting_Index"] == 8)) & (
            df["State Type"] == state.StateTypeEnum.charging
        )
        NON_SCHEDULED_CONDITION = (
            (df["State_sorting_Index"] == 3) | (df["State_sorting_Index"] == 7) | (df["State_sorting_Index"] == 8)
        ) & (df["State Type"] == state.StateTypeEnum.non_scheduled)

        # First, exclude interrupt events from time calculations - they are just markers
        # Interrupt events should not be classified as any time type and should have 0 time_increment
        interrupt_events_mask = (
            (df["State_sorting_Index"] == 4)  # end interrupt
            | (df["State_sorting_Index"] == 7)  # start interrupt
        )
        df.loc[interrupt_events_mask, "Time_type"] = "na"  # Keep as "na" so they're excluded
        
        # Apply conditions in order of specificity (most specific first)
        # DEPENDENCY is most specific (requires State_sorting_Index == 6 AND State Type == dependency)
        df.loc[DEPENDENCY_CONDITION, "Time_type"] = "DP"
        # Then apply other specific conditions
        # Apply NON_SCHEDULED before DOWN_CONDITION to ensure it's not overwritten
        df.loc[NON_SCHEDULED_CONDITION, "Time_type"] = "NS"  # Non Scheduled
        df.loc[DOWN_CONDITION, "Time_type"] = "UD"
        df.loc[SETUP_CONDITION, "Time_type"] = "ST"
        df.loc[CHARGING_CONDITION, "Time_type"] = "CR"
        # Then apply general conditions
        df.loc[STANDBY_CONDITION, "Time_type"] = "SB"
        df.loc[PRODUCTIVE_CONDITION, "Time_type"] = "PR"
        
        # Fallback: if any events still don't have a Time_type, assign based on Used_Capacity
        # Events with Used_Capacity != 0 should be PR, others should be SB
        # But exclude interrupt events from this fallback
        unassigned = (df["Time_type"] == "na") & ~interrupt_events_mask
        df.loc[unassigned & (df["Used_Capacity"] != 0), "Time_type"] = "PR"
        df.loc[unassigned & (df["Used_Capacity"] == 0), "Time_type"] = "SB"

        # Add system resource states by aggregating subresource states
        system_resource_mapping = self._get_system_resource_mapping()
        if system_resource_mapping:
            # Use df_prepared to get raw productive process events, not the processed df_resource_states
            df_prepared_for_system = self.data_prep.df_prepared.copy()
            # Exclude loading/unloading and source/sink events for system resource calculation
            df_prepared_for_system = df_prepared_for_system.loc[
                (df_prepared_for_system["State Type"] != state.StateTypeEnum.loading)
                & (df_prepared_for_system["State Type"] != state.StateTypeEnum.unloading)
            ]
            sink_input_queues, source_output_queues = self._get_sink_source_queue_names()
            source_sink_resources = df_prepared_for_system.loc[
                (df_prepared_for_system["State Type"] == state.StateTypeEnum.source)
                | (df_prepared_for_system["State Type"] == state.StateTypeEnum.sink),
                "Resource"
            ].unique()
            resources_to_exclude = set(source_sink_resources) | sink_input_queues | source_output_queues
            if len(resources_to_exclude) > 0:
                df_prepared_for_system = df_prepared_for_system.loc[~df_prepared_for_system["Resource"].isin(resources_to_exclude)]
            
            # Ensure State_type column exists (it should from df_prepared, but double-check)
            if "State_type" not in df_prepared_for_system.columns:
                df_prepared_for_system.loc[
                    get_conditions_for_interface_state(df_prepared_for_system),
                    "State_type",
                ] = "Interface State"
                df_prepared_for_system.loc[
                    get_conditions_for_process_state(df_prepared_for_system),
                    "State_type",
                ] = "Process State"
            
            df_system_resources = self._calculate_system_resource_states(df_prepared_for_system, system_resource_mapping, simulation_end_time)
            if len(df_system_resources) > 0:
                df = pd.concat([df, df_system_resources], ignore_index=True)
                df = df.sort_values(by=["Resource", "Time"]).reset_index(drop=True)

        return df
    
    def _calculate_system_resource_states(self, df_subresources: pd.DataFrame, system_resource_mapping: dict, simulation_end_time: float) -> pd.DataFrame:
        """
        Calculate resource states for system resources based on running processes in subresources.
        
        Each started productive process increases the counter by 1, each ended decreases by 1.
        System resource is productive if counter > 0, otherwise standby.
        
        Args:
            df_subresources: DataFrame with subresource states
            system_resource_mapping: Dict mapping system resource ID to list of subresource IDs
            simulation_end_time: End time of simulation
            
        Returns:
            DataFrame with system resource states
        """
        system_resource_dfs = []
        
        for system_resource_id, subresource_ids in system_resource_mapping.items():
            # Filter to only include subresources of this system resource
            subresource_df = df_subresources[df_subresources["Resource"].isin(subresource_ids)].copy()
            
            if len(subresource_df) == 0:
                continue
            
            # Get a template row to copy all necessary columns
            system_template = subresource_df.iloc[0].copy()
            
            # Get only productive process start/end events from subresources
            # These are the events that change the running process count
            # Count only Production and Transport states (exclude dependency, setup, breakdown, charging)
            productive_start = (
                (subresource_df["State_type"] == "Process State")
                & (subresource_df["Activity"] == "start state")
                & (subresource_df["State Type"] != state.StateTypeEnum.setup)
                & (subresource_df["State Type"] != state.StateTypeEnum.breakdown)
                & (subresource_df["State Type"] != state.StateTypeEnum.charging)
                & (subresource_df["State Type"] != state.StateTypeEnum.dependency)
            )
            productive_end = (
                (subresource_df["State_type"] == "Process State")
                & (subresource_df["Activity"] == "end state")
                & (subresource_df["State Type"] != state.StateTypeEnum.setup)
                & (subresource_df["State Type"] != state.StateTypeEnum.breakdown)
                & (subresource_df["State Type"] != state.StateTypeEnum.charging)
                & (subresource_df["State Type"] != state.StateTypeEnum.dependency)
            )
            
            # Create events for system resource based on subresource productive process events
            system_events = []
            
            # Add start events (+1 increment)
            start_events = subresource_df[productive_start].copy()
            if len(start_events) > 0:
                # Copy all columns and update specific ones
                start_events["Increment"] = 1
                start_events["Resource"] = system_resource_id
                system_events.append(start_events)
            
            # Add end events (-1 increment)
            end_events = subresource_df[productive_end].copy()
            if len(end_events) > 0:
                # Copy all columns and update specific ones
                end_events["Increment"] = -1
                end_events["Resource"] = system_resource_id
                system_events.append(end_events)
            
            # Combine all events for this system resource
            if system_events:
                df_system = pd.concat(system_events, ignore_index=True)
                # Sort by time, then by increment (start events before end events at same time)
                # This ensures we process +1 before -1 when events happen simultaneously
                df_system = df_system.sort_values(by=["Time", "Increment"], ascending=[True, False]).reset_index(drop=True)
            else:
                # No productive events, create empty dataframe with correct structure
                df_system = pd.DataFrame([system_template])
            
            # Add initial event at time 0 (standby, increment = 0)
            initial_row = system_template.copy()
            initial_row["Time"] = 0.0
            initial_row["Increment"] = 0
            initial_row["State_sorting_Index"] = 3  # Interface State, end state -> standby
            initial_row["State_type"] = "Interface State"
            initial_row["Resource"] = system_resource_id
            initial_row["Activity"] = "end state"
            
            # Check if we already have a time 0 event
            if len(df_system) == 0 or df_system["Time"].min() > 0.0:
                # Prepend initial event
                df_system = pd.concat([pd.DataFrame([initial_row]), df_system], ignore_index=True)
            else:
                # Update existing time 0 event(s) - there might be multiple
                time_0_mask = df_system["Time"] == 0.0
                if time_0_mask.any():
                    # Set first time 0 event to initial state, remove others
                    first_idx = df_system[time_0_mask].index[0]
                    df_system.loc[first_idx, "Increment"] = 0
                    df_system.loc[first_idx, "State_sorting_Index"] = 3
                    df_system.loc[first_idx, "State_type"] = "Interface State"
                    df_system.loc[first_idx, "Activity"] = "end state"
                    # Remove other time 0 events
                    other_time_0 = df_system[time_0_mask].index[1:]
                    if len(other_time_0) > 0:
                        df_system = df_system.drop(other_time_0).reset_index(drop=True)
            
            # Sort by time, then by increment after all modifications
            df_system = df_system.sort_values(by=["Time", "Increment"], ascending=[True, False]).reset_index(drop=True)
            
            # Calculate cumulative Used_Capacity (running process count)
            # Start from 0, then apply increments
            df_system["Used_Capacity"] = df_system["Increment"].cumsum()
            
            # If we have more ends than starts (net_imbalance > 0), processes were already running at time 0
            # Adjust the capacity: shift up by the maximum negative value (if any)
            min_capacity = df_system["Used_Capacity"].min()
            if min_capacity < 0:
                # Processes were already running at start - shift all values up
                adjustment = -min_capacity
                df_system["Used_Capacity"] = df_system["Used_Capacity"] + adjustment
                # Also adjust the initial time 0 event
                time_0_mask = df_system["Time"] == 0.0
                if time_0_mask.any():
                    df_system.loc[time_0_mask, "Used_Capacity"] = adjustment
            
            # Add end event at simulation_end_time if needed
            last_time = df_system["Time"].max()
            if last_time < simulation_end_time:
                end_row = df_system.iloc[-1].copy()
                end_row["Time"] = simulation_end_time
                end_row["Increment"] = 0
                # Keep the state from the last event
                df_system = pd.concat([df_system, pd.DataFrame([end_row])], ignore_index=True)
            
            # Sort again after adding end event
            df_system = df_system.sort_values(by=["Time", "Increment"], ascending=[True, False]).reset_index(drop=True)
            
            # Recalculate Used_Capacity after adding end event
            # If we had an adjustment, we need to maintain it
            if min_capacity < 0:
                # Recalculate with adjustment
                df_system["Used_Capacity"] = df_system["Increment"].cumsum() + adjustment
                # Ensure time 0 has the adjusted value
                time_0_mask = df_system["Time"] == 0.0
                if time_0_mask.any():
                    df_system.loc[time_0_mask, "Used_Capacity"] = adjustment
            else:
                df_system["Used_Capacity"] = df_system["Increment"].cumsum()
            
            # Final safety check: ensure never negative
            df_system["Used_Capacity"] = df_system["Used_Capacity"].clip(lower=0)
            
            # Calculate next_Time
            df_system["next_Time"] = df_system["Time"].shift(-1)
            df_system["next_Time"] = df_system["next_Time"].fillna(df_system["Time"])
            df_system["time_increment"] = df_system["next_Time"] - df_system["Time"]
            
            # Determine Time_type: PR if Used_Capacity > 0, SB otherwise
            df_system["Time_type"] = "SB"
            df_system.loc[df_system["Used_Capacity"] > 0, "Time_type"] = "PR"
            
            # Set other required columns
            df_system["State Type"] = "Production"  # System resources are production resources
            df_system["Activity"] = "end state"  # Default activity
            df_system.loc[df_system["Increment"] == 1, "Activity"] = "start state"
            
            system_resource_dfs.append(df_system)
        
        if system_resource_dfs:
            return pd.concat(system_resource_dfs, ignore_index=True)
        else:
            return pd.DataFrame()

    @cached_property
    def df_aggregated_resource_states(self) -> pd.DataFrame:
        """
        Returns a data frame with the total time spent in each state of each resource.

        There are 4 different states a resource can spend its time:
            -SB: A resource is in standby state, could process but no product is available
            -PR: A resource is in productive state and performs a process
            -UD: A resource is in unscheduled downtime state due to a breakdown
            -ST: A resource is in setup state
            -CR: A resource is in charging state

        Returns:
            pd.DataFrame: Data frame with the total time spent in each state of each resource.
        """
        df = self.df_resource_states.copy()
        df = df.loc[df["Time_type"] != "na"]

        if self.context.warm_up_cutoff:
            df = df.loc[df["Time"] >= self.throughput_analytics.warm_up_cutoff_time]

        # Fix overlapping time periods with proper state hierarchy:
        # 1. NS periods are from NS start to NS end events
        # 2. UD (breakdown) during NS: UD takes precedence, NS time excluded during UD
        # 3. PR/SB/ST during NS: excluded from their time_increment
        # 4. UD events are always counted (they take precedence over NS)
        
        # Get raw events to identify NS and UD periods properly
        df_raw = self.df_resource_states.copy()
        if self.context.warm_up_cutoff:
            df_raw = df_raw.loc[df_raw["Time"] >= self.throughput_analytics.warm_up_cutoff_time]
        
        # Identify NS periods per resource (from NS start to NS end events)
        ns_periods_by_resource = {}
        ud_periods_by_resource = {}
        
        for resource in df["Resource"].unique():
            resource_events = df_raw[df_raw["Resource"] == resource].copy()
            
            # Identify NS periods: find NS start and end events
            ns_starts = resource_events[
                (resource_events["State Type"] == state.StateTypeEnum.non_scheduled) &
                (resource_events["Activity"] == "start state")
            ].copy()
            ns_ends = resource_events[
                (resource_events["State Type"] == state.StateTypeEnum.non_scheduled) &
                (resource_events["Activity"] == "end state")
            ].copy()
            
            # Match NS start and end events to create periods
            ns_periods = []
            for _, start_row in ns_starts.iterrows():
                start_time = start_row["Time"]
                # Find corresponding end event (same State ID, after start)
                state_id = start_row["State"]
                matching_ends = ns_ends[
                    (ns_ends["State"] == state_id) &
                    (ns_ends["Time"] >= start_time)
                ]
                if len(matching_ends) > 0:
                    end_time = matching_ends["Time"].min()
                    if end_time > start_time:
                        ns_periods.append((start_time, end_time))
            
            # Merge overlapping NS periods
            if ns_periods:
                ns_periods.sort()
                merged_ns = []
                current_start, current_end = ns_periods[0]
                for start, end in ns_periods[1:]:
                    if start <= current_end:
                        current_end = max(current_end, end)
                    else:
                        merged_ns.append((current_start, current_end))
                        current_start, current_end = start, end
                merged_ns.append((current_start, current_end))
                ns_periods_by_resource[resource] = merged_ns
            else:
                ns_periods_by_resource[resource] = []
            
            # Identify UD periods: find breakdown start and end events
            ud_starts = resource_events[
                (resource_events["State Type"] == state.StateTypeEnum.breakdown) &
                (resource_events["Activity"] == "start state")
            ].copy()
            ud_ends = resource_events[
                (resource_events["State Type"] == state.StateTypeEnum.breakdown) &
                (resource_events["Activity"] == "end state")
            ].copy()
            
            # Match UD start and end events
            ud_periods = []
            for _, start_row in ud_starts.iterrows():
                start_time = start_row["Time"]
                state_id = start_row["State"]
                matching_ends = ud_ends[
                    (ud_ends["State"] == state_id) &
                    (ud_ends["Time"] >= start_time)
                ]
                if len(matching_ends) > 0:
                    end_time = matching_ends["Time"].min()
                    if end_time > start_time:
                        ud_periods.append((start_time, end_time))
            
            ud_periods_by_resource[resource] = ud_periods
        
        # Adjust NS time: subtract UD periods that occur during NS
        df_ns = df[df["Time_type"] == "NS"].copy()
        if len(df_ns) > 0:
            def adjust_ns_time(row):
                resource = row["Resource"]
                event_start = row["Time"]
                event_end = row["next_Time"]
                original_time = row["time_increment"]
                
                if event_end <= event_start:
                    return 0
                
                # Find which NS period this event belongs to
                ns_periods = ns_periods_by_resource.get(resource, [])
                ud_periods = ud_periods_by_resource.get(resource, [])
                
                # Check if this event overlaps with any NS period
                for ns_start, ns_end in ns_periods:
                    if event_start >= ns_start and event_end <= ns_end:
                        # This event is within an NS period
                        # Subtract any UD periods that overlap with this event's time
                        total_ud_overlap = 0
                        for ud_start, ud_end in ud_periods:
                            overlap_start = max(event_start, ud_start)
                            overlap_end = min(event_end, ud_end)
                            if overlap_start < overlap_end:
                                total_ud_overlap += overlap_end - overlap_start
                        return max(0, original_time - total_ud_overlap)
                
                return original_time
            
            df_ns["time_increment"] = df_ns.apply(adjust_ns_time, axis=1)
        
        # For PR/SB/ST events, exclude time that overlaps with NS periods
        df_non_ns_non_ud = df[~df["Time_type"].isin(["NS", "UD"])].copy()
        if len(df_non_ns_non_ud) > 0:
            def exclude_ns_overlap(row):
                resource = row["Resource"]
                event_start = row["Time"]
                event_end = row["next_Time"]
                original_time = row["time_increment"]
                
                if event_end <= event_start:
                    return 0
                
                ns_periods = ns_periods_by_resource.get(resource, [])
                if not ns_periods:
                    return original_time
                
                # Calculate total overlap with NS periods
                total_overlap = 0
                for ns_start, ns_end in ns_periods:
                    overlap_start = max(event_start, ns_start)
                    overlap_end = min(event_end, ns_end)
                    if overlap_start < overlap_end:
                        total_overlap += overlap_end - overlap_start
                
                return max(0, original_time - total_overlap)
            
            df_non_ns_non_ud["time_increment"] = df_non_ns_non_ud.apply(exclude_ns_overlap, axis=1)
        
        # Combine all events back together
        df_ud = df[df["Time_type"] == "UD"].copy()  # UD events are unchanged
        df = pd.concat([df_ns, df_ud, df_non_ns_non_ud], ignore_index=True)
        
        df_time_per_state = df.groupby(["Resource", "Time_type"])[
            "time_increment"
        ].sum()
        df_time_per_state = df_time_per_state.to_frame().reset_index()

        # Calculate resource_time as the total time span for each resource
        # This should be from 0 to simulation_end_time for all resources
        # Use time_range if available, otherwise use max Time (which should be simulation_end_time
        # since end events are inserted at simulation_end_time in df_resource_states)
        if self.context.time_range is not None:
            # Use the provided time_range for all resources
            resources = df["Resource"].unique()
            df_resource_time = pd.DataFrame({
                "Resource": resources,
                "resource_time": [self.context.time_range] * len(resources)
            })
        else:
            # Use the actual time range (max Time) for each resource
            # Since end events are inserted at simulation_end_time, max Time should be correct
            df_resource_time = df.groupby(by="Resource")["Time"].max().reset_index()
            df_resource_time.rename(columns={"Time": "resource_time"}, inplace=True)
        df_time_per_state = pd.merge(df_time_per_state, df_resource_time)
        
        # Calculate percentages: all states use resource_time (total time) as denominator
        # This ensures percentages represent the proportion of total time spent in each state
        df_time_per_state["percentage"] = (
            df_time_per_state["time_increment"] / df_time_per_state["resource_time"]
        ) * 100
        
        # Handle division by zero (shouldn't happen, but safety check)
        df_time_per_state.loc[df_time_per_state["resource_time"] == 0, "percentage"] = 0

        return df_time_per_state
    
    def get_resource_states_by_interval(self, interval_minutes: float) -> pd.DataFrame:
        """
        Returns resource states aggregated by time intervals.
        
        Calculates resource states on the complete event log, then aggregates
        by time intervals (e.g., 10 minutes, 1000 minutes).
        
        Args:
            interval_minutes: Time interval in minutes for aggregation.
            
        Returns:
            pd.DataFrame: Data frame with resource states aggregated by intervals.
                         Columns: Resource, Interval_start, Interval_end, Time_type,
                         time_increment, interval_time, percentage
        """
        df = self.df_resource_states.copy()
        df = df.loc[df["Time_type"] != "na"]
        
        if self.context.warm_up_cutoff:
            df = df.loc[df["Time"] >= self.throughput_analytics.warm_up_cutoff_time]
        
        simulation_end_time = self._get_simulation_end_time()
        
        # Determine the start time for intervals
        # If warm_up_cutoff is used, start from warm_up_cutoff_time, otherwise from 0 or min time
        if self.context.warm_up_cutoff:
            min_time = self.throughput_analytics.warm_up_cutoff_time
        else:
            min_time = df["Time"].min() if len(df) > 0 else 0.0
        
        # Create intervals starting from min_time
        intervals = []
        current_start = min_time
        while current_start < simulation_end_time:
            interval_end = min(current_start + interval_minutes, simulation_end_time)
            intervals.append((current_start, interval_end))
            current_start = interval_end
        
        # For each resource and interval, aggregate time_increment by Time_type
        results = []
        
        for resource in df["Resource"].unique():
            df_resource = df[df["Resource"] == resource].copy()
            
            for interval_start, interval_end in intervals:
                # Filter events that overlap with this interval
                # An event overlaps if: event_start < interval_end AND event_end > interval_start
                overlapping = df_resource[
                    (df_resource["Time"] < interval_end) &
                    (df_resource["next_Time"] > interval_start)
                ].copy()
                
                if len(overlapping) == 0:
                    continue
                
                # Calculate the time spent in each state during this interval
                # For events that overlap with the interval, we clip to the interval boundaries
                # and proportionally scale the time_increment based on the overlap
                def calculate_interval_time(row):
                    event_start = row["Time"]
                    event_end = row["next_Time"]
                    
                    # Calculate overlap with interval - clip event to interval boundaries
                    overlap_start = max(event_start, interval_start)
                    overlap_end = min(event_end, interval_end)
                    
                    if overlap_end <= overlap_start:
                        return 0.0
                    
                    # Calculate the proportion of the event that falls within this interval
                    event_duration = event_end - event_start
                    overlap_duration = overlap_end - overlap_start
                    
                    if event_duration <= 0:
                        return 0.0
                    
                    # Scale time_increment proportionally to the overlap
                    # time_increment represents the actual time in this state during the event
                    # We scale it by the proportion of the event that falls in this interval
                    proportion = overlap_duration / event_duration
                    scaled_time = row["time_increment"] * proportion
                    
                    # However, we also need to ensure we don't exceed the overlap duration
                    # This handles cases where time_increment might be adjusted (e.g., NS minus UD)
                    return min(scaled_time, overlap_duration)
                
                overlapping["interval_time"] = overlapping.apply(calculate_interval_time, axis=1)
                
                # Aggregate by Time_type
                interval_aggregated = overlapping.groupby("Time_type")["interval_time"].sum().reset_index()
                interval_aggregated.columns = ["Time_type", "time_increment"]
                
                # Add metadata
                interval_aggregated["Resource"] = resource
                interval_aggregated["Interval_start"] = interval_start
                interval_aggregated["Interval_end"] = interval_end
                interval_time_total = interval_end - interval_start
                interval_aggregated["interval_time"] = interval_time_total
                
                # Calculate percentage and ensure it doesn't exceed 100%
                # Normalize if the sum exceeds the interval time
                total_time = interval_aggregated["time_increment"].sum()
                if total_time > interval_time_total:
                    # Normalize: scale down proportionally
                    scale_factor = interval_time_total / total_time
                    interval_aggregated["time_increment"] = interval_aggregated["time_increment"] * scale_factor
                
                interval_aggregated["percentage"] = (
                    interval_aggregated["time_increment"] / interval_time_total
                ) * 100
                
                # Clip percentages to 0-100% range as a safety measure
                interval_aggregated["percentage"] = interval_aggregated["percentage"].clip(0, 100)
                
                results.append(interval_aggregated)
        
        if results:
            df_result = pd.concat(results, ignore_index=True)
            # Reorder columns
            df_result = df_result[["Resource", "Interval_start", "Interval_end", "Time_type", 
                                  "time_increment", "interval_time", "percentage"]]
            return df_result
        else:
            return pd.DataFrame(columns=["Resource", "Interval_start", "Interval_end", "Time_type",
                                        "time_increment", "interval_time", "percentage"])
    
    def get_aggregated_resource_states_by_interval(self, interval_minutes: float) -> pd.DataFrame:
        """
        Returns aggregated resource states by time intervals.
        
        Similar to df_aggregated_resource_states but aggregated by intervals.
        
        Args:
            interval_minutes: Time interval in minutes for aggregation.
            
        Returns:
            pd.DataFrame: Data frame with aggregated resource states per interval.
                         Columns: Resource, Interval_start, Interval_end, Time_type,
                         time_increment, interval_time, percentage
        """
        return self.get_resource_states_by_interval(interval_minutes)