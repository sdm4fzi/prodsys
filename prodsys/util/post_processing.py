from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

from prodsys.simulation import state
from prodsys.models import performance_indicators

from typing import List, Literal, Optional

import pandas as pd

import numpy as np

import logging

from prodsys.util.warm_up_post_processing import get_warm_up_cutoff_index

logger = logging.getLogger(__name__)


@dataclass
class PostProcessor:
    """
    Class that represents a post processor for the simulation results. It provides methods to read the simulation results from a csv file and to calculate simulation result analysis data and KPIs.

    The data frame that contains the raw simulation results contains the following columns:

        -Time: Time of the event
        -Resource: ID fo the Resource that performed the event
        -State: ID of the State of the resource (production states, transport states, breakdown states, setup states)
        -State Type: Type of the state according to the prodsys.simulation.state.StateTypeEnum
        -Activity: Activity of the resource according to the prodsys.simulation.state.StateEnum
        -Product: ID of the Product that is processed by the resource only for creation and production states
        -Expected End Time: Expected end time of the state at the beginning of the process
        -Target location: Target location of the product at the end of the process

    Args:
        filepath (str): Path to the csv file with the simulation results.
        df_raw (pd.DataFrame): Data frame with the simulation results.
    """

    filepath: str = field(default="")
    df_raw: pd.DataFrame = field(default=None)
    warm_up_cutoff: bool = field(default=False)
    cut_off_method: Optional[Literal["mser5", "threshold_stabilization", "static_ratio"]] = field(
        default=None
    )

    def __post_init__(self):
        if self.filepath:
            self.read_df_from_csv()

    def read_df_from_csv(self, filepath_input: str = None):
        """
        Reads the simulation results from a csv file.

        Args:
            filepath_input (str, optional): Path to the csv file with the simulation results. Defaults to None and the at instantiation provided filepath is used.
        """
        if filepath_input:
            self.filepath = filepath_input
        self.df_raw = pd.read_csv(self.filepath)
        if "Unnamed: 0" in self.df_raw.columns:
            self.df_raw.drop(columns=["Unnamed: 0"], inplace=True)

    def get_conditions_for_interface_state(self, df: pd.DataFrame) -> pd.Series:
        """
        This function returns a Series with the conditions wether a row in the data frame belongs to a interface state or not.
        Hereby, an interface state belongs to a state, where a resource does not perform a process, i.e. either setup, breakdown or creation (source) or finish (sink) of products.

        Args:
            df (pd.DataFrame): Data frame with the simulation results.

        Returns:
            pd.Series: Series with boolean conditions wether a row in the data frame belongs to an interface state or not.
        """
        # TODO: also consider state.StateTypeEnum.process_breakdown for data analysis in the future
        return df["State Type"].isin(
            [
                state.StateTypeEnum.source,
                state.StateTypeEnum.sink,
                state.StateTypeEnum.breakdown,
                state.StateTypeEnum.setup,
                state.StateTypeEnum.charging,
                state.StateTypeEnum.loading,
                state.StateTypeEnum.unloading,
            ]
        )

    def get_conditions_for_process_state(self, df: pd.DataFrame) -> pd.Series:
        """
        This function returns a Series with the conditions wether a row in the data frame belongs to a process state or not.
        Hereby, a process state belongs to a state, where a resource performs a process, i.e. either production or transport.

        Args:
            df (pd.DataFrame): Data frame with the simulation results.

        Returns:
            pd.Series: Series with boolean conditions wether a row in the data frame belongs to a process state or not.
        """
        return df["State Type"].isin(
            [
                state.StateTypeEnum.production,
                state.StateTypeEnum.transport,
                state.StateTypeEnum.dependency,
            ]
        )

    def get_total_simulation_time(self) -> float:
        """
        Calculates the total simulation time from the data frame.

        Returns:
            float: Total simulation time.
        """
        if self.df_raw is not None and "Time" in self.df_raw.columns:
            start_time = self.df_raw["Time"].min()
            end_time = self.df_raw["Time"].max()
            return end_time - start_time
        else:
            raise ValueError("Data frame is not loaded or 'Time' column is missing.")

    @cached_property
    def df_prepared(self) -> pd.DataFrame:
        """
        Adds to self.df_raw the following columns:

            -DateTime: Time of the event
            -Combined_activity: Activity and state of the event combined for easier filtering
            -Product_type: Type of the product
            -State_type: Type of the state according to the StateTypeEnum
            -State_sorting_Index: Index to sort the states in the correct order

        Returns:
            pd.DataFrame: Data frame with the simulation results and the added columns.
        """
        df = self.df_raw.copy()
        
        df["DateTime"] = pd.to_datetime(df["Time"], unit="m")
        df["Combined_activity"] = df["State"].astype(str) + " " + df["Activity"].astype(str)
        
        # Vectorized string operations are efficient
        df["Product_type"] = df["Product"].str.rsplit("_", n=1).str[0]
        
        if "Primitive" not in df.columns:
            df["Primitive"] = None
        df["Primitive_type"] = df["Primitive"].str.rsplit("_", n=1).str[0]
        
        # Use np.select for conditional assignment, which is highly efficient
        conditions = [
            self.get_conditions_for_interface_state(df),
            self.get_conditions_for_process_state(df),
        ]
        choices = ["Interface State", "Process State"]
        df["State_type"] = np.select(conditions, choices, default=pd.NA)

        # TODO: remove this, if processbreakdown is added
        df = df.loc[df["State Type"] != state.StateTypeEnum.process_breakdown].copy()

        # Using a mapping dictionary with .map() is very fast for this kind of transformation
        STATE_SORTING_INDEX = {
            ("Interface State", "finished product"): 1,
            ("Interface State", "created product"): 2,
            ("Interface State", "end state"): 3,
            ("Process State", "end interrupt"): 4,
            ("Process State", "end state"): 5,
            ("Process State", "start state"): 6,
            ("Process State", "start interrupt"): 7,
            ("Interface State", "start state"): 8,
        }
        
        # Create a tuple series to map against the dictionary keys
        state_activity_tuples = zip(df["State_type"], df["Activity"])
        df["State_sorting_Index"] = pd.Series(state_activity_tuples, index=df.index).map(STATE_SORTING_INDEX).fillna(0).astype(int)
        
        return df

    @cached_property
    def df_finished_product(self) -> pd.DataFrame:
        """
        Returns a prepared data frame (df_prepared) with only finished products.

        Returns:
            pd.DataFrame: Data frame with only finished products.
        """
        df = self.df_prepared
        # Using .isin() is faster than merging for filtering
        finished_product_ids = df.loc[
            (df["Product"].notna()) & (df["Activity"] == "finished product"), "Product"
        ].unique()
        return df[df["Product"].isin(finished_product_ids)].copy()

    def get_df_with_product_entries(self, input_df: pd.DataFrame) -> pd.DataFrame:
        # Use vectorized filtering instead of merge (much faster)
        primitive_types = self.get_primitive_types()
        primitive_set = set(primitive_types) if primitive_types else set()
        
        # Vectorized filter - avoid merge operation
        mask = (
            input_df["Product_type"].notna()
            & (input_df["Product_type"] != "")
            & (~input_df["Product_type"].isin(primitive_set))
        )
        return input_df.loc[mask].copy()

    @cached_property
    def df_throughput(self) -> pd.DataFrame:
        """
        Returns a data frame with the throughput time for each finished product.

        Returns:
            pd.DataFrame: Data frame with the throughput time for each finished product.
        """
        df = self.df_prepared
        df_finished = self.df_finished_product
        
        # Group by once and aggregate min and max simultaneously
        agg_df = df_finished.groupby("Product")["Time"].agg(['min', 'max']).reset_index()
        agg_df.columns = ["Product", "Start_time", "End_time"]
        agg_df["Throughput_time"] = agg_df["End_time"] - agg_df["Start_time"]

        # Merge with product types, dropping duplicates for efficiency
        product_types = df[["Product", "Product_type"]].drop_duplicates()
        df_tpt = pd.merge(product_types, agg_df, on="Product")
        
        return df_tpt

    @cached_property
    def warm_up_cutoff_time(self) -> float:
        """
        Calculates the warm up cutoff time for the simulation results.

        Returns:
            float: Warm up cutoff time for the simulation results.
        """
        df = self.df_throughput_with_warum_up_cutoff
        if df["Start_time"].min() == self.df_finished_product["Time"].min():
            return 0.0
        return df["Start_time"].min()

    @cached_property
    def df_throughput_with_warum_up_cutoff(self) -> pd.DataFrame:
        """
        Returns a data frame with the throughput time for each finished product with the warm up phase cut off.

        Returns:
            pd.DataFrame: Data frame with the throughput time for each finished product with the warm up phase cut off.
        """
        df = self.df_throughput.copy()
        product_types_min_start_time = {}
        product_types_max_start_time = {}
        for product_type in df["Product_type"].unique():
            df_product_type = df.loc[df["Product_type"] == product_type].copy()
            df_product_type.sort_values(by="Start_time", inplace=True)
            cutoff_index = get_warm_up_cutoff_index(
                df_product_type, "Throughput_time", self.cut_off_method
            )
            if cutoff_index == len(df_product_type):
                logger.info(
                    f"The simulation time is too short to perform a warm up cutoff for product type {product_type}. Try to increase the simulation time."
                )
                return df
            product_types_min_start_time[product_type] = df_product_type.iloc[
                cutoff_index
            ]["Start_time"]
            product_types_max_start_time[product_type] = df_product_type[
                "Start_time"
            ].max()
        if not product_types_min_start_time:
            logger.info("No products finished during simulation, cannot perform warm up cutoff.")
            return df
        cut_off_time = min(product_types_min_start_time.values())
        for (
            product_type,
            product_type_latest_start,
        ) in product_types_max_start_time.items():
            if product_type_latest_start < cut_off_time:
                logger.info(
                    f"The simulation time is too short to perform a warm up cutoff for product type {product_type} because the latest start time is before the cut off time."
                )
                return df
        return df.loc[df["Start_time"] >= cut_off_time]

    @cached_property
    def dynamic_thoughput_time_KPIs(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of Dynamic Throughput KPI values for the throughput time of each finished product.

        Returns:
            List[performance_indicators.KPI]: List of Dynamic Throughput KPI values.
        """
        df_tp = self.df_throughput.copy()
        context = (
            performance_indicators.KPILevelEnum.SYSTEM,
            performance_indicators.KPILevelEnum.PRODUCT,
        )
        # Use itertuples() instead of iterrows() for better performance
        KPIs = [
            performance_indicators.DynamicThroughputTime(
                name=performance_indicators.KPIEnum.DYNAMIC_THROUGHPUT_TIME,
                context=context,
                value=row.Throughput_time,
                product=row.Product,
                product_type=row.Product_type,
                start_time=row.Start_time,
                end_time=row.End_time,
            )
            for row in df_tp.itertuples()
        ]
        return KPIs

    @cached_property
    def df_aggregated_throughput_time(self) -> pd.DataFrame:
        """
        Returns a data frame with the average throughput time for each product type.

        Returns:
            pd.DataFrame: Data frame with the average throughput time for each product type.
        """
        if self.warm_up_cutoff:
            df = self.df_throughput_with_warum_up_cutoff.copy()
        else:
            df = self.df_throughput.copy()
        df = df.groupby(by=["Product_type"])["Throughput_time"].mean()
        return df

    @cached_property
    def aggregated_throughput_time_KPIs(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of average Throughput Time KPI values for each product type.

        Returns:
            List[performance_indicators.KPI]: List of average Throughput Time KPI values.
        """
        ser = self.df_aggregated_throughput_time.copy()
        KPIs = []
        context = (
            performance_indicators.KPILevelEnum.SYSTEM,
            performance_indicators.KPILevelEnum.PRODUCT_TYPE,
        )
        for index, value in ser.items():
            KPIs.append(
                performance_indicators.ThroughputTime(
                    name=performance_indicators.KPIEnum.TRHOUGHPUT_TIME,
                    value=value,
                    context=context,
                    product_type=index,
                )
            )
        return KPIs

    @cached_property
    def df_aggregated_output_and_throughput(self) -> pd.DataFrame:
        """
        Returns a data frame with the average throughput and output for each product type.

        Returns:
            pd.DataFrame: Data frame with the average throughput and output for each product type.
        """
        if self.warm_up_cutoff:
            df = self.df_throughput_with_warum_up_cutoff.copy()
        else:
            df = self.df_throughput.copy()

        available_time = df["End_time"].max() - df["Start_time"].min()
        df_tp = df.groupby(by="Product_type")["Product"].count().to_frame()
        df_tp.rename(columns={"Product": "Output"}, inplace=True)
        df_tp["Throughput"] = df_tp["Output"] / available_time

        return df_tp

    @cached_property
    def throughput_and_output_KPIs(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of average Throughput and Output KPI values for each product type.

        Returns:
            List[performance_indicators.KPI]: List of average Throughput and Output KPI values.
        """
        df = self.df_aggregated_output_and_throughput.copy()
        context = (
            performance_indicators.KPILevelEnum.SYSTEM,
            performance_indicators.KPILevelEnum.PRODUCT_TYPE,
        )
        # Use itertuples() instead of iterrows() for better performance
        KPIs = []
        for row in df.itertuples():
            KPIs.append(
                performance_indicators.Throughput(
                    name=performance_indicators.KPIEnum.THROUGHPUT,
                    value=row.Throughput,
                    context=context,
                    product_type=row.Index,
                )
            )
            KPIs.append(
                performance_indicators.Output(
                    name=performance_indicators.KPIEnum.OUTPUT,
                    value=row.Output,
                    context=context,
                    product_type=row.Index,
                )
            )
        return KPIs

    @cached_property
    def df_aggregated_output(self) -> pd.DataFrame:
        """
        Returns a data frame with the total output for each product type.

        Returns:
            pd.DataFrame: Data frame with the total output for each product type.
        """
        if self.warm_up_cutoff:
            df = self.df_throughput_with_warum_up_cutoff.copy()
        else:
            df = self.df_throughput.copy()
        df_tp = df.groupby(by="Product_type")["Product"].count()

        return df_tp

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
        df = self.df_prepared.copy()

        # Vectorized increment calculation
        is_process_state = df["State_type"] == "Process State"
        is_start_activity = df["Activity"] == "start state"
        is_end_activity = df["Activity"] == "end state"
        
        base_condition = is_process_state & ~df["State Type"].isin([
            state.StateTypeEnum.setup, state.StateTypeEnum.breakdown, state.StateTypeEnum.charging
        ])
        
        df["Increment"] = np.select(
            [base_condition & is_start_activity, base_condition & is_end_activity],
            [1, -1],
            default=0
        )
        df["Used_Capacity"] = df.groupby("Resource")["Increment"].cumsum()

        # Pre-compute resource types and collect all example rows first
        # This avoids concatenating the entire dataframe N times in a loop
        df_resource_types = df[["Resource", "State Type"]].drop_duplicates()
        resource_types_dict = pd.Series(
            df_resource_types["State Type"].values,
            index=df_resource_types["Resource"].values,
        ).to_dict()
        
        # Vectorized approach to find the first row to duplicate as the starting entry (Time=0)
        # Sort first to ensure consistent first row selection
        df.sort_values(by=['Resource', 'Time'], inplace=True)
        # Get first row for each resource (excluding source/sink)
        first_row_mask = df['Resource'].shift() != df['Resource']
        first_rows = df.loc[first_row_mask].copy()
        # Filter out source/sink resources
        first_rows = first_rows[
            ~first_rows["Resource"].map(resource_types_dict).isin([
                state.StateTypeEnum.source,
                state.StateTypeEnum.sink,
            ])
        ]
        first_rows['Time'] = 0.0
        df = pd.concat([first_rows, df], ignore_index=True)

        # Use shift for next time calculation within groups
        df["next_Time"] = df.groupby("Resource")["Time"].shift(-1)
        df["next_Time"] = df["next_Time"].fillna(df["Time"].max())
        df["time_increment"] = df["next_Time"] - df["Time"]

        # Conditions for time types
        ssi = df["State_sorting_Index"]
        st = df["State Type"]
        uc = df["Used_Capacity"]

        conditions = [
            ((ssi == 5) & (uc == 0)) | (ssi == 3),
            (ssi == 6) | (ssi == 4) | ((ssi == 5) & (uc != 0)),
            (ssi == 6) & (st == state.StateTypeEnum.dependency),
            ((ssi == 7) | (ssi == 8)) & (st == state.StateTypeEnum.breakdown),
            (ssi == 8) & (st == state.StateTypeEnum.setup),
            (ssi == 8) & (st == state.StateTypeEnum.charging)
        ]
        choices = ["SB", "PR", "DP", "UD", "ST", "CR"]
        df["Time_type"] = np.select(conditions, choices, default=pd.NA)

        return df

    @cached_property
    def df_resource_states_buckets(self) -> pd.DataFrame:
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
        df = self.df_prepared.copy()
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

        # Vectorized bucket assignment - much faster than loop
        # Calculate bucket sizes per resource using vectorized operations
        resource_counts = df.groupby("Resource").size()
        num_bins = (1 + np.log2(resource_counts)).astype(int)
        bucket_sizes = (resource_counts / num_bins).astype(int).clip(lower=1)
        bucket_size_dict = bucket_sizes.to_dict()
        
        # Vectorized bucket assignment - use cumcount and map bucket sizes
        cumcounts = df.groupby("Resource").cumcount()
        bucket_sizes_mapped = df["Resource"].map(bucket_size_dict).fillna(1).astype(int)
        df["Bucket"] = (cumcounts // bucket_sizes_mapped).astype(int)

        df["Used_Capacity"] = df.groupby(["Resource", "Bucket"])["Increment"].cumsum()

        # Pre-compute resource types and example rows to avoid repeated concat operations
        df_resource_types = df[["Resource", "State Type"]].drop_duplicates()
        resource_types_dict = pd.Series(
            df_resource_types["State Type"].values,
            index=df_resource_types["Resource"].values,
        ).to_dict()
        
        # Collect all example rows first, then concatenate once
        example_rows = []
        for resource in df["Resource"].unique():
            if resource_types_dict[resource] in {
                state.StateTypeEnum.source,
                state.StateTypeEnum.sink,
            }:
                continue
            example_row = (
                df.loc[
                    (df["Resource"] == resource)
                    & (
                        ((df["State_sorting_Index"] == 5) & (df["Used_Capacity"] == 0))
                        | (df["State_sorting_Index"] == 3)
                    )
                ]
                .head(1)
            )
            if not example_row.empty:
                example_row = example_row.copy()
                example_row["Time"] = 0.0
                example_rows.append(example_row)
        
        # Concatenate all example rows at once if any exist
        if example_rows:
            example_df = pd.concat(example_rows, ignore_index=True)
            df = pd.concat([example_df, df], ignore_index=True)

        df["next_Time"] = df.groupby(["Resource", "Bucket"])["Time"].shift(-1)
        df["next_Time"] = df["next_Time"].fillna(
            df.groupby(["Resource", "Bucket"])["Time"].transform("max")
        )
        df["time_increment"] = df["next_Time"] - df["Time"]

        STANDBY_CONDITION = (
            (df["State_sorting_Index"] == 5) & (df["Used_Capacity"] == 0)
        ) | (df["State_sorting_Index"] == 3)
        PRODUCTIVE_CONDITION = (
            (df["State_sorting_Index"] == 6)
            | (df["State_sorting_Index"] == 4)
            | ((df["State_sorting_Index"] == 5) & df["Used_Capacity"] != 0)
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

        df.loc[STANDBY_CONDITION, "Time_type"] = "SB"
        df.loc[PRODUCTIVE_CONDITION, "Time_type"] = "PR"
        df.loc[DOWN_CONDITION, "Time_type"] = "UD"
        df.loc[SETUP_CONDITION, "Time_type"] = "ST"
        df.loc[CHARGING_CONDITION, "Time_type"] = "CR"

        return df

    @cached_property
    def df_aggregated_resource_bucket_states(self) -> pd.DataFrame:
        """
        Returns a data frame with the total time spent in each state of each resource.

        There are 5 different states a resource can spend its time:
            -SB: A resource is in standby state, could process but no product is available
            -PR: A resource is in productive state and performs a process
            -UD: A resource is in unscheduled downtime state due to a breakdown
            -ST: A resource is in setup state
            -CR: A resource is in charging state

        Returns:
            pd.DataFrame: Data frame with the total time spent in each state of each resource.
        """
        df = self.df_resource_states_buckets.copy()
        # TODO: locate is nan with function
        df = df.loc[df["Time_type"] != "na"]

        if self.warm_up_cutoff:
            df = df.loc[df["Time"] >= self.warm_up_cutoff_time]

        df_time_per_state = (
            df.groupby(["Resource", "Bucket", "Time_type"])
            .agg({"time_increment": "sum", "Time": "first"})
            .reset_index()
        )

        # Optimize: compute resource_time more efficiently
        df_resource_time = (
            df.groupby(["Resource", "Bucket"])["time_increment"]
            .sum()
            .reset_index(name="resource_time")
        )
        df_time_per_state = pd.merge(
            df_time_per_state, df_resource_time, on=["Resource", "Bucket"]
        )
        df_time_per_state["percentage"] = (
            df_time_per_state["time_increment"] / df_time_per_state["resource_time"]
        ) * 100

        return df_time_per_state

    @cached_property
    def df_resource_states_buckets_boxplot(self) -> pd.DataFrame:
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
        df_base = self.df_prepared.copy()
        positive_condition = (
            (df_base["State_type"] == "Process State")
            & (df_base["Activity"] == "start state")
            & (df_base["State Type"] != state.StateTypeEnum.setup)
            & (df_base["State Type"] != state.StateTypeEnum.breakdown)
            & (df_base["State Type"] != state.StateTypeEnum.charging)
        )
        negative_condition = (
            (df_base["State_type"] == "Process State")
            & (df_base["Activity"] == "end state")
            & (df_base["State Type"] != state.StateTypeEnum.setup)
            & (df_base["State Type"] != state.StateTypeEnum.breakdown)
            & (df_base["State Type"] != state.StateTypeEnum.charging)
        )

        df_base["Increment"] = 0
        df_base.loc[positive_condition, "Increment"] = 1
        df_base.loc[negative_condition, "Increment"] = -1

        # Pre-compute resource types dictionary once
        df_resource_types = df_base[["Resource", "State Type"]].drop_duplicates()
        resource_types_dict = pd.Series(
            df_resource_types["State Type"].values,
            index=df_resource_types["Resource"].values,
        ).to_dict()
        
        # Pre-compute example rows for each resource (only compute once)
        example_rows_dict = {}
        for resource in df_base["Resource"].unique():
            if resource_types_dict[resource] in {
                state.StateTypeEnum.source,
                state.StateTypeEnum.sink,
            }:
                continue
            example_row = (
                df_base.loc[
                    (df_base["Resource"] == resource)
                    & (
                        ((df_base["State_sorting_Index"] == 5) & (df_base["Increment"] == 0))
                        | (df_base["State_sorting_Index"] == 3)
                    )
                ]
                .head(1)
                .copy()
            )
            if not example_row.empty:
                example_row["Time"] = 0.0
                example_row["Increment"] = 0
                example_rows_dict[resource] = example_row

        bucket_sizes = [50, 100, 150]
        df_list = []
        
        # Pre-compute example rows once for all bucket sizes
        example_rows_list = []
        if example_rows_dict:
            for resource, example_row in example_rows_dict.items():
                example_row_base = example_row.copy()
                example_row_base["Used_Capacity"] = 0
                example_rows_list.append(example_row_base)

        # Pre-compute example_df once outside loop
        if example_rows_list:
            example_df_base = pd.concat(example_rows_list, ignore_index=True)
            example_df_base["Used_Capacity"] = 0
        
        for bucket_size in bucket_sizes:
            # Create a view first, copy only when necessary
            df = df_base.copy()
            
            # Vectorized bucket assignment
            df["Bucket"] = df.groupby("Resource").cumcount() // bucket_size
            df["Used_Capacity"] = df.groupby(["Resource", "Bucket"])[
                "Increment"
            ].cumsum()

            # Add example rows more efficiently - reuse pre-computed base
            if example_rows_list:
                example_df = example_df_base.copy()
                example_df["Bucket"] = 0
                df = pd.concat([example_df, df], ignore_index=True)

            # Vectorized time calculations - optimize groupby operations
            grouped = df.groupby(["Resource", "Bucket"])["Time"]
            df["next_Time"] = grouped.shift(-1)
            max_times = grouped.transform("max")
            df["next_Time"] = df["next_Time"].fillna(max_times)
            df["time_increment"] = df["next_Time"] - df["Time"]

            # Pre-extract columns for faster condition evaluation
            state_sort_idx = df["State_sorting_Index"].values
            used_cap = df["Used_Capacity"].values
            state_type = df["State Type"].values
            
            # Vectorized condition assignments using numpy
            standby_condition = ((state_sort_idx == 5) & (used_cap == 0)) | (state_sort_idx == 3)
            productive_condition = (
                (state_sort_idx == 6)
                | (state_sort_idx == 4)
                | ((state_sort_idx == 5) & (used_cap != 0))
            )
            downtime_condition = (
                ((state_sort_idx == 7) | (state_sort_idx == 8))
                & (state_type == state.StateTypeEnum.breakdown)
            )
            setup_condition = (state_sort_idx == 8) & (state_type == state.StateTypeEnum.setup)
            charging_condition = (state_sort_idx == 8) & (state_type == state.StateTypeEnum.charging)

            # Initialize Time_type column once
            df["Time_type"] = pd.NA
            df.loc[standby_condition, "Time_type"] = "SB"
            df.loc[productive_condition, "Time_type"] = "PR"
            df.loc[downtime_condition, "Time_type"] = "UD"
            df.loc[setup_condition, "Time_type"] = "ST"
            df.loc[charging_condition, "Time_type"] = "CR"

            df_list.append(df)

        # Concatenate all dataframes at once instead of in a loop
        return pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()

    @cached_property
    def df_aggregated_resource_bucket_states_boxplot(self) -> pd.DataFrame:
        """
        Returns a data frame with the total time spent in each state of each resource.

        There are 4 different states a resource can spend its time:
            -SB: A resource is in standby state, could process but no product is available
            -PR: A resource is in productive state and performs a process
            -UD: A resource is in unscheduled downtime state due to a breakdown
            -ST: A resource is in setup state

        Returns:
            pd.DataFrame: Data frame with the total time spent in each state of each resource.
        """
        df = self.df_resource_states_buckets_boxplot.copy()
        # Filter in one step
        mask = df["Time_type"] != "na"
        if self.warm_up_cutoff:
            mask = mask & (df["Time"] >= self.warm_up_cutoff_time)
        df = df.loc[mask]

        # Optimize: compute both aggregations in a single groupby operation where possible
        df_time_per_state = (
            df.groupby(["Resource", "Bucket", "Time_type"])
            .agg({"time_increment": "sum", "Time": "first"})
            .reset_index()
        )

        # Optimize: compute resource_time more efficiently using transform
        df_resource_time = (
            df.groupby(["Resource", "Bucket"])["time_increment"]
            .sum()
            .reset_index(name="resource_time")
        )
        
        # Use merge with explicit indicator for better performance
        df_time_per_state = pd.merge(
            df_time_per_state, df_resource_time, on=["Resource", "Bucket"], how="left"
        )
        # Vectorized percentage calculation
        df_time_per_state["percentage"] = (
            df_time_per_state["time_increment"] / df_time_per_state["resource_time"]
        ) * 100

        return df_time_per_state

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

        if self.warm_up_cutoff:
            df = df.loc[df["Time"] >= self.warm_up_cutoff_time]

        df_time_per_state = df.groupby(["Resource", "Time_type"])[
            "time_increment"
        ].sum()
        df_time_per_state = df_time_per_state.to_frame().reset_index()

        df_resource_time = (
            df_time_per_state.groupby(by="Resource")
            .sum(numeric_only=True)
            .reset_index()
        )
        df_resource_time.rename(
            columns={"time_increment": "resource_time"}, inplace=True
        )
        df_time_per_state = pd.merge(df_time_per_state, df_resource_time)
        df_time_per_state["percentage"] = (
            df_time_per_state["time_increment"] / df_time_per_state["resource_time"]
        ) * 100

        return df_time_per_state

    @cached_property
    def df_oee_production_system(self) -> pd.DataFrame:
        """
        Calculate the Overall Equipment Efficiency (OEE) of the production system.

        Returns:
            pd.DataFrame: A DataFrame containing the calculated OEE values for Availability, Performance, Quality, and OEE.
        """
        df_resource_states = self.df_aggregated_resource_states.copy()
        df_resource_states = df_resource_states.reset_index()
        average_kpis = df_resource_states.groupby("Time_type")["percentage"].mean()
        unplanned_downtime = average_kpis.get("UD", 0)
        availibility = (100 - unplanned_downtime) / 100
        # TODO: also calculate performance based on arrival rates, available time and output of the system
        # TODO: calculate scrap rate based on number of failed processes?

        # Create new DataFrame
        oee_df = pd.DataFrame(
            {
                "KPI": ["Availability", "Performance", "Quality", "OEE"],
                "Value": [availibility * 100, 1 * 100, 1 * 100, availibility * 100],
            }
        )
        oee_df["Value"] = oee_df["Value"].round(2)

        return oee_df

    @cached_property
    def df_production_flow_ratio(self) -> pd.DataFrame:
        """
        Calculates the production flow ratio for each product type.

        Returns:
            percentage_df (pd.DataFrame): DataFrame containing the production flow ratio for each product type.
                The DataFrame has the following columns:
                - Product_type: The type of the product.
                - Production: The percentage of time spent in production activities.
                - Transport: The percentage of time spent in transport activities.
                - Idle: The percentage of idle time.
        """
        df_finished_product = self.df_finished_product.copy()

        if self.warm_up_cutoff:
            df_finished_product = df_finished_product.loc[
                df_finished_product["Time"] >= self.warm_up_cutoff_time
            ]

        # Production
        filtered_df = df_finished_product[
            df_finished_product["State Type"] == "Production"
        ]
        df_production = filtered_df[
            ["Product", "Product_type", "State Type", "Activity", "Time"]
        ]
        grouped_production_df = (
            df_production.groupby(["Product", "Product_type", "Activity"])["Time"]
            .sum()
            .reset_index()
        )
        pivot_production_df = grouped_production_df.pivot(
            index=["Product", "Product_type"], columns="Activity", values="Time"
        )
        pivot_production_df = pivot_production_df.fillna(0)
        pivot_production_df["Production Time"] = (
            pivot_production_df["end state"]
            + pivot_production_df.get("end interrupt", 0)
            - pivot_production_df["start state"]
            - (
                pivot_production_df.get("end interrupt", 0)
                - pivot_production_df.get("start interrupt", 0)
            )
        )
        mean_production_time = (
            pivot_production_df.groupby("Product_type")["Production Time"]
            .mean()
            .reset_index()
        )

        # Transport
        df_transport = df_finished_product[
            df_finished_product["State Type"] == "Transport"
        ]
        df_transport = df_transport[
            ["Product", "Product_type", "State Type", "Activity", "Time"]
        ]
        df_transport = (
            df_transport.groupby(["Product", "Product_type", "Activity"])["Time"]
            .sum()
            .reset_index()
        )
        df_transport = df_transport.pivot(
            index=["Product", "Product_type"], columns="Activity", values="Time"
        )
        df_transport = df_transport.fillna(0)
        df_transport["Transport Time"] = (
            df_transport["end state"]
            + df_transport.get("end interrupt", 0)
            - df_transport["start state"]
            - (
                df_transport.get("end interrupt", 0)
                - df_transport.get("start interrupt", 0)
            )
        )
        mean_transport_time = (
            df_transport.groupby("Product_type")["Transport Time"].mean().reset_index()
        )

        df_aggregated_throughput_time_copy = self.df_aggregated_throughput_time.copy()

        merged_df = pd.merge(
            df_aggregated_throughput_time_copy,
            mean_production_time,
            on="Product_type",
            how="inner",
        )
        merged_df = pd.merge(
            merged_df, mean_transport_time, on="Product_type", how="inner"
        )
        merged_df["Idle Time"] = (
            merged_df["Throughput_time"]
            - merged_df["Production Time"]
            - merged_df["Transport Time"]
        )

        percentage_df = pd.DataFrame(
            {
                "Product_type": merged_df["Product_type"],
                "Production ": merged_df["Production Time"]
                / merged_df["Throughput_time"]
                * 100,
                "Transport ": merged_df["Transport Time"]
                / merged_df["Throughput_time"]
                * 100,
                "Idle ": merged_df["Idle Time"] / merged_df["Throughput_time"] * 100,
            }
        )

        return percentage_df

    @cached_property
    def machine_state_KPIS(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of KPI values for the time spent in each state of each resource.

        Returns:
            List[performance_indicators.KPI]: List of KPI values for the time spent in each state of each resource.
        """
        df = self.df_aggregated_resource_states.copy()
        context = (performance_indicators.KPILevelEnum.RESOURCE,)
        class_dict = {
            "SB": (
                performance_indicators.StandbyTime,
                performance_indicators.KPIEnum.STANDBY_TIME,
            ),
            "PR": (
                performance_indicators.ProductiveTime,
                performance_indicators.KPIEnum.PRODUCTIVE_TIME,
            ),
            "UD": (
                performance_indicators.UnscheduledDowntime,
                performance_indicators.KPIEnum.UNSCHEDULED_DOWNTIME,
            ),
            "ST": (
                performance_indicators.SetupTime,
                performance_indicators.KPIEnum.SETUP_TIME,
            ),
            "CR": (
                performance_indicators.ChargingTime,
                performance_indicators.KPIEnum.CHARGING_TIME,
            ),
            "DP": (
                performance_indicators.DependencyTime,
                performance_indicators.KPIEnum.DEPENDENCY_TIME,
            ),
        }
        # Use itertuples() instead of iterrows() for better performance
        KPIs = [
            class_dict[row.Time_type][0](
                name=class_dict[row.Time_type][1],
                value=row.percentage,
                context=context,
                resource=row.Resource,
            )
            for row in df.itertuples()
        ]
        return KPIs

    def get_WIP_KPI(self, df: pd.DataFrame) -> pd.DataFrame:
        CREATED_CONDITION = df["Activity"] == "created product"
        FINISHED_CONDITION = df["Activity"] == "finished product"

        df["WIP_Increment"] = 0
        df.loc[CREATED_CONDITION, "WIP_Increment"] = 1
        df.loc[FINISHED_CONDITION, "WIP_Increment"] = -1

        df = df.loc[
            df["WIP_Increment"] != 0
        ].copy()  # Remove rows where WIP_Increment is 0

        df["WIP"] = df["WIP_Increment"].cumsum()
        return df

    def get_primitive_WIP_KPI(self, df: pd.DataFrame) -> pd.DataFrame:
        primitive_types = self.get_primitive_types()
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
        df = self.get_primitive_WIP_KPI(self.df_prepared)
        return df

    @cached_property
    def df_primitive_WIP_per_primitive_type(self) -> pd.DataFrame:
        """
        Returns a data frame with the WIP over time for each primitive.

        Returns:
            pd.DataFrame: Data frame with the WIP over time for each primitive.
        """
        primitive_types = self.get_primitive_types()
        df_list = []
        
        # Use groupby instead of loop + combine_first for better performance
        for primitive_type in primitive_types:
            df_temp = self.df_prepared.loc[
                self.df_prepared["Primitive_type"] == primitive_type
            ].copy()
            if not df_temp.empty:
                df_temp = self.get_primitive_WIP_KPI(df_temp)
                df_list.append(df_temp)
        
        # Concatenate all primitive types at once
        return pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()

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

        if self.warm_up_cutoff:
            df = df.loc[df["Time"] >= self.warm_up_cutoff_time]

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
        df = self.df_resource_states.copy()
        return self.get_WIP_KPI(df)
        """
        Calculate the mean Work-in-Progress (WIP) per station.
        
        WIP tracking rules:
        - Create product: +1 at source resource
        - Finish product: -1 at sink resource
        - Transport (empty=False):
            - start state: -1 at Origin location, +1 at Transport resource
            - end state: -1 at Transport resource, +1 at Target location
        - Production:
            - start state: -1 at Origin location, +1 at Production resource
            - end state: -1 at Production resource, +1 at Target location
        - Transport (empty=True): No WIP changes

        Returns:
            pd.DataFrame: A DataFrame containing the mean WIP per station.
        """
        df = self.df_resource_states.copy()
        df["wip_increment"] = 0
        df["wip_resource"] = None

        # Rule 1: Create product -> +1 at source
        created_condition = df["Activity"] == state.StateEnum.created_product
        df.loc[created_condition, "wip_increment"] = 1
        df.loc[created_condition, "wip_resource"] = df.loc[created_condition, "Resource"]

        # Rule 2: Finish product -> -1 at sink
        finished_condition = df["Activity"] == state.StateEnum.finished_product
        df.loc[finished_condition, "wip_increment"] = -1
        df.loc[finished_condition, "wip_resource"] = df.loc[finished_condition, "Resource"]

        # Rule 3: Transport with empty=False
        transport_condition = df["State Type"] == "Transport"
        # Handle None/NaN values in Empty Transport column (occurs for non-transport activities)
        # We need explicit False check (not just "not True") to exclude None/NaN values
        non_empty_transport = transport_condition & df["Empty Transport"].fillna(True).eq(False)
        
        # Transport start state: -1 at Origin, +1 at Transport resource
        transport_start = non_empty_transport & (df["Activity"] == "start state")
        # Create two entries for each transport start
        transport_start_indices = df[transport_start].index
        for idx in transport_start_indices:
            # Decrement origin
            df.at[idx, "wip_increment"] = -1
            df.at[idx, "wip_resource"] = df.at[idx, "Origin location"]
            # We need to add a separate entry for incrementing transport resource
            # For now, we'll handle this by creating duplicate rows
        
        # Transport end state: -1 at Transport resource, +1 at Target
        transport_end = non_empty_transport & (df["Activity"] == "end state")
        transport_end_indices = df[transport_end].index
        for idx in transport_end_indices:
            # Increment target
            df.at[idx, "wip_increment"] = 1
            df.at[idx, "wip_resource"] = df.at[idx, "Target location"]

        # Rule 4: Production
        # NOTE: The Origin/Target in Production events represent QUEUE CONFIGURATION, not product movement!
        # The product stays at the input queue (or resource) during production.
        # Actual product movement is handled by Transport events.
        # Therefore, we DON'T create WIP changes based on Production Origin/Target columns.
        production_condition = df["State Type"] == "Production"
        
        # Production start state: Product enters the production resource
        production_start = production_condition & (df["Activity"] == "start state")
        production_start_indices = df[production_start].index
        for idx in production_start_indices:
            # Mark as no automatic WIP change - will be handled by additional rows below
            df.at[idx, "wip_increment"] = 1
            df.at[idx, "wip_resource"] = df.at[idx, "Target location"]
        
        # Production end state: Product leaves the production resource
        production_end = production_condition & (df["Activity"] == "end state")
        production_end_indices = df[production_end].index
        for idx in production_end_indices:
            # Mark as no automatic WIP change - will be handled by additional rows below
            df.at[idx, "wip_increment"] = -1
            df.at[idx, "wip_resource"] = df.at[idx, "Origin location"]

        # Handle interrupts (product returned to origin)
        # We need explicit False check (not just "not True") to exclude None/NaN values
        interrupted_condition = df["Empty Transport"].fillna(True).eq(False) & (
            df["Activity"] == "end interrupt"
        )
        df.loc[interrupted_condition, "wip_increment"] = 1
        df.loc[interrupted_condition, "wip_resource"] = df.loc[
            interrupted_condition, "Origin location"
        ]

        # Now we need to add the increment entries for transport resources
        # Create additional rows for transport resource increments (start state)
        # transport_start_df = df[transport_start].copy()
        # transport_start_df["wip_increment"] = 1
        # transport_start_df["wip_resource"] = transport_start_df["Resource"]
        
        # # Create additional rows for transport resource decrements (end state)
        # transport_end_df = df[transport_end].copy()
        # transport_end_df["wip_increment"] = -1
        # transport_end_df["wip_resource"] = transport_end_df["Resource"]
        
        # NOTE: We do NOT create additional rows for production because:
        # - Products stay at the input queue during production (based on data analysis)
        # - Next transport always picks up from input queue, not output queue
        # - Production Origin/Target represent queue configuration, not product location
        # - Therefore, WIP doesn't move during production events
        
        # Combine all dataframes
        # df = pd.concat([df, transport_start_df, transport_end_df], ignore_index=False)
        
        # Sort by time to maintain chronological order
        df = df.sort_values(by=["Time", "wip_resource"])

        # Filter out rows with no wip_resource
        df = df[df["wip_resource"].notna()]
        
        # Calculate cumulative WIP per resource
        df["wip"] = df.groupby(by="wip_resource")["wip_increment"].cumsum()

        # Exclude sinks and sources from the final results
        df_temp = df[["State", "State Type"]].drop_duplicates()
        sinks = df_temp.loc[
            df_temp["State Type"] == state.StateTypeEnum.sink, "State"
        ].unique()
        df = df.loc[~df["wip_resource"].isin(sinks)]
        sources = df_temp.loc[
            df_temp["State Type"] == state.StateTypeEnum.source, "State"
        ].unique()
        df = df.loc[~df["wip_resource"].isin(sources)]
        
        # Exclude network nodes (routing points like n_src, n101, n102, etc.)
        # Network nodes typically start with 'n' followed by '_' or digits
        # Also exclude input port nodes (ip_glue6, ip_align, etc.)
        network_node_mask = df["wip_resource"].str.match(r'^(n[_\d]|ip_)', na=False)
        df = df.loc[~network_node_mask]

        if self.warm_up_cutoff:
            df = df.loc[df["Time"] >= self.warm_up_cutoff_time]

        # Calculate mean WIP per station
        df_mean_wip_per_station = df.groupby("wip_resource")["wip"].mean().reset_index()
        df_mean_wip_per_station.rename(columns={"wip": "mean_wip"}, inplace=True)
        df_mean_wip_per_station.rename(
            columns={"wip_resource": "Resource"}, inplace=True
        )

        return df_mean_wip_per_station

    def get_primitive_types(self) -> List[str]:
        """
        Returns a list of primitive types of the resources.

        Returns:
            List[str]: List of primitive types of the resources.
        """
        return self.df_prepared["Primitive_type"].dropna().unique().tolist()

    @cached_property
    def df_WIP_per_product(self) -> pd.DataFrame:
        """
        Returns a data frame with the WIP over time for each product type.

        Returns:
            pd.DataFrame: Data frame with the WIP over time for each product type.
        """
        # Avoid unnecessary copy - get_df_with_product_entries already returns a copy
        df = self.get_df_with_product_entries(self.df_resource_states)
        df = df.reset_index(drop=True)
        
        # Use groupby instead of loop + combine_first for better performance
        df_list = []
        for product_type, group in df.groupby("Product_type", sort=False):
            if pd.isna(product_type):  # Skip NaN more efficiently
                continue
            # get_WIP_KPI modifies the dataframe in place, so we need a copy
            df_temp = self.get_WIP_KPI(group.copy())
            df_list.append(df_temp)
        
        # Concatenate all product types at once
        return pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()

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
        
        Args:
            df: DataFrame with resource states
            
        Returns:
            pd.DataFrame: DataFrame with WIP tracking per resource
        """
        # Filter events that change WIP: created, finished, loading, unloading
        wip_events = df[
            df["Activity"].isin(["created product", "finished product", "end state"]) &
            df["State Type"].isin([
                state.StateTypeEnum.source, state.StateTypeEnum.sink,
                state.StateTypeEnum.loading, state.StateTypeEnum.unloading
            ]) &
            (df["Time"] != 0)
        ].copy()

        # --- Create arrays to hold data for new WIP entries ---
        times = []
        resources = []
        increments = []

        # Rule 1 & 2: Created (+1) and Finished (-1)
        created_mask = wip_events["Activity"] == "created product"
        finished_mask = wip_events["Activity"] == "finished product"
        
        times.extend(wip_events.loc[created_mask, "Time"].values)
        resources.extend(wip_events.loc[created_mask, "Resource"].values)
        increments.extend(np.ones(created_mask.sum(), dtype=int))
        
        times.extend(wip_events.loc[finished_mask, "Time"].values)
        resources.extend(wip_events.loc[finished_mask, "Resource"].values)
        increments.extend(-np.ones(finished_mask.sum(), dtype=int))

        # Rule 3: End loading -> +1 at resource, -1 at Origin
        loading_mask = (wip_events["State Type"] == state.StateTypeEnum.loading) & (wip_events["Activity"] == "end state")
        loading_df = wip_events.loc[loading_mask]
        
        # +1 at resource
        times.extend(loading_df["Time"].values)
        resources.extend(loading_df["Resource"].values)
        increments.extend(np.ones(len(loading_df), dtype=int))
        
        # -1 at origin location
        times.extend(loading_df["Time"].values)
        resources.extend(loading_df["Origin location"].values)
        increments.extend(-np.ones(len(loading_df), dtype=int))
        
        # Rule 4: End unloading -> -1 at resource, +1 at Target
        unloading_mask = (wip_events["State Type"] == state.StateTypeEnum.unloading) & (wip_events["Activity"] == "end state")
        unloading_df = wip_events.loc[unloading_mask]
        
        # -1 at resource
        times.extend(unloading_df["Time"].values)
        resources.extend(unloading_df["Resource"].values)
        increments.extend(-np.ones(len(unloading_df), dtype=int))
        
        # +1 at target location
        times.extend(unloading_df["Time"].values)
        resources.extend(unloading_df["Target location"].values)
        increments.extend(np.ones(len(unloading_df), dtype=int))

        # --- Create a single DataFrame from the collected data ---
        if not times:
            return pd.DataFrame(columns=["Time", "WIP_resource", "WIP_Increment", "WIP"])
            
        wip_df = pd.DataFrame({
            "Time": times,
            "WIP_resource": resources,
            "WIP_Increment": increments
        })
        
        wip_df.dropna(subset=["WIP_resource"], inplace=True)
        
        # Sort by time, then by increment to ensure decrements are processed before increments at the same timestamp
        wip_df.sort_values(by=["Time", "WIP_Increment"], ascending=[True, False], inplace=True)
        
        # Calculate cumulative WIP per resource
        wip_df["WIP"] = wip_df.groupby("WIP_resource")["WIP_Increment"].cumsum()
        
        return wip_df

    @cached_property
    def df_WIP_per_resource(self) -> pd.DataFrame:
        """
        Returns a data frame with the WIP over time for each resource.

        Returns:
            pd.DataFrame: Data frame with the WIP over time for each resource.
        """
        df = self.df_resource_states.copy()
        # df = self.get_df_with_product_entries(df).copy()
        df = self.get_WIP_per_resource_KPI(df)

        return df

    @cached_property
    def dynamic_WIP_per_resource_KPIs(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of Dynamic WIP KPI values for the WIP over time for each product type.

        Returns:
            List[performance_indicators.KPI]: List of Dynamic WIP KPI values.
        """
        # Filter first without copying the entire dataframe
        mask = self.df_WIP_per_resource["WIP_Increment"] != 0
        df = self.df_WIP_per_resource.loc[mask].copy()

        # Vectorized next_Time calculation
        df["next_Time"] = df.groupby(by="WIP_resource")["Time"].shift(-1)
        df["next_Time"] = df["next_Time"].fillna(df["Time"])
        
        # Use itertuples() instead of iterrows() for better performance
        # Pre-compute context outside loop
        context = (
            performance_indicators.KPILevelEnum.RESOURCE,
            performance_indicators.KPILevelEnum.ALL_PRODUCTS,
        )
        
        # Extract arrays once for faster access
        wip_values = df["WIP"].values
        resources = df["WIP_resource"].values
        times = df["Time"].values
        next_times = df["next_Time"].values
        
        KPIs = [
            performance_indicators.DynamicWIP(
                name=performance_indicators.KPIEnum.DYNAMIC_WIP,
                value=wip_values[i],
                context=context,
                product_type="Total",
                resource=resources[i],
                start_time=times[i],
                end_time=next_times[i],
            )
            for i in range(len(df))
        ]
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

        df["next_Time"] = df.groupby(by="Product_type")["Time"].shift(-1)
        df["next_Time"] = df["next_Time"].fillna(df["Time"])
        
        # Pre-compute contexts outside loop
        context_total = (
            performance_indicators.KPILevelEnum.SYSTEM,
            performance_indicators.KPILevelEnum.ALL_PRODUCTS,
        )
        context_product = (
            performance_indicators.KPILevelEnum.SYSTEM,
            performance_indicators.KPILevelEnum.PRODUCT_TYPE,
        )
        
        # Extract arrays once for faster access
        wip_values = df["WIP"].values
        product_types = df["Product_type"].values
        times = df["Time"].values
        next_times = df["next_Time"].values
        is_total = (product_types == "Total")
        
        KPIs = [
            performance_indicators.DynamicWIP(
                name=performance_indicators.KPIEnum.DYNAMIC_WIP,
                value=wip_values[i],
                context=context_total if is_total[i] else context_product,
                product_type=product_types[i],
                start_time=times[i],
                end_time=next_times[i],
            )
            for i in range(len(df))
        ]
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
        primitive_types = self.get_primitive_types()
        df_total_wip = df_total_wip.loc[
            ~df_total_wip["Product_type"].isin(primitive_types)
        ]
        df_total_wip["Product_type"] = "Total"
        df = pd.concat([df, df_total_wip])

        if self.warm_up_cutoff:
            df = df.loc[df["Time"] >= self.warm_up_cutoff_time]

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

    def get_aggregated_data(self) -> dict:
        """
        Returns a dictionary with the aggregated data for the simulation results.

        Returns:
            dict: Dictionary with the aggregated data for throughput, wip, throughput time and resource states.
        """
        data = {}
        data["Throughput"] = (
            self.df_aggregated_output_and_throughput.copy().reset_index().to_dict()
        )
        data["WIP"] = self.df_aggregated_WIP.copy().reset_index().to_dict()
        data["Throughput time"] = (
            self.df_aggregated_throughput_time.copy().reset_index().to_dict()
        )
        data["Resource states"] = (
            self.df_aggregated_resource_states.copy()
            .set_index(["Resource", "Time_type"])
            .reset_index()
            .to_dict()
        )

        return data

    def get_aggregated_throughput_time_data(self) -> List[float]:
        """
        Returns a list of the aggregated throughput time data.

        Returns:
            List[float]: List of the aggregated throughput time data ordered alphabetically by product type.
        """
        return list(self.df_aggregated_throughput_time.values)

    def get_aggregated_throughput_data(self) -> List[float]:
        """
        Returns a list of the aggregated throughput data.

        Returns:
            List[float]: List of the aggregated throughput data ordered alphabetically by product type.
        """
        return list(self.df_aggregated_output.values)

    def get_aggregated_wip_data(self) -> List[float]:
        """
        Returns a list of the aggregated WIP data.

        Returns:
            List[float]: List of the aggregated WIP data ordered alphabetically by product type.
        """
        s = self.df_aggregated_WIP.copy()
        s = s.drop(labels=["Total"])
        return list(s.values)
