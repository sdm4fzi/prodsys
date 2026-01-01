"""
WIP analytics module.

This module handles Work-in-Progress (WIP) calculations.
"""

from __future__ import annotations

from functools import cached_property
from typing import List

import pandas as pd

from prodsys.simulation import state
from prodsys.models import performance_indicators
from prodsys.analytics.base import AnalyticsContext
from prodsys.analytics.data_preparation import DataPreparation
from prodsys.analytics.throughput import ThroughputAnalytics

import logging

logger = logging.getLogger(__name__)


class WIPAnalytics:
    """
    Handles Work-in-Progress (WIP) calculations.
    """
    
    def __init__(
        self,
        context: AnalyticsContext,
        data_prep: DataPreparation,
        throughput_analytics: ThroughputAnalytics,
    ):
        """
        Initialize WIP analytics.
        
        Args:
            context: Analytics context containing raw data and configuration.
            data_prep: Data preparation instance.
            throughput_analytics: Throughput analytics instance.
        """
        self.context = context
        self.data_prep = data_prep
        self.throughput_analytics = throughput_analytics
    
    def get_WIP_KPI(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate WIP over time based on created and finished products.
        This tracks total system WIP and includes finished products at sinks.
        
        Args:
            df: DataFrame with simulation events
            
        Returns:
            pd.DataFrame: DataFrame with WIP tracking over time
        """
        CREATED_CONDITION = df["Activity"] == "created product"
        FINISHED_CONDITION = df["Activity"] == "finished product"
        CONSUMED_CONDITION = df["Activity"] == "consumed product"

        df["WIP_Increment"] = 0
        df.loc[CREATED_CONDITION, "WIP_Increment"] = 1
        # Track finished products (including at sinks) to decrease total WIP
        df.loc[FINISHED_CONDITION, "WIP_Increment"] = -1
        # Also track consumed products to decrease WIP
        df.loc[CONSUMED_CONDITION, "WIP_Increment"] = -1
        
        df = df.loc[
            df["WIP_Increment"] != 0
        ].copy()  # Remove rows where WIP_Increment is 0

        # If no rows with WIP changes, return empty dataframe with WIP column as float
        if len(df) == 0:
            # Add WIP column as float type for consistency
            df = df.copy()
            df["WIP"] = pd.Series(dtype=float)
            return df

        # Sort by time to ensure correct cumulative sum
        df = df.sort_values(by="Time").reset_index(drop=True)
        
        # Calculate WIP as float to handle potential NaN values
        df["WIP"] = df["WIP_Increment"].cumsum().astype(float)
        
        # Ensure WIP never goes negative (clip at 0)
        # This handles edge cases where finished products might be logged before created products
        # or other timing issues
        df["WIP"] = df["WIP"].clip(lower=0.0)
        
        return df

    def get_primitive_WIP_KPI(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate primitive WIP over time."""
        primitive_types = self.data_prep.get_primitive_types()
        START_USAGE_CONDITION = (df["Activity"] == "start state") & (df["State"] == "Dependency") & (df["Primitive_type"].isin(primitive_types))
        FINISHED_USAGE_CONDITION = (df["Activity"] == "end state") & (df["State"] == "Dependency") & (df["Primitive_type"].isin(primitive_types))

        df["primitive_WIP_Increment"] = 0
        df.loc[START_USAGE_CONDITION, "primitive_WIP_Increment"] = 1
        df.loc[FINISHED_USAGE_CONDITION, "primitive_WIP_Increment"] = -1

        df["primitive_WIP"] = df["primitive_WIP_Increment"].cumsum()

        return df

    @cached_property
    def df_primitive_WIP(self) -> pd.DataFrame:
        """
        Returns a data frame with the WIP over time for each primitive.

        Returns:
            pd.DataFrame: Data frame with the WIP over time for each primitive.
        """
        df = self.get_primitive_WIP_KPI(self.data_prep.df_prepared)
        return df

    @cached_property
    def df_primitive_WIP_per_primitive_type(self) -> pd.DataFrame:
        """
        Returns a data frame with the WIP over time for each primitive.

        Returns:
            pd.DataFrame: Data frame with the WIP over time for each primitive.
        """
        df = pd.DataFrame()
        primitive_types = self.data_prep.get_primitive_types()
        for primitive_type in primitive_types:
            df_temp = self.data_prep.df_prepared.loc[
                self.data_prep.df_prepared["Primitive_type"] == primitive_type
            ].copy()
            df_temp = self.get_primitive_WIP_KPI(df_temp)
            df = df.combine_first(df_temp)

        return df

    @cached_property
    def df_aggregated_primitive_WIP(self) -> pd.DataFrame:
        """
        Returns a data frame with the average WIP for each primitive.

        Returns:
            pd.DataFrame: Data frame with the average WIP for each primitive.
        """
        df = self.df_primitive_WIP_per_primitive_type.copy()
        df_total = self.df_primitive_WIP.copy()
        df_total["Primitive_type"] = "Total"

        df = pd.concat([df, df_total])

        if self.context.warm_up_cutoff:
            df = df.loc[df["Time"] >= self.throughput_analytics.warm_up_cutoff_time]

        group = ["Primitive_type"]
        df = df.groupby(by=group)["primitive_WIP"].mean()

        return df

    @cached_property
    def df_WIP(self) -> pd.DataFrame:
        """
        Returns a data frame with the WIP over time in the total production system.

        Returns:
            pd.DataFrame: Data frame with the WIP over time in the total production system.
        """
        # Use df_prepared because it contains created/finished product activities
        # that are needed for WIP calculation
        df = self.data_prep.df_prepared.copy()
        return self.get_WIP_KPI(df)

    @cached_property
    def df_WIP_per_product(self) -> pd.DataFrame:
        """
        Returns a data frame with the WIP over time for each product type.

        Returns:
            pd.DataFrame: Data frame with the WIP over time for each product type.
        """
        # Use df_prepared because it contains created/finished product activities
        # that are needed for WIP calculation
        df_base = self.data_prep.df_prepared.copy()
        df_base = self.data_prep.get_df_with_product_entries(df_base).copy()
        df_base = df_base.reset_index()
        
        # Collect results for each product type
        result_dfs = []
        for product_type in df_base["Product_type"].unique():
            if product_type != product_type:  # Skip NaN
                continue
            df_temp = df_base.loc[df_base["Product_type"] == product_type].copy()
            df_temp = self.get_WIP_KPI(df_temp)
            
            # Ensure WIP column is float to handle NaN values properly
            if "WIP" in df_temp.columns:
                df_temp["WIP"] = df_temp["WIP"].astype(float)
            
            if len(df_temp) > 0:
                result_dfs.append(df_temp)
        
        # Combine all product type dataframes
        if result_dfs:
            df = pd.concat(result_dfs, ignore_index=True)
            # Ensure WIP is float type and handle any NaN values
            if "WIP" in df.columns:
                df["WIP"] = pd.to_numeric(df["WIP"], errors='coerce').fillna(0.0)
            return df
        else:
            # Return empty dataframe with expected structure
            return pd.DataFrame(columns=["Product_type", "Time", "WIP", "WIP_Increment"])

    def get_WIP_per_resource_KPI(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate WIP per resource over time.
        
        WIP tracking rules:
        - Create product: +1 at source resource
        - Finish product: -1 at sink resource
        - End loading: +1 at resource (the resource doing the loading), -1 at queue (Origin location)
        - End unloading: -1 at resource (the resource doing the unloading), +1 at queue (Target location)
        - Production states: No WIP changes
        - Transport states: No WIP changes
        - Sink resources and sink input queues are excluded from WIP calculation
        
        Args:
            df: DataFrame with resource states
            
        Returns:
            pd.DataFrame: DataFrame with WIP tracking per resource
        """
        df = df.loc[df["Time"] != 0].copy()
        df["WIP_Increment"] = 0
        df["WIP_resource"] = None

        # Identify sink resources and sink input queues to exclude from WIP
        sink_resources = df[df["State Type"] == state.StateTypeEnum.sink]["Resource"].unique()
        sink_resources_set = set(sink_resources)
        
        # Find sink input queues by looking for queues that receive products from unloading events targeting sinks
        # and queues that are associated with sink resources
        sink_queues = set()
        # Check for queues that are unloaded to when Resource is a sink
        unloading_to_sinks = df[
            (df["State Type"].isin([state.StateTypeEnum.unloading, "Unloading"])) &
            (df["Resource"].isin(sink_resources_set)) &
            (df["Target location"].notna())
        ]["Target location"].unique()
        sink_queues.update(unloading_to_sinks)
        
        # Also check for queues that might be sink input queues (could be identified by naming pattern)
        # If there are any queues that appear only in unloading events targeting sinks, they're likely sink input queues
        all_unloading_targets = df[
            (df["State Type"].isin([state.StateTypeEnum.unloading, "Unloading"])) &
            (df["Target location"].notna())
        ]["Target location"].unique()
        for queue_id in all_unloading_targets:
            # If this queue is only ever the target of unloading to sink resources, it's a sink input queue
            unloading_events_to_queue = df[
                (df["State Type"].isin([state.StateTypeEnum.unloading, "Unloading"])) &
                (df["Target location"] == queue_id)
            ]
            if len(unloading_events_to_queue) > 0:
                # Check if all unloading events to this queue are from sink resources
                resources_unloading_to_queue = unloading_events_to_queue["Resource"].unique()
                if all(resource in sink_resources_set for resource in resources_unloading_to_queue):
                    sink_queues.add(queue_id)

        # Rule 1: Create product -> +1 at source (but exclude if source is a sink, which shouldn't happen)
        CREATED_CONDITION = df["Activity"] == state.StateEnum.created_product
        created_mask = CREATED_CONDITION & ~df["Resource"].isin(sink_resources_set)
        df.loc[created_mask, "WIP_Increment"] = 1
        df.loc[created_mask, "WIP_resource"] = df.loc[created_mask, "Resource"]

        # Rule 2: Consume product -> -1 at resource (but exclude sinks)
        CONSUMED_CONDITION = df["Activity"] == state.StateEnum.consumed_product
        consumed_mask = CONSUMED_CONDITION & ~df["Resource"].isin(sink_resources_set)
        df.loc[consumed_mask, "WIP_Increment"] = -1
        df.loc[consumed_mask, "WIP_resource"] = df.loc[consumed_mask, "Resource"]

        # Rule 3: End loading -> +1 at resource, -1 at Origin location (queue)
        # Exclude if resource is a sink or origin location is a sink queue
        loading_condition = (df["State Type"] == state.StateTypeEnum.loading) | (df["State Type"] == "Loading")
        end_loading = loading_condition & (df["Activity"] == "end state")
        # Exclude loading events from sink resources
        end_loading_valid = end_loading & ~df["Resource"].isin(sink_resources_set)
        
        # Create rows for end loading: +1 at resource (exclude sinks)
        if end_loading_valid.any():
            end_loading_resource_df = df[end_loading_valid].copy()
            end_loading_resource_df["WIP_Increment"] = 1
            end_loading_resource_df["WIP_resource"] = end_loading_resource_df["Resource"]
        else:
            end_loading_resource_df = pd.DataFrame()
        
        # Create rows for end loading: -1 at Origin location (queue) - exclude sink queues
        if end_loading_valid.any():
            end_loading_queue_df = df[end_loading_valid].copy()
            # Filter out sink queues
            end_loading_queue_df = end_loading_queue_df[
                ~end_loading_queue_df["Origin location"].isin(sink_queues)
            ]
            if len(end_loading_queue_df) > 0:
                end_loading_queue_df["WIP_Increment"] = -1
                end_loading_queue_df["WIP_resource"] = end_loading_queue_df["Origin location"]
            else:
                end_loading_queue_df = pd.DataFrame()
        else:
            end_loading_queue_df = pd.DataFrame()

        # Rule 4: End unloading -> -1 at resource, +1 at Target location (queue)
        # Exclude if resource is a sink or target location is a sink queue
        unloading_condition = (df["State Type"] == state.StateTypeEnum.unloading) | (df["State Type"] == "Unloading")
        end_unloading = unloading_condition & (df["Activity"] == "end state")
        # Exclude unloading events from sink resources
        end_unloading_valid = end_unloading & ~df["Resource"].isin(sink_resources_set)
        
        # Create rows for end unloading: -1 at resource (exclude sinks)
        if end_unloading_valid.any():
            end_unloading_resource_df = df[end_unloading_valid].copy()
            end_unloading_resource_df["WIP_Increment"] = -1
            end_unloading_resource_df["WIP_resource"] = end_unloading_resource_df["Resource"]
        else:
            end_unloading_resource_df = pd.DataFrame()
        
        # Create rows for end unloading: +1 at Target location (queue) - EXCLUDE SINK QUEUES
        if end_unloading_valid.any():
            end_unloading_queue_df = df[end_unloading_valid].copy()
            # Filter out sink input queues from WIP calculation
            end_unloading_queue_df = end_unloading_queue_df[
                ~end_unloading_queue_df["Target location"].isin(sink_queues)
            ]
            if len(end_unloading_queue_df) > 0:
                end_unloading_queue_df["WIP_Increment"] = 1
                end_unloading_queue_df["WIP_resource"] = end_unloading_queue_df["Target location"]
            else:
                end_unloading_queue_df = pd.DataFrame()
        else:
            end_unloading_queue_df = pd.DataFrame()

        # Combine all dataframes (only non-empty ones)
        dfs_to_concat = [df]
        if len(end_loading_resource_df) > 0:
            dfs_to_concat.append(end_loading_resource_df)
        if len(end_loading_queue_df) > 0:
            dfs_to_concat.append(end_loading_queue_df)
        if len(end_unloading_resource_df) > 0:
            dfs_to_concat.append(end_unloading_resource_df)
        if len(end_unloading_queue_df) > 0:
            dfs_to_concat.append(end_unloading_queue_df)
        
        df = pd.concat(dfs_to_concat, ignore_index=True)

        df = df.sort_values(
            by=["Time", "WIP_Increment"], 
            ascending=[True, False], 
            ignore_index=True
        )

        # Filter out rows with no WIP_resource
        df = df[df["WIP_resource"].notna()]
        
        # Filter out sink resources and sink queues from final results
        df = df[~df["WIP_resource"].isin(sink_resources_set)]
        df = df[~df["WIP_resource"].isin(sink_queues)]
        
        # Sort by resource and time before calculating cumulative WIP
        df = df.sort_values(by=["WIP_resource", "Time"]).reset_index(drop=True)
        
        # Calculate cumulative WIP per resource
        df["WIP"] = df.groupby(by="WIP_resource")["WIP_Increment"].cumsum()
        
        # Ensure WIP never goes negative (clip at 0) to handle edge cases
        # This prevents negative values that could occur due to timing issues or data inconsistencies
        df["WIP"] = df["WIP"].clip(lower=0)

        return df

    @cached_property
    def df_WIP_per_resource(self) -> pd.DataFrame:
        """
        Returns a data frame with the WIP over time for each resource.

        Returns:
            pd.DataFrame: Data frame with the WIP over time for each resource.
        """
        # Use df_prepared instead of df_resource_states because WIP calculation
        # needs loading/unloading events that are filtered out of df_resource_states
        df = self.data_prep.df_prepared.copy()
        df = self.get_WIP_per_resource_KPI(df)

        return df

    @cached_property
    def dynamic_WIP_per_resource_KPIs(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of Dynamic WIP KPI values for the WIP over time for each product type.

        Returns:
            List[performance_indicators.KPI]: List of Dynamic WIP KPI values.
        """
        df = self.df_WIP_per_resource.copy()
        df = df.loc[df["WIP_Increment"] != 0]

        KPIs = []
        df["next_Time"] = df.groupby(by="WIP_resource")["Time"].shift(-1)
        df["next_Time"] = df["next_Time"].fillna(df["Time"])
        for index, row in df.iterrows():
            KPIs.append(
                performance_indicators.DynamicWIP(
                    name=performance_indicators.KPIEnum.DYNAMIC_WIP,
                    value=row["WIP"],
                    context=(
                        performance_indicators.KPILevelEnum.RESOURCE,
                        performance_indicators.KPILevelEnum.ALL_PRODUCTS,
                    ),
                    product_type="Total",
                    resource=row["WIP_resource"],
                    start_time=row["Time"],
                    end_time=row["next_Time"],
                )
            )
        return KPIs

    @cached_property
    def dynamic_system_WIP_KPIs(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of Dynamic WIP KPI values for the WIP over time for each product type and the whole system.

        Returns:
            List[performance_indicators.KPI]: List of Dynamic WIP KPI values.
        """
        df = self.df_WIP.copy()
        df["Product_type"] = "Total"
        df_per_product = self.df_WIP_per_product.copy()
        df = pd.concat([df, df_per_product])
        df = df.loc[~df["WIP_Increment"].isnull()]

        KPIs = []
        df["next_Time"] = df.groupby(by="Product_type")["Time"].shift(-1)
        df["next_Time"] = df["next_Time"].fillna(df["Time"])
        for index, row in df.iterrows():
            if row["Product_type"] == "Total":
                context = (
                    performance_indicators.KPILevelEnum.SYSTEM,
                    performance_indicators.KPILevelEnum.ALL_PRODUCTS,
                )
            else:
                context = (
                    performance_indicators.KPILevelEnum.SYSTEM,
                    performance_indicators.KPILevelEnum.PRODUCT_TYPE,
                )
            KPIs.append(
                performance_indicators.DynamicWIP(
                    name=performance_indicators.KPIEnum.DYNAMIC_WIP,
                    value=row["WIP"],
                    context=context,
                    product_type=row["Product_type"],
                    start_time=row["Time"],
                    end_time=row["next_Time"],
                )
            )
        return KPIs

    @cached_property
    def df_aggregated_WIP(self) -> pd.DataFrame:
        """
        Returns a data frame with the average WIP for each product type and the whole system.

        Returns:
            pd.DataFrame: Dataframe with the average WIP for each product type and the whole system.
        """
        df = self.df_WIP_per_product.copy()
        df_total_wip = self.df_WIP.copy()
        # TODO: probably remove below with primitive type filter, because not needed
        primitive_types = self.data_prep.get_primitive_types()
        df_total_wip = df_total_wip.loc[
            ~df_total_wip["Product_type"].isin(primitive_types)
        ]
        df_total_wip["Product_type"] = "Total"
        df = pd.concat([df, df_total_wip])

        if self.context.warm_up_cutoff:
            df = df.loc[df["Time"] >= self.throughput_analytics.warm_up_cutoff_time]

        group = ["Product_type"]
        df = df.groupby(by=group)["WIP"].mean()

        return df

    @cached_property
    def WIP_KPIs(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of average WIP KPI values for each product type and the whole system.

        Returns:
            List[performance_indicators.KPI]: List of average WIP KPI values.
        """
        ser = self.df_aggregated_WIP.copy()
        KPIs = []
        for index, value in ser.items():
            if index == "Total":
                context = (
                    performance_indicators.KPILevelEnum.SYSTEM,
                    performance_indicators.KPILevelEnum.ALL_PRODUCTS,
                )
                index = performance_indicators.KPILevelEnum.ALL_PRODUCTS
            else:
                context = (
                    performance_indicators.KPILevelEnum.SYSTEM,
                    performance_indicators.KPILevelEnum.PRODUCT_TYPE,
                )
            KPIs.append(
                performance_indicators.WIP(
                    name=performance_indicators.KPIEnum.WIP,
                    value=value,
                    context=context,
                    product_type=index,
                )
            )
        return KPIs

    @cached_property
    def primitive_WIP_KPIs(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of average WIP KPI values for each primitive.

        Returns:
            List[performance_indicators.KPI]: List of average WIP KPI values.
        """
        ser = self.df_aggregated_primitive_WIP.copy()
        KPIs = []
        for index, value in ser.items():
            if index == "Total":
                context = (
                    performance_indicators.KPILevelEnum.SYSTEM,
                    performance_indicators.KPILevelEnum.ALL_PRODUCTS,
                )
                index = performance_indicators.KPILevelEnum.ALL_PRODUCTS
            else:
                context = (
                    performance_indicators.KPILevelEnum.SYSTEM,
                    performance_indicators.KPILevelEnum.PRODUCT_TYPE,
                )
            KPIs.append(
                performance_indicators.PrimitiveWIP(
                    name=performance_indicators.KPIEnum.PRIMITIVE_WIP,
                    value=value,
                    context=context,
                    product_type=index,
                )
            )
        return KPIs
