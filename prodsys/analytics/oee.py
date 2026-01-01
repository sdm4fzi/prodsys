"""
OEE analytics module.

This module handles Overall Equipment Effectiveness (OEE) calculations.
"""

from __future__ import annotations

from functools import cached_property

import pandas as pd
import numpy as np

from prodsys.simulation import state
from prodsys.analytics.base import AnalyticsContext
from prodsys.analytics.data_preparation import DataPreparation
from prodsys.analytics.throughput import ThroughputAnalytics
from prodsys.analytics.scrap import ScrapAnalytics
from prodsys.analytics.resource_states import ResourceStatesAnalytics

import logging

logger = logging.getLogger(__name__)


class OEEAnalytics:
    """
    Handles Overall Equipment Effectiveness (OEE) calculations.
    """
    
    def __init__(
        self,
        context: AnalyticsContext,
        data_prep: DataPreparation,
        throughput_analytics: ThroughputAnalytics,
        scrap_analytics: ScrapAnalytics,
        resource_states_analytics: ResourceStatesAnalytics,
    ):
        """
        Initialize OEE analytics.
        
        Args:
            context: Analytics context containing raw data and configuration.
            data_prep: Data preparation instance.
            throughput_analytics: Throughput analytics instance.
            scrap_analytics: Scrap analytics instance.
            resource_states_analytics: Resource states analytics instance.
        """
        self.context = context
        self.data_prep = data_prep
        self.throughput_analytics = throughput_analytics
        self.scrap_analytics = scrap_analytics
        self.resource_states_analytics = resource_states_analytics
    
    def _get_total_simulation_time(self) -> float:
        """Get total simulation time."""
        if self.context.time_range is not None:
            return self.context.time_range
        return self.data_prep.df_prepared["Time"].max()
    
    @cached_property
    def df_oee_production_system(self) -> pd.DataFrame:
        """
        Calculate the Overall Equipment Effectiveness (OEE) of the production system.
        
        OEE = Availability × Performance × Quality
        
        Following formal OEE definitions (standard OEE/TPM view):
        - Availability = Operating Time / Planned Production Time
          Where Planned Production Time = Total Time - Non Scheduled Time (all time where production is expected)
          And Operating Time = PR (Productive) + DP (Dependency)
          Availability losses (UD, ST, SB, CR) are in Planned Production Time but reduce Operating Time
        
        - Performance = (Ideal Cycle Time × Total Units Produced) / Operating Time
          Operating Time includes PR (productive) and DP (dependency)
        
        - Quality = Good Units / Total Units Produced
        
        Returns:
            pd.DataFrame: A DataFrame containing the calculated OEE values for 
                         Availability, Performance, Quality, and OEE.
        """
        # For system-level OEE, calculate as weighted average of resource-level OEEs
        # This avoids double-counting parallel resource time
        df_oee_resources = self.df_oee_per_resource.copy()
        
        if len(df_oee_resources) == 0:
            logger.warning(
                "No resource-level OEE data available. System OEE will default to 100%."
            )
            availability = 1.0
            performance = 1.0
            quality = 1.0
        else:
            # Get resource states to calculate weights (planned production time per resource)
            df_resource_states = self.resource_states_analytics.df_aggregated_resource_states.copy()
            df_resource_states = df_resource_states.reset_index()
            
            # Calculate planned production time per resource for weighting
            resource_weights = {}
            for resource in df_resource_states["Resource"].unique():
                df_resource = df_resource_states[df_resource_states["Resource"] == resource]
                resource_time = df_resource["resource_time"].iloc[0]
                time_per_state = df_resource.set_index("Time_type")["time_increment"]
                non_scheduled_time = time_per_state.get("NS", 0)
                planned_production_time = resource_time - non_scheduled_time
                resource_weights[resource] = planned_production_time
            
            # Calculate total weight (sum of all planned production times)
            total_weight = sum(resource_weights.values())
            
            if total_weight > 0:
                # Calculate weighted average availability
                availability_sum = 0.0
                
                for _, row in df_oee_resources.iterrows():
                    resource = row["Resource"]
                    weight = resource_weights.get(resource, 0)
                    if weight > 0:
                        # Convert percentages back to ratios
                        availability_sum += (row["Availability"] / 100.0) * weight
                
                availability = availability_sum / total_weight
            else:
                # Fallback: simple average if no weights available
                availability = df_oee_resources["Availability"].mean() / 100.0
        
        # Performance: Actual Output / Expected Output (system-level calculation)
        # Expected output is based on source arrival time models, schedules, or order data
        if self.context.production_system_data is None:
            logger.warning(
                "production_system_data not available. Cannot calculate expected output. "
                "Performance will default to 100%."
            )
            performance = 1.0
        else:
            # Get simulation time range
            total_time = self._get_total_simulation_time()
            
            # Calculate expected output from sources
            from prodsys.factories.time_model_factory import TimeModelFactory
            
            time_model_factory = TimeModelFactory()
            time_model_factory.create_time_models(self.context.production_system_data)
            
            expected_output = 0.0
            
            # Check for order data or schedule first
            # Note: order_data might not be a direct attribute, check if it exists
            order_data = getattr(self.context.production_system_data, 'order_data', None)
            if order_data and len(order_data) > 0:
                # If order data exists, sum up the quantities from all orders
                from prodsys.models.order_data import OrderData
                expected_output = sum(
                    sum(product.quantity for product in order.ordered_products)
                    for order in order_data
                    if isinstance(order, OrderData)
                )
            elif hasattr(self.context.production_system_data, 'schedule') and self.context.production_system_data.schedule:
                # If schedule exists, count scheduled products within simulation time
                schedule_products = [
                    event for event in self.context.production_system_data.schedule
                    if hasattr(event, 'time') and event.time <= total_time
                ]
                expected_output = len(schedule_products)
            else:
                # Calculate expected output from source arrival time models
                for source_data in self.context.production_system_data.source_data:
                    try:
                        time_model = time_model_factory.get_time_model(source_data.time_model_id)
                        
                        # Check if it's a ScheduledTimeModel
                        from prodsys.simulation.time_model import ScheduledTimeModel
                        if isinstance(time_model, ScheduledTimeModel):
                            # For scheduled time models, count how many arrivals are expected
                            schedule = time_model.data.schedule
                            if time_model.data.absolute:
                                # Absolute schedule: count entries <= total_time
                                expected_output += len([t for t in schedule if t <= total_time])
                            else:
                                # Relative schedule: calculate cumulative times and count
                                cumulative_time = 0.0
                                count = 0
                                for interval in schedule:
                                    cumulative_time += interval
                                    if cumulative_time <= total_time:
                                        count += 1
                                    else:
                                        break
                                expected_output += count
                        else:
                            # For other time models, use expected interarrival time
                            expected_interarrival_time = time_model.get_expected_time()
                            
                            if expected_interarrival_time > 0:
                                # Expected output = Total Time / Expected Interarrival Time
                                source_expected_output = total_time / expected_interarrival_time
                                expected_output += source_expected_output
                    except (ValueError, TypeError, AttributeError) as e:
                        # Time model not found or doesn't support get_expected_time
                        logger.warning(
                            f"Could not get expected time for source {source_data.ID}: {e}. "
                            "Skipping this source for expected output calculation."
                        )
                        continue
            
            # Get actual output
            df_output = self.throughput_analytics.df_aggregated_output_and_throughput.copy()
            if len(df_output) > 0:
                actual_output = df_output["Output"].sum()
            else:
                actual_output = 0
            
            # Performance = Actual Output / Expected Output
            if expected_output > 0:
                performance = actual_output / expected_output
            else:
                if actual_output > 0:
                    # If we have actual output but no expected output, performance is undefined
                    # Default to 100% but log a warning
                    performance = 1.0
                    logger.warning(
                        "Could not calculate expected output. Performance will default to 100%."
                    )
                else:
                    performance = 1.0
        
        # Quality: Good Units / Total Units Produced (system-level calculation)
        df_output = self.throughput_analytics.df_aggregated_output_and_throughput.copy()
        if len(df_output) > 0:
            total_units_produced = df_output["Output"].sum()
        else:
            total_units_produced = 0
        
        if total_units_produced > 0:
            # Get scrap data to calculate good units
            df_scrap = self.scrap_analytics.df_scrap_per_product_type.copy()
            if len(df_scrap) > 0:
                # Calculate weighted average scrap rate based on output
                df_output_for_quality = self.throughput_analytics.df_aggregated_output.copy()
                if len(df_output_for_quality) > 0:
                    # Merge scrap data with output data
                    df_quality = pd.merge(
                        df_output_for_quality.reset_index(),
                        df_scrap[["Product_type", "Scrap_rate"]],
                        on="Product_type",
                        how="left"
                    )
                    df_quality["Scrap_rate"] = df_quality["Scrap_rate"].fillna(0)
                    
                    # Calculate total scrap units
                    total_scrap_units = (
                        (df_quality["Product"] * df_quality["Scrap_rate"] / 100).sum()
                    )
                    
                    # Good units = Total units - Scrap units
                    good_units = total_units_produced - total_scrap_units
                    quality = good_units / total_units_produced
                else:
                    # No output data - assume 100% quality
                    quality = 1.0
            else:
                # No scrap data - assume all units are good
                quality = 1.0
        else:
            # No units produced - assume 100% quality
            quality = 1.0
            logger.info(
                "No units produced. Quality will default to 100%."
            )
        
        # Calculate OEE
        oee = availability * performance * quality
        
        # Create DataFrame
        oee_df = pd.DataFrame(
            {
                "KPI": ["Availability", "Performance", "Quality", "OEE"],
                "Value": [
                    availability * 100,
                    performance * 100,
                    quality * 100,
                    oee * 100,
                ],
            }
        )
        oee_df["Value"] = oee_df["Value"].round(2)
        
        return oee_df

    @cached_property
    def df_oee_per_resource(self) -> pd.DataFrame:
        """
        Calculate OEE for each resource individually.
        
        OEE = Availability × Performance × Quality
        
        Following formal OEE definitions (standard OEE/TPM view):
        - Availability = Operating Time / Planned Production Time
          Where Planned Production Time = Resource Time - Non Scheduled Time (all time where production is expected)
          And Operating Time = PR (Productive) + DP (Dependency)
          Availability losses (UD, ST, SB, CR) are in Planned Production Time but reduce Operating Time
        
        - Performance = (Ideal Cycle Time × Total Units Produced) / Operating Time
          Operating Time includes PR (productive) and DP (dependency)
        
        - Quality = Good Units / Total Units Produced
        
        Returns:
            pd.DataFrame: DataFrame with OEE components per resource.
        """
        if self.context.production_system_data is None:
            logger.warning(
                "production_system_data not available. Cannot calculate resource-level OEE."
            )
            return pd.DataFrame(columns=["Resource", "Availability", "Performance", "Quality", "OEE"])
        
        # Get resource states
        df_resource_states = self.resource_states_analytics.df_aggregated_resource_states.copy()
        df_resource_states = df_resource_states.reset_index()
        
        # Get time model factory
        from prodsys.factories.time_model_factory import TimeModelFactory
        time_model_factory = TimeModelFactory()
        time_model_factory.create_time_models(self.context.production_system_data)
        
        # Get processes per resource
        resource_to_processes = {}
        for resource_data in self.context.production_system_data.resource_data:
            if hasattr(resource_data, 'process_ids'):
                resource_to_processes[resource_data.ID] = resource_data.process_ids
        
        # Identify transport resources
        from prodsys.models.production_system_data import get_transport_resources
        transport_resources = get_transport_resources(self.context.production_system_data)
        transport_resource_ids = {r.ID for r in transport_resources}
        
        # Calculate OEE per resource
        oee_results = []
        
        for resource in df_resource_states["Resource"].unique():
            df_resource = df_resource_states[df_resource_states["Resource"] == resource]
            
            # Get resource time
            resource_time = df_resource["resource_time"].iloc[0]
            
            # Calculate time per state (time_increment is already in absolute time)
            time_per_state = df_resource.set_index("Time_type")["time_increment"]
            
            # Get time components
            non_scheduled_time = time_per_state.get("NS", 0)
            setup_time = time_per_state.get("ST", 0)
            productive_time = time_per_state.get("PR", 0)
            dependency_time = time_per_state.get("DP", 0)
            
            # Availability: (PR + ST + DP) / (Total Time - Non-scheduled Time)
            # Scheduled Time = Total Time - Non-scheduled Time (NS)
            scheduled_time = resource_time - non_scheduled_time
            
            # Availability = (Productive + Setup + Dependency) / Scheduled Time
            # This measures how much of scheduled time was used for production-related activities
            # Excludes standby (SB) and breakdowns (UD) as availability losses
            if scheduled_time > 0:
                availability = (productive_time + setup_time + dependency_time) / scheduled_time
            else:
                availability = 0.0
            
            # Run Time = time actually producing (PR time) - this is used for performance calculation
            # Standby time is NOT included in run time
            run_time = productive_time
            
            # Performance calculation depends on resource type
            is_transport_resource = resource in transport_resource_ids
            
            if is_transport_resource:
                # For transport resources: Performance defaults to 100%
                # Transport performance is typically not measured the same way as production resources
                performance = 1.0
            else:
                # For production resources: Performance = (Ideal Cycle Time × Total Units Produced) / Operating Time
                # Get actual process end events for this resource (production only) to count process occurrences
                df_prepared = self.data_prep.df_prepared.copy()
                resource_process_ends = df_prepared[
                    (df_prepared["Resource"] == resource) &
                    (df_prepared["State Type"] == state.StateTypeEnum.production) &
                    (df_prepared["Activity"] == "end state")
                ]
                total_units_produced = len(resource_process_ends)
                
                # Get resource capacity
                resource_capacity = 1  # Default capacity
                process_capacities = {}  # Map process_id -> capacity
                for resource_data in self.context.production_system_data.resource_data:
                    if resource_data.ID == resource:
                        resource_capacity = resource_data.capacity if hasattr(resource_data, 'capacity') else 1
                        # Get process-specific capacities if available
                        if hasattr(resource_data, 'process_capacities') and resource_data.process_capacities:
                            for i, process_id in enumerate(resource_data.process_ids):
                                if i < len(resource_data.process_capacities):
                                    process_capacities[process_id] = resource_data.process_capacities[i]
                        break
                
                if total_units_produced > 0:
                    # Get actual process execution times from event log (start to end)
                    # This gives us the actual time spent on each process execution
                    resource_process_starts = df_prepared[
                        (df_prepared["Resource"] == resource) &
                        (df_prepared["State Type"] == state.StateTypeEnum.production) &
                        (df_prepared["Activity"] == "start state")
                    ].copy()
                    
                    # Match start and end events to get actual process execution times
                    actual_process_times = []
                    for _, end_row in resource_process_ends.iterrows():
                        process_id = end_row["State"]
                        end_time = end_row["Time"]
                        
                        # Find corresponding start event (same process, same resource, before end time)
                        matching_starts = resource_process_starts[
                            (resource_process_starts["State"] == process_id) &
                            (resource_process_starts["Time"] <= end_time)
                        ]
                        
                        if len(matching_starts) > 0:
                            # Use the most recent start event before this end event
                            start_time = matching_starts["Time"].max()
                            actual_time = end_time - start_time
                            if actual_time > 0:
                                actual_process_times.append((process_id, actual_time))
                    
                    # Calculate total ideal time and total actual time
                    total_ideal_time = 0.0
                    total_actual_time = 0.0
                    process_ideal_times = {}  # Cache ideal times per process
                    
                    # Get ideal cycle times for each process
                    for process_data in self.context.production_system_data.process_data:
                        if hasattr(process_data, 'time_model_id'):
                            try:
                                time_model = time_model_factory.get_time_model(process_data.time_model_id)
                                ideal_cycle_time = time_model.get_expected_time()
                                if ideal_cycle_time > 0:
                                    process_capacity = process_capacities.get(process_data.ID, resource_capacity)
                                    ideal_cycle_time_per_unit = ideal_cycle_time / process_capacity if process_capacity > 0 else ideal_cycle_time
                                    process_ideal_times[process_data.ID] = ideal_cycle_time_per_unit
                            except (ValueError, TypeError):
                                pass
                    
                    # Sum up ideal and actual times
                    for process_id, actual_time in actual_process_times:
                        total_actual_time += actual_time
                        if process_id in process_ideal_times:
                            total_ideal_time += process_ideal_times[process_id]
                    
                    # Performance = Total Ideal Time / Total Actual Time
                    # This compares the ideal time needed vs actual time spent
                    # Should be ~100% if the machine runs at ideal speed
                    if total_actual_time > 0 and total_ideal_time > 0:
                        performance = total_ideal_time / total_actual_time
                    elif run_time > 0 and total_ideal_time > 0:
                        # Fallback: use PR time if we can't get actual process times
                        performance = total_ideal_time / run_time
                    else:
                        performance = 0.0
                        logger.warning(
                            f"Could not calculate performance for resource {resource}. "
                            f"Total actual time: {total_actual_time}, Total ideal time: {total_ideal_time}, Run time: {run_time}"
                        )
                else:
                    if total_units_produced == 0:
                        performance = 0.0
                    else:
                        performance = 0.0
                        logger.warning(
                            f"No run time for resource {resource} with units produced. "
                            "Performance set to 0%."
                        )
            
            # Quality - get scrap rate for this resource
            df_scrap_resource = self.scrap_analytics.df_scrap_per_resource.copy()
            resource_scrap = df_scrap_resource[df_scrap_resource["Resource"] == resource]
            
            if len(resource_scrap) > 0:
                scrap_rate = resource_scrap["Scrap_rate"].iloc[0]
                quality = 1 - (scrap_rate / 100)
            else:
                quality = 1.0
            
            # Calculate OEE
            oee = availability * performance * quality
            
            oee_results.append({
                "Resource": resource,
                "Availability": round(availability * 100, 2),
                "Performance": round(performance * 100, 2),
                "Quality": round(quality * 100, 2),
                "OEE": round(oee * 100, 2),
            })

        return pd.DataFrame(oee_results)
    
    def get_oee_per_resource_by_interval(self, interval_minutes: float) -> pd.DataFrame:
        """
        Calculate OEE for each resource aggregated by time intervals.
        
        Calculates OEE on the complete event log, then aggregates by intervals.
        
        Optimized version using vectorized operations and pre-computed lookups.
        
        Args:
            interval_minutes: Time interval in minutes for aggregation.
            
        Returns:
            pd.DataFrame: DataFrame with OEE components per resource per interval.
                         Columns: Resource, Interval_start, Interval_end, Availability,
                         Performance, Quality, OEE
        """
        if self.context.production_system_data is None:
            logger.warning(
                "production_system_data not available. Cannot calculate resource-level OEE by interval."
            )
            return pd.DataFrame(columns=["Resource", "Interval_start", "Interval_end", 
                                        "Availability", "Performance", "Quality", "OEE"])
        
        # Get resource states by interval
        df_resource_states_interval = self.resource_states_analytics.get_resource_states_by_interval(interval_minutes)
        
        if len(df_resource_states_interval) == 0:
            return pd.DataFrame(columns=["Resource", "Interval_start", "Interval_end", 
                                        "Availability", "Performance", "Quality", "OEE"])
        
        # Get time model factory
        from prodsys.factories.time_model_factory import TimeModelFactory
        time_model_factory = TimeModelFactory()
        time_model_factory.create_time_models(self.context.production_system_data)
        
        # Pre-compute resource capacities and process ideal times (cache for all resources)
        resource_capacities = {}
        resource_process_capacities = {}
        process_ideal_times_cache = {}
        
        for resource_data in self.context.production_system_data.resource_data:
            resource_id = resource_data.ID
            resource_capacities[resource_id] = resource_data.capacity if hasattr(resource_data, 'capacity') else 1
            if hasattr(resource_data, 'process_capacities') and resource_data.process_capacities:
                resource_process_capacities[resource_id] = {}
                if hasattr(resource_data, 'process_ids'):
                    for i, process_id in enumerate(resource_data.process_ids):
                        if i < len(resource_data.process_capacities):
                            resource_process_capacities[resource_id][process_id] = resource_data.process_capacities[i]
        
        # Pre-compute ideal cycle times for all processes
        for process_data in self.context.production_system_data.process_data:
            if hasattr(process_data, 'time_model_id'):
                try:
                    time_model = time_model_factory.get_time_model(process_data.time_model_id)
                    ideal_cycle_time = time_model.get_expected_time()
                    if ideal_cycle_time > 0:
                        process_ideal_times_cache[process_data.ID] = ideal_cycle_time
                except (ValueError, TypeError):
                    pass
        
        # Identify transport resources
        from prodsys.models.production_system_data import get_transport_resources
        transport_resources = get_transport_resources(self.context.production_system_data)
        transport_resource_ids = {r.ID for r in transport_resources}
        
        # Pre-filter and prepare process events data once (not per interval)
        df_prepared = self.data_prep.df_prepared.copy()
        if self.context.warm_up_cutoff:
            warm_up_time = self.throughput_analytics.warm_up_cutoff_time
            df_prepared = df_prepared[df_prepared["Time"] >= warm_up_time]
        
        # Filter production events once
        production_mask = (
            (df_prepared["State Type"] == state.StateTypeEnum.production) &
            (df_prepared["Resource"].notna())
        )
        df_production = df_prepared[production_mask].copy()
        
        # Separate start and end events
        df_process_starts = df_production[
            df_production["Activity"] == "start state"
        ][["Resource", "State", "Time"]].copy()
        df_process_ends = df_production[
            df_production["Activity"] == "end state"
        ][["Resource", "State", "Time"]].copy()
        
        # Sort for efficient merge_asof operations
        df_process_starts = df_process_starts.sort_values(["Resource", "State", "Time"])
        df_process_ends = df_process_ends.sort_values(["Resource", "State", "Time"])
        
        # Create index on Resource for faster lookups
        # Keep sorted by State and Time for merge_asof
        df_process_starts_by_resource = {
            resource: group.sort_values(["State", "Time"]).reset_index(drop=True)
            for resource, group in df_process_starts.groupby("Resource")
        }
        
        # Pre-compute scrap rates per resource (cache)
        df_scrap_resource = self.scrap_analytics.df_scrap_per_resource.copy()
        scrap_rates = df_scrap_resource.set_index("Resource")["Scrap_rate"].to_dict()
        
        # Pivot resource states to get time per state per interval efficiently
        df_states_pivot = df_resource_states_interval.pivot_table(
            index=["Resource", "Interval_start", "Interval_end"],
            columns="Time_type",
            values="time_increment",
            fill_value=0
        ).reset_index()
        
        # Calculate availability for all intervals at once (vectorized)
        df_states_pivot["interval_time"] = (
            df_states_pivot["Interval_end"] - df_states_pivot["Interval_start"]
        )
        df_states_pivot["non_scheduled_time"] = df_states_pivot.get("NS", 0)
        df_states_pivot["productive_time"] = df_states_pivot.get("PR", 0)
        df_states_pivot["setup_time"] = df_states_pivot.get("ST", 0)
        df_states_pivot["dependency_time"] = df_states_pivot.get("DP", 0)
        
        df_states_pivot["scheduled_time"] = (
            df_states_pivot["interval_time"] - df_states_pivot["non_scheduled_time"]
        )
        
        # Vectorized availability calculation
        availability = (
            df_states_pivot["productive_time"] + 
            df_states_pivot["setup_time"] + 
            df_states_pivot["dependency_time"]
        ) / df_states_pivot["scheduled_time"].replace(0, np.nan)
        availability = availability.fillna(0).clip(0, 1)
        df_states_pivot["availability"] = availability
        
        # Pre-match all process starts and ends efficiently using merge_asof
        # This creates a lookup table of all matched processes
        matched_processes_list = []
        
        for resource in df_process_ends["Resource"].unique():
            # Filter and copy, ensuring we have a clean dataframe
            resource_ends = df_process_ends[df_process_ends["Resource"] == resource].copy()
            resource_starts = df_process_starts_by_resource.get(resource, pd.DataFrame())
            
            if len(resource_starts) == 0 or len(resource_ends) == 0:
                continue
            
            # Process by State to ensure proper sorting for merge_asof
            # merge_asof with by="State" requires sorting by [State, time] within each State group
            for state_id in resource_ends["State"].unique():
                state_ends = resource_ends[resource_ends["State"] == state_id].copy()
                state_starts = resource_starts[resource_starts["State"] == state_id].copy()
                
                if len(state_starts) == 0 or len(state_ends) == 0:
                    continue
                
                # Rename columns - keep Resource and State columns
                state_ends = state_ends.rename(columns={"Time": "end_time"})
                state_starts = state_starts.rename(columns={"Time": "start_time"})
                
                # Ensure Resource and State columns are present
                if "Resource" not in state_ends.columns:
                    state_ends["Resource"] = resource
                if "State" not in state_ends.columns:
                    state_ends["State"] = state_id
                
                # Sort by time only (since we're already filtered by State)
                state_ends = state_ends.sort_values("end_time", kind='mergesort').reset_index(drop=True)
                state_starts = state_starts.sort_values("start_time", kind='mergesort').reset_index(drop=True)
                
                # Use merge_asof - it will keep all columns from left (state_ends)
                # and add start_time from right (state_starts)
                matched = pd.merge_asof(
                    state_ends,
                    state_starts[["start_time"]].reset_index(drop=True),
                    left_on="end_time",
                    right_on="start_time",
                    direction="backward",
                    allow_exact_matches=True
                )
                
                # Calculate actual time and filter valid matches
                matched = matched[matched["start_time"].notna()]
                matched["actual_time"] = matched["end_time"] - matched["start_time"]
                matched = matched[matched["actual_time"] > 0]
                
                if len(matched) > 0:
                    matched_processes_list.append(matched[["Resource", "State", "start_time", "end_time", "actual_time"]])
        
        if matched_processes_list:
            df_matched = pd.concat(matched_processes_list, ignore_index=True)
        else:
            df_matched = pd.DataFrame(columns=["Resource", "State", "start_time", "end_time", "actual_time"])
        
        # Calculate performance per interval using fully vectorized operations
        # Split processes that span multiple intervals proportionally
        if len(df_matched) > 0:
            # Get unique intervals per resource (sorted by start time)
            intervals_lookup = df_states_pivot[["Resource", "Interval_start", "Interval_end"]].drop_duplicates()
            intervals_lookup = intervals_lookup.sort_values(["Resource", "Interval_start"]).reset_index(drop=True)
            
            # Get simulation end time for interval boundary calculation
            simulation_end_time = self._get_total_simulation_time()
            if self.context.warm_up_cutoff:
                min_time = self.throughput_analytics.warm_up_cutoff_time
            else:
                min_time = df_matched["start_time"].min() if len(df_matched) > 0 else 0.0
            
            # Prepare process data for interval overlap calculation
            df_processes = df_matched[["Resource", "State", "start_time", "end_time", "actual_time"]].copy()
            df_processes['process_start'] = df_processes['start_time'].values
            df_processes['process_end'] = df_processes['end_time'].values
            df_processes['process_duration'] = np.maximum(df_processes['process_end'] - df_processes['process_start'], 1e-10)
            
            # Calculate interval indices for all processes at once (fully vectorized)
            process_starts = df_processes['process_start'].values
            process_ends = df_processes['process_end'].values
            
            # Calculate first and last interval index for each process (vectorized)
            first_interval_indices = np.maximum(0, np.floor((process_starts - min_time) / interval_minutes).astype(int))
            last_interval_indices = np.ceil((process_ends - min_time) / interval_minutes).astype(int)
            
            # Create interval index ranges for each process (vectorized)
            interval_ranges = [
                np.arange(first_idx, last_idx) if last_idx > first_idx else np.array([], dtype=int)
                for first_idx, last_idx in zip(first_interval_indices, last_interval_indices)
            ]
            
            # Add interval ranges to dataframe for explode
            df_processes['interval_indices'] = interval_ranges
            
            # Explode to create one row per process-interval pair
            df_expanded = df_processes.explode('interval_indices', ignore_index=True)
            
            # Filter out rows where interval_indices is NaN (no overlapping intervals)
            df_expanded = df_expanded[df_expanded['interval_indices'].notna()].copy()
            
            if len(df_expanded) == 0:
                performance_by_interval = pd.DataFrame(columns=["Resource", "Interval_start", "Interval_end", "actual_time", "total_ideal_time"])
            else:
                # Calculate interval boundaries (vectorized)
                df_expanded['Interval_start'] = min_time + df_expanded['interval_indices'].astype(int) * interval_minutes
                df_expanded['Interval_end'] = np.minimum(
                    df_expanded['Interval_start'] + interval_minutes,
                    simulation_end_time
                )
                
                # Filter to only overlapping intervals (vectorized)
                overlap_mask = (
                    (df_expanded['Interval_end'] > df_expanded['process_start']) &
                    (df_expanded['Interval_start'] < df_expanded['process_end'])
                )
                df_expanded = df_expanded[overlap_mask].copy()
                
                if len(df_expanded) == 0:
                    performance_by_interval = pd.DataFrame(columns=["Resource", "Interval_start", "Interval_end", "actual_time", "total_ideal_time"])
                else:
                    # Calculate overlaps (vectorized)
                    df_expanded['overlap_start'] = np.maximum(df_expanded['process_start'], df_expanded['Interval_start'])
                    df_expanded['overlap_end'] = np.minimum(df_expanded['process_end'], df_expanded['Interval_end'])
                    df_expanded['overlap_duration'] = np.maximum(df_expanded['overlap_end'] - df_expanded['overlap_start'], 0)
                    
                    # Filter to non-zero overlaps
                    df_expanded = df_expanded[df_expanded['overlap_duration'] > 0].copy()
                    
                    if len(df_expanded) == 0:
                        performance_by_interval = pd.DataFrame(columns=["Resource", "Interval_start", "Interval_end", "actual_time", "total_ideal_time"])
                    else:
                        # Calculate proportional time (vectorized)
                        # Only count the portion of actual_time that falls within each interval
                        df_expanded['proportion'] = df_expanded['overlap_duration'] / df_expanded['process_duration']
                        df_expanded['scaled_actual_time'] = df_expanded['actual_time'] * df_expanded['proportion']
                        # Use overlap_duration as the actual time for this interval (not the full process time)
                        df_expanded['actual_time'] = df_expanded['overlap_duration']
                        
                        # Add resource capacity and process capacity info
                        df_expanded["resource_capacity"] = df_expanded["Resource"].map(
                            lambda r: resource_capacities.get(r, 1)
                        )
                        df_expanded["process_cap"] = df_expanded.apply(
                            lambda row: resource_process_capacities.get(row["Resource"], {}).get(row["State"], row["resource_capacity"]),
                            axis=1
                        )
                        
                        # Calculate ideal time per process
                        df_expanded["ideal_base"] = df_expanded["State"].map(
                            process_ideal_times_cache
                        ).fillna(0)
                        df_expanded["ideal_per_unit"] = np.where(
                            df_expanded["process_cap"] > 0,
                            df_expanded["ideal_base"] / df_expanded["process_cap"],
                            df_expanded["ideal_base"]
                        )
                        
                        # Scale ideal time proportionally (same proportion as actual time)
                        df_expanded["scaled_ideal_time"] = df_expanded["ideal_per_unit"] * df_expanded["proportion"]
                        
                        # Aggregate by interval to get total actual and ideal time
                        performance_by_interval = df_expanded.groupby(
                            ["Resource", "Interval_start", "Interval_end"]
                        ).agg({
                            "actual_time": "sum",
                            "scaled_ideal_time": "sum"
                        }).reset_index()
                        performance_by_interval = performance_by_interval.rename(columns={"scaled_ideal_time": "total_ideal_time"})
        else:
            performance_by_interval = pd.DataFrame(columns=["Resource", "Interval_start", "Interval_end", "actual_time", "total_ideal_time"])
        
        # Merge performance data with df_states_pivot
        df_states_pivot = df_states_pivot.merge(
            performance_by_interval,
            on=["Resource", "Interval_start", "Interval_end"],
            how="left"
        )
        df_states_pivot["actual_time"] = df_states_pivot["actual_time"].fillna(0)
        df_states_pivot["total_ideal_time"] = df_states_pivot["total_ideal_time"].fillna(0)
        
        # Calculate performance vectorized
        # Handle transport resources
        is_transport = df_states_pivot["Resource"].isin(transport_resource_ids)
        
        # For non-transport resources: performance = total_ideal_time / actual_time (or productive_time as fallback)
        performance = np.where(
            is_transport,
            1.0,  # Transport resources default to 100%
            np.where(
                (df_states_pivot["actual_time"] > 0) & (df_states_pivot["total_ideal_time"] > 0),
                df_states_pivot["total_ideal_time"] / df_states_pivot["actual_time"],
                np.where(
                    (df_states_pivot["productive_time"] > 0) & (df_states_pivot["total_ideal_time"] > 0),
                    df_states_pivot["total_ideal_time"] / df_states_pivot["productive_time"],
                    0.0
                )
            )
        )
        
        df_states_pivot["performance"] = performance
        
        # Calculate quality (vectorized using cached scrap rates)
        df_states_pivot["scrap_rate"] = df_states_pivot["Resource"].map(scrap_rates).fillna(0)
        df_states_pivot["quality"] = 1 - (df_states_pivot["scrap_rate"] / 100)
        
        # Calculate OEE
        df_states_pivot["oee"] = (
            df_states_pivot["availability"] * 
            df_states_pivot["performance"] * 
            df_states_pivot["quality"]
        )
        
        # Create result dataframe
        result_df = pd.DataFrame({
            "Resource": df_states_pivot["Resource"],
            "Interval_start": df_states_pivot["Interval_start"],
            "Interval_end": df_states_pivot["Interval_end"],
            "Availability": (df_states_pivot["availability"] * 100).round(2),
            "Performance": (df_states_pivot["performance"] * 100).round(2),
            "Quality": (df_states_pivot["quality"] * 100).round(2),
            "OEE": (df_states_pivot["oee"] * 100).round(2),
        })
        
        return result_df