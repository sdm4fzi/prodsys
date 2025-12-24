"""
OEE analytics module.

This module handles Overall Equipment Effectiveness (OEE) calculations.
"""

from __future__ import annotations

from functools import cached_property

import pandas as pd

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
        
        # Get processes per resource
        resource_to_processes = {}
        for resource_data in self.context.production_system_data.resource_data:
            if hasattr(resource_data, 'process_ids'):
                resource_to_processes[resource_data.ID] = resource_data.process_ids
        
        # Identify transport resources
        from prodsys.models.production_system_data import get_transport_resources
        transport_resources = get_transport_resources(self.context.production_system_data)
        transport_resource_ids = {r.ID for r in transport_resources}
        
        # Get prepared data for process counting
        df_prepared = self.data_prep.df_prepared.copy()
        if self.context.warm_up_cutoff:
            warm_up_time = self.throughput_analytics.warm_up_cutoff_time
            df_prepared = df_prepared[df_prepared["Time"] >= warm_up_time]
        
        # Calculate OEE per resource per interval
        oee_results = []
        
        # Group by resource and interval
        for (resource, interval_start, interval_end), df_interval in df_resource_states_interval.groupby(
            ["Resource", "Interval_start", "Interval_end"]
        ):
            # Get time per state for this interval
            time_per_state = df_interval.set_index("Time_type")["time_increment"]
            
            # Get time components
            non_scheduled_time = time_per_state.get("NS", 0)
            setup_time = time_per_state.get("ST", 0)
            productive_time = time_per_state.get("PR", 0)
            dependency_time = time_per_state.get("DP", 0)
            
            # Interval time
            interval_time = interval_end - interval_start
            
            # Availability: (PR + ST + DP) / (Interval Time - Non-scheduled Time)
            scheduled_time = interval_time - non_scheduled_time
            
            if scheduled_time > 0:
                # Calculate availability, but ensure it doesn't exceed 100%
                # This can happen if resource states sum to more than 100% due to rounding/aggregation issues
                availability = (productive_time + setup_time + dependency_time) / scheduled_time
                # Clip to 0-1 range (0-100%)
                availability = min(availability, 1.0)
            else:
                availability = 0.0
            
            # Performance calculation
            is_transport_resource = resource in transport_resource_ids
            
            if is_transport_resource:
                performance = 1.0
            else:
                # Count process end events in this interval
                resource_process_ends = df_prepared[
                    (df_prepared["Resource"] == resource) &
                    (df_prepared["State Type"] == state.StateTypeEnum.production) &
                    (df_prepared["Activity"] == "end state") &
                    (df_prepared["Time"] >= interval_start) &
                    (df_prepared["Time"] < interval_end)
                ]
                total_units_produced = len(resource_process_ends)
                
                if total_units_produced > 0:
                    # Get resource capacity
                    resource_capacity = 1
                    process_capacities = {}
                    for resource_data in self.context.production_system_data.resource_data:
                        if resource_data.ID == resource:
                            resource_capacity = resource_data.capacity if hasattr(resource_data, 'capacity') else 1
                            if hasattr(resource_data, 'process_capacities') and resource_data.process_capacities:
                                for i, process_id in enumerate(resource_data.process_ids):
                                    if i < len(resource_data.process_capacities):
                                        process_capacities[process_id] = resource_data.process_capacities[i]
                            break
                    
                    # Get actual process execution times
                    resource_process_starts = df_prepared[
                        (df_prepared["Resource"] == resource) &
                        (df_prepared["State Type"] == state.StateTypeEnum.production) &
                        (df_prepared["Activity"] == "start state")
                    ].copy()
                    
                    actual_process_times = []
                    for _, end_row in resource_process_ends.iterrows():
                        process_id = end_row["State"]
                        end_time = end_row["Time"]
                        
                        matching_starts = resource_process_starts[
                            (resource_process_starts["State"] == process_id) &
                            (resource_process_starts["Time"] <= end_time)
                        ]
                        
                        if len(matching_starts) > 0:
                            start_time = matching_starts["Time"].max()
                            actual_time = end_time - start_time
                            if actual_time > 0:
                                actual_process_times.append((process_id, actual_time))
                    
                    # Calculate total ideal time and total actual time
                    total_ideal_time = 0.0
                    total_actual_time = 0.0
                    process_ideal_times = {}
                    
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
                    
                    for process_id, actual_time in actual_process_times:
                        total_actual_time += actual_time
                        if process_id in process_ideal_times:
                            total_ideal_time += process_ideal_times[process_id]
                    
                    if total_actual_time > 0 and total_ideal_time > 0:
                        performance = total_ideal_time / total_actual_time
                    elif productive_time > 0 and total_ideal_time > 0:
                        performance = total_ideal_time / productive_time
                    else:
                        performance = 0.0
                else:
                    performance = 0.0
            
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
                "Interval_start": interval_start,
                "Interval_end": interval_end,
                "Availability": round(availability * 100, 2),
                "Performance": round(performance * 100, 2),
                "Quality": round(quality * 100, 2),
                "OEE": round(oee * 100, 2),
            })
        
        return pd.DataFrame(oee_results)