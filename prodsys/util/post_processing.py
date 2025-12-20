from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

from prodsys.models.production_system_data import ProductionSystemData
from prodsys.models.resource_data import SystemResourceData
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
    production_system_data: Optional[ProductionSystemData] = field(default=None)
    df_raw: pd.DataFrame = field(default=None)
    time_range: float = field(default=None)
    warm_up_cutoff: bool = field(default=False)
    cut_off_method: Optional[Literal["mser5", "threshold_stabilization", "static_ratio"]] = field(
        default=None
    )
    _system_resource_mapping: Optional[dict] = field(default=None, init=False, repr=False)
    _sink_input_queues: Optional[set] = field(default=None, init=False, repr=False)
    _source_output_queues: Optional[set] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        if self.filepath:
            self.read_df_from_csv()
    
    def set_production_system_data(self, production_system_data: ProductionSystemData):
        """
        Set the production system data after initialization.
        
        This data is used to determine system resource / subresources mapping 
        and sink / source IDs. It is optional and only needed for advanced features.
        
        Args:
            production_system_data (ProductionSystemData): The production system data to set.
        """
        self.production_system_data = production_system_data
        # Clear manually set mappings when production_system_data is set
        self._system_resource_mapping = None
        self._sink_input_queues = None
        self._source_output_queues = None
        # Clear cached properties that depend on production_system_data
        if hasattr(self, '__dict__'):
            # Clear cached properties that might depend on production_system_data
            cached_props = ['df_resource_states']
            for prop in cached_props:
                if prop in self.__dict__:
                    delattr(self, prop)
    
    def set_system_resource_mapping(self, mapping: dict):
        """
        Set the system resource mapping directly.
        
        This mapping is used to aggregate subresource states into system resource states.
        The mapping should be a dictionary where keys are system resource IDs and values 
        are lists of subresource IDs.
        
        Args:
            mapping (dict): Mapping from system resource ID to list of subresource IDs.
        """
        self._system_resource_mapping = mapping
        # Clear cached properties that depend on system resource mapping
        if hasattr(self, '__dict__'):
            cached_props = ['df_resource_states']
            for prop in cached_props:
                if prop in self.__dict__:
                    delattr(self, prop)
    
    def set_sink_source_queue_names(self, sink_input_queues: set, source_output_queues: set):
        """
        Set sink input queue names and source output queue names directly.
        
        These queue names are used to exclude sink/source queues from resource states calculation.
        
        Args:
            sink_input_queues (set): Set of sink input queue names to exclude.
            source_output_queues (set): Set of source output queue names to exclude.
        """
        self._sink_input_queues = sink_input_queues
        self._source_output_queues = source_output_queues
        # Clear cached properties that depend on sink/source queue names
        if hasattr(self, '__dict__'):
            cached_props = ['df_resource_states']
            for prop in cached_props:
                if prop in self.__dict__:
                    delattr(self, prop)

    def _get_system_resource_mapping(self) -> dict:
        """
        Get mapping of system resource IDs to their subresource IDs.
        
        Returns:
            dict: Mapping from system resource ID to list of subresource IDs.
                  Returns empty dict if neither production_system_data nor manual mapping is set.
        """
        # Check if manual mapping is set
        if self._system_resource_mapping is not None:
            return self._system_resource_mapping
        
        # Otherwise, derive from production_system_data if available
        if self.production_system_data is None:
            return {}
        
        system_resource_mapping = {}
        for resource_data in self.production_system_data.resource_data:
            if isinstance(resource_data, SystemResourceData):
                system_resource_mapping[resource_data.ID] = resource_data.subresource_ids
        
        return system_resource_mapping
    
    def _get_sink_source_queue_names(self) -> tuple[set, set]:
        """
        Get names of sink input queues and source output queues.
        
        Returns:
            tuple[set, set]: (sink_input_queues, source_output_queues)
        """
        # Check if manual queue names are set
        if self._sink_input_queues is not None and self._source_output_queues is not None:
            return self._sink_input_queues, self._source_output_queues
        
        sink_input_queues = set()
        source_output_queues = set()
        
        # Otherwise, derive from production_system_data if available
        if self.production_system_data is None:
            return sink_input_queues, source_output_queues
        
        # Get sink input queues
        for sink_data in self.production_system_data.sink_data:
            if sink_data.ports:
                sink_input_queues.update(sink_data.ports)
        
        # Get source output queues
        for source_data in self.production_system_data.source_data:
            if source_data.ports:
                source_output_queues.update(source_data.ports)
        
        return sink_input_queues, source_output_queues

    def read_df_from_csv(self, filepath_input: str = None):
        """
        Reads the simulation results from a csv file.

        Args:
            filepath_input (str, optional): Path to the csv file with the simulation results. Defaults to None and the at instantiation provided filepath is used.
        """
        if filepath_input:
            self.filepath = filepath_input
        self.df_raw = pd.read_csv(self.filepath)
        self.df_raw.drop(columns=["Unnamed: 0"], inplace=True)

    def get_conditions_for_interface_state(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        This function returns a data frame with the conditions wether a row in the data frame belongs to a interface state or not.
        Hereby, an interface state belongs to a state, where a resource does not perform a process, i.e. either setup, breakdown or creation (source) or finish (sink) of products.

        Args:
            df (pd.DataFrame): Data frame with the simulation results.

        Returns:
            pd.DataFrame: Data frame with the conditions wether a row in the data frame belongs to a process state or not.
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
                state.StateTypeEnum.assembly,
                state.StateTypeEnum.non_scheduled,
            ]
        )

    def get_conditions_for_process_state(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        This function returns a data frame with the conditions wether a row in the data frame belongs to a process state or not.
        Hereby, a process state belongs to a state, where a resource performs a process, i.e. either production or transport.

        Args:
            df (pd.DataFrame): Data frame with the simulation results.

        Returns:
            pd.DataFrame: Data frame with the conditions wether a row in the data frame belongs to a process state or not.
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
        df["Combined_activity"] = df["State"] + " " + df["Activity"]
        df["Product_type"] = df["Product"].str.rsplit("_", n=1).str[0]
        if "Primitive" not in df.columns:
            df["Primitive"] = None
        df["Primitive_type"] = df["Primitive"].str.rsplit("_", n=1).str[0]
        df.loc[
            self.get_conditions_for_interface_state(df),
            "State_type",
        ] = "Interface State"
        df.loc[
            self.get_conditions_for_process_state(df),
            "State_type",
        ] = "Process State"

        # TODO: remove this, if processbreakdown is added
        df = df.loc[df["State Type"] != state.StateTypeEnum.process_breakdown]

        COLUMNS = ["State_type", "Activity", "State_sorting_Index"]
        STATE_SORTING_INDEX = {
            "0": ["Interface State", "finished product", 1],
            "1": ["Interface State", "created product", 2],
            "2": ["Interface State", "consumed product", 2],
            "3": ["Interface State", "end state", 3],
            "4": ["Process State", "end interrupt", 4],
            "5": ["Process State", "end state", 5],
            "6": ["Process State", "start state", 6],
            "7": ["Process State", "start interrupt", 7],
            "8": ["Interface State", "start state", 8],
        }

        df_unique = pd.DataFrame.from_dict(
            data=STATE_SORTING_INDEX, orient="index", columns=COLUMNS
        )

        df = pd.merge(df, df_unique)
        return df

    @cached_property
    def df_finished_product(self) -> pd.DataFrame:
        """
        Returns a prepared data frame (df_prepared) with only finished products.

        Returns:
            pd.DataFrame: Data frame with only finished products.
        """
        df = self.df_prepared.copy()
        finished_product = df.loc[
            (df["Product"].notna()) & (df["Activity"] == "finished product")
        ]["Product"].unique()
        finished_product = pd.Series(finished_product, name="Product")
        df_finished_product = pd.merge(df, finished_product)
        return df_finished_product

    def get_df_with_product_entries(self, input_df: pd.DataFrame) -> pd.DataFrame:
        df = input_df.copy()
        primitive_types = self.get_primitive_types()
        product_types = df.loc[
            (df["Product_type"].notna())
            & (df["Product_type"] != "")
            & (~df["Product_type"].isin(primitive_types))
        ]["Product_type"].unique()
        product_types = pd.Series(product_types, name="Product_type")
        df_product_info = pd.merge(df, product_types)
        return df_product_info

    @cached_property
    def df_throughput(self) -> pd.DataFrame:
        """
        Returns a data frame with the throughput time for each finished product.

        Returns:
            pd.DataFrame: Data frame with the throughput time for each finished product.
        """
        df = self.df_prepared.copy()
        df_finished_product = self.df_finished_product.copy()
        min = df_finished_product.groupby(by="Product")["Time"].min()
        min.name = "Start_time"
        max = df_finished_product.groupby(by="Product")["Time"].max()
        max.name = "End_time"
        tpt = max - min
        tpt.name = "Throughput_time"

        df_tpt = pd.merge(
            df[["Product_type", "Product"]].drop_duplicates(),
            tpt.to_frame().reset_index(),
        )
        df_tpt = pd.merge(df_tpt, min.to_frame().reset_index())
        df_tpt = pd.merge(df_tpt, max.to_frame().reset_index())

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
        KPIs = []
        context = (
            performance_indicators.KPILevelEnum.SYSTEM,
            performance_indicators.KPILevelEnum.PRODUCT,
        )
        for index, values in df_tp.iterrows():
            KPIs.append(
                performance_indicators.DynamicThroughputTime(
                    name=performance_indicators.KPIEnum.DYNAMIC_THROUGHPUT_TIME,
                    context=context,
                    value=values["Throughput_time"],
                    product=values["Product"],
                    product_type=values["Product_type"],
                    start_time=values["Start_time"],
                    end_time=values["End_time"],
                )
            )
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
        KPIs = []
        context = (
            performance_indicators.KPILevelEnum.SYSTEM,
            performance_indicators.KPILevelEnum.PRODUCT_TYPE,
        )
        for index, values in df.iterrows():
            KPIs.append(
                performance_indicators.Throughput(
                    name=performance_indicators.KPIEnum.THROUGHPUT,
                    value=values["Throughput"],
                    context=context,
                    product_type=index,
                )
            )
            KPIs.append(
                performance_indicators.Output(
                    name=performance_indicators.KPIEnum.OUTPUT,
                    value=values["Output"],
                    context=context,
                    product_type=index,
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
        # Get the global simulation end time - use time_range if provided, otherwise use max Time
        if self.time_range is not None:
            simulation_end_time = self.time_range
        else:
            simulation_end_time = df["Time"].max()
        
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
                    
                    # Match breakdown start and end events by Resource and State
                    for idx in needs_matching.index:
                        resource = df.loc[idx, "Resource"]
                        state_id = df.loc[idx, "State"]
                        # Find the corresponding end event
                        matching_end = breakdown_ends[
                            (breakdown_ends["Resource"] == resource) 
                            & (breakdown_ends["State"] == state_id)
                            & (breakdown_ends["Time"] >= df.loc[idx, "Time"])
                        ]
                        if len(matching_end) > 0:
                            # Use the earliest matching end event
                            end_time = matching_end["Time"].min()
                            df.loc[idx, "next_Time"] = end_time
        
        df["time_increment"] = df["next_Time"] - df["Time"]

        # Initialize Time_type column
        df["Time_type"] = "na"

        STANDBY_CONDITION = (
            (df["State_sorting_Index"] == 5) & (df["Used_Capacity"] == 0)
        ) | (
            (df["State_sorting_Index"] == 3) 
            & (df["State Type"] != state.StateTypeEnum.breakdown)
            & (df["State Type"] != state.StateTypeEnum.setup)
            & (df["State Type"] != state.StateTypeEnum.charging)
        )
        PRODUCTIVE_CONDITION = (
            (
                (df["State_sorting_Index"] == 6)
                | (df["State_sorting_Index"] == 4)
                | ((df["State_sorting_Index"] == 5) & (df["Used_Capacity"] != 0))
            )
            & (df["State Type"] != state.StateTypeEnum.dependency)
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
            (df["State_sorting_Index"] == 7) | (df["State_sorting_Index"] == 8)
        ) & (df["State Type"] == state.StateTypeEnum.non_scheduled)

        # Apply conditions in order of specificity (most specific first)
        # DEPENDENCY is most specific (requires State_sorting_Index == 6 AND State Type == dependency)
        df.loc[DEPENDENCY_CONDITION, "Time_type"] = "DP"
        # Then apply other specific conditions
        df.loc[NON_SCHEDULED_CONDITION, "Time_type"] = "NS"  # Non Scheduled
        df.loc[DOWN_CONDITION, "Time_type"] = "UD"
        df.loc[SETUP_CONDITION, "Time_type"] = "ST"
        df.loc[CHARGING_CONDITION, "Time_type"] = "CR"
        # Then apply general conditions
        df.loc[STANDBY_CONDITION, "Time_type"] = "SB"
        df.loc[PRODUCTIVE_CONDITION, "Time_type"] = "PR"
        
        # Fallback: if any events still don't have a Time_type, assign based on Used_Capacity
        # Events with Used_Capacity != 0 should be PR, others should be SB
        unassigned = df["Time_type"] == "na"
        df.loc[unassigned & (df["Used_Capacity"] != 0), "Time_type"] = "PR"
        df.loc[unassigned & (df["Used_Capacity"] == 0), "Time_type"] = "SB"

        # Add system resource states by aggregating subresource states
        system_resource_mapping = self._get_system_resource_mapping()
        if system_resource_mapping:
            # Use df_prepared to get raw productive process events, not the processed df_resource_states
            df_prepared_for_system = self.df_prepared.copy()
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
                    self.get_conditions_for_interface_state(df_prepared_for_system),
                    "State_type",
                ] = "Interface State"
                df_prepared_for_system.loc[
                    self.get_conditions_for_process_state(df_prepared_for_system),
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
        # Get the global simulation end time - use time_range if provided, otherwise use max Time
        if self.time_range is not None:
            simulation_end_time = self.time_range
        else:
            simulation_end_time = df["Time"].max()
        
        # Exclude loading and unloading states from resource states calculation
        df = df.loc[
            (df["State Type"] != state.StateTypeEnum.loading)
            & (df["State Type"] != state.StateTypeEnum.unloading)
        ]
        
        # Identify source and sink resources and exclude all their events
        source_sink_resources = df.loc[
            (df["State Type"] == state.StateTypeEnum.source)
            | (df["State Type"] == state.StateTypeEnum.sink),
            "Resource"
        ].unique()
        
        # Also exclude sink input queues and source output queues by name pattern
        # These are queue resources associated with sinks and sources
        queue_resources_to_exclude = df.loc[
            df["Resource"].str.contains("Sink.*input.*queue|source.*output.*queue", case=False, na=False, regex=True),
            "Resource"
        ].unique()
        
        # Combine all resources to exclude
        resources_to_exclude = set(source_sink_resources) | set(queue_resources_to_exclude)
        
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

        # Insert Time=0.0 start events BEFORE calculating Buckets and Used_Capacity
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

        df["Bucket"] = 0
        for resource, group in df.groupby("Resource"):
            n = len(group)
            num_bins = int(np.ceil(1 + np.log2(n)))
            bucket_size = max(1, n // num_bins)
            df.loc[group.index, "Bucket"] = (
                group.groupby("Resource").cumcount() // bucket_size
            )

        df["Used_Capacity"] = df.groupby(["Resource", "Bucket"])["Increment"].cumsum()

        # Use the global simulation end time (all resources should end at this time)
        
        # Insert end events at simulation end time for each resource/bucket
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
            
            # Insert end event for each bucket of this resource
            for bucket in resource_df["Bucket"].unique():
                bucket_df = resource_df[resource_df["Bucket"] == bucket]
                if bucket_df.empty:
                    continue
                
                # Check if there's already an event at simulation_end_time
                events_at_end = bucket_df[bucket_df["Time"] == simulation_end_time]
                
                # Only insert if there's no event at simulation_end_time
                if len(events_at_end) == 0:
                    # Use the last event as template to maintain the status of the last event
                    example_row = bucket_df.iloc[-1:].copy()
                    
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
            # Sort by Resource, Bucket, and Time to ensure proper order
            df = df.sort_values(by=["Resource", "Bucket", "Time"]).reset_index(drop=True)
            # Recalculate Used_Capacity after inserting end events
            df["Used_Capacity"] = df.groupby(["Resource", "Bucket"])["Increment"].cumsum()

        df["next_Time"] = df.groupby(["Resource", "Bucket"])["Time"].shift(-1)
        # For the last event of each resource/bucket, next_Time should equal its own Time
        df["next_Time"] = df["next_Time"].fillna(df["Time"])
        df["time_increment"] = df["next_Time"] - df["Time"]

        STANDBY_CONDITION = (
            (df["State_sorting_Index"] == 5) & (df["Used_Capacity"] == 0)
        ) | (
            (df["State_sorting_Index"] == 3) 
            & (df["State Type"] != state.StateTypeEnum.breakdown)
        )
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
        NON_SCHEDULED_CONDITION = (
            (df["State_sorting_Index"] == 7) | (df["State_sorting_Index"] == 8)
        ) & (df["State Type"] == state.StateTypeEnum.non_scheduled)

        df.loc[STANDBY_CONDITION, "Time_type"] = "SB"
        df.loc[PRODUCTIVE_CONDITION, "Time_type"] = "PR"
        df.loc[NON_SCHEDULED_CONDITION, "Time_type"] = "NS"  # Non Scheduled
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

        df_resource_time = (
            df.groupby(["Resource", "Bucket"])
            .agg(
                {
                    "time_increment": "sum",
                }
            )
            .reset_index()
        )
        df_resource_time.rename(
            columns={"time_increment": "resource_time"}, inplace=True
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

        bucket_sizes = [50, 100, 150]
        df_all = pd.DataFrame()

        for bucket_size in bucket_sizes:
            df["Bucket"] = df.groupby("Resource").cumcount() // bucket_size
            df["Used_Capacity"] = df.groupby(["Resource", "Bucket"])[
                "Increment"
            ].cumsum()

            df_resource_types = df[["Resource", "State Type"]].drop_duplicates().copy()
            resource_types_dict = pd.Series(
                df_resource_types["State Type"].values,
                index=df_resource_types["Resource"].values,
            ).to_dict()
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
                            (
                                (df["State_sorting_Index"] == 5)
                                & (df["Used_Capacity"] == 0)
                            )
                            | (df["State_sorting_Index"] == 3)
                        )
                    ]
                    .copy()
                    .head(1)
                )
                example_row["Time"] = 0.0
                df = pd.concat([example_row, df]).reset_index(drop=True)

            df["next_Time"] = df.groupby(["Resource", "Bucket"])["Time"].shift(-1)
            df["next_Time"] = df["next_Time"].fillna(
                df.groupby(["Resource", "Bucket"])["Time"].transform("max")
            )
            df["time_increment"] = df["next_Time"] - df["Time"]

            standby_condition = (
                (df["State_sorting_Index"] == 5) & (df["Used_Capacity"] == 0)
            ) | (
                (df["State_sorting_Index"] == 3) 
                & (df["State Type"] != state.StateTypeEnum.breakdown)
                & (df["State Type"] != state.StateTypeEnum.setup)
                & (df["State Type"] != state.StateTypeEnum.charging)
            )
            productive_condition = (
                (df["State_sorting_Index"] == 6)
                | (df["State_sorting_Index"] == 4)
                | ((df["State_sorting_Index"] == 5) & df["Used_Capacity"] != 0)
            )
            downtime_condition = (
                (df["State_sorting_Index"] == 7) | (df["State_sorting_Index"] == 8)
            ) & (df["State Type"] == state.StateTypeEnum.breakdown)
            setup_condition = ((df["State_sorting_Index"] == 8)) & (
                df["State Type"] == state.StateTypeEnum.setup
            )
            charging_condition = ((df["State_sorting_Index"] == 8)) & (
                df["State Type"] == state.StateTypeEnum.charging
            )
            non_scheduled_condition = (
                (df["State_sorting_Index"] == 7) | (df["State_sorting_Index"] == 8)
            ) & (df["State Type"] == state.StateTypeEnum.non_scheduled)

            df.loc[standby_condition, "Time_type"] = "SB"
            df.loc[productive_condition, "Time_type"] = "PR"
            df.loc[non_scheduled_condition, "Time_type"] = "NS"  # Non Scheduled
            df.loc[downtime_condition, "Time_type"] = "UD"
            df.loc[setup_condition, "Time_type"] = "ST"
            df.loc[charging_condition, "Time_type"] = "CR"

            df_all = pd.concat([df_all, df])

        return df_all

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
        df = df.loc[df["Time_type"] != "na"]

        if self.warm_up_cutoff:
            df = df.loc[df["Time"] >= self.warm_up_cutoff_time]

        df_time_per_state = (
            df.groupby(["Resource", "Bucket", "Time_type"])
            .agg({"time_increment": "sum", "Time": "first"})
            .reset_index()
        )

        df_resource_time = (
            df.groupby(["Resource", "Bucket"])
            .agg(
                {
                    "time_increment": "sum",
                }
            )
            .reset_index()
        )
        df_resource_time.rename(
            columns={"time_increment": "resource_time"}, inplace=True
        )
        df_time_per_state = pd.merge(
            df_time_per_state, df_resource_time, on=["Resource", "Bucket"]
        )
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

        # Calculate resource_time as the total time span for each resource
        # This should be from 0 to simulation_end_time for all resources
        df_resource_time = df.groupby(by="Resource")["time_increment"].sum().reset_index()
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
            df_resource_states = self.df_aggregated_resource_states.copy()
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
        if self.production_system_data is None:
            logger.warning(
                "production_system_data not available. Cannot calculate expected output. "
                "Performance will default to 100%."
            )
            performance = 1.0
        else:
            # Get simulation time range
            if self.time_range is not None:
                total_time = self.time_range
            else:
                total_time = self.get_total_simulation_time()
            
            # Calculate expected output from sources
            from prodsys.factories.time_model_factory import TimeModelFactory
            
            time_model_factory = TimeModelFactory()
            time_model_factory.create_time_models(self.production_system_data)
            
            expected_output = 0.0
            
            # Check for order data or schedule first
            # Note: order_data might not be a direct attribute, check if it exists
            order_data = getattr(self.production_system_data, 'order_data', None)
            if order_data and len(order_data) > 0:
                # If order data exists, sum up the quantities from all orders
                from prodsys.models.order_data import OrderData
                expected_output = sum(
                    sum(product.quantity for product in order.ordered_products)
                    for order in order_data
                    if isinstance(order, OrderData)
                )
            elif hasattr(self.production_system_data, 'schedule') and self.production_system_data.schedule:
                # If schedule exists, count scheduled products within simulation time
                schedule_products = [
                    event for event in self.production_system_data.schedule
                    if hasattr(event, 'time') and event.time <= total_time
                ]
                expected_output = len(schedule_products)
            else:
                # Calculate expected output from source arrival time models
                for source_data in self.production_system_data.source_data:
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
            df_output = self.df_aggregated_output_and_throughput.copy()
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
        df_output = self.df_aggregated_output_and_throughput.copy()
        if len(df_output) > 0:
            total_units_produced = df_output["Output"].sum()
        else:
            total_units_produced = 0
        
        if total_units_produced > 0:
            # Get scrap data to calculate good units
            df_scrap = self.df_scrap_per_product_type.copy()
            if len(df_scrap) > 0:
                # Calculate weighted average scrap rate based on output
                df_output_for_quality = self.df_aggregated_output.copy()
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
        if self.production_system_data is None:
            logger.warning(
                "production_system_data not available. Cannot calculate resource-level OEE."
            )
            return pd.DataFrame(columns=["Resource", "Availability", "Performance", "Quality", "OEE"])
        
        # Get resource states
        df_resource_states = self.df_aggregated_resource_states.copy()
        df_resource_states = df_resource_states.reset_index()
        
        # Get time model factory
        from prodsys.factories.time_model_factory import TimeModelFactory
        time_model_factory = TimeModelFactory()
        time_model_factory.create_time_models(self.production_system_data)
        
        # Get processes per resource
        resource_to_processes = {}
        for resource_data in self.production_system_data.resource_data:
            if hasattr(resource_data, 'process_ids'):
                resource_to_processes[resource_data.ID] = resource_data.process_ids
        
        # Calculate OEE per resource
        oee_results = []
        
        for resource in df_resource_states["Resource"].unique():
            df_resource = df_resource_states[df_resource_states["Resource"] == resource]
            
            # Get resource time
            resource_time = df_resource["resource_time"].iloc[0]
            
            # Calculate time per state (time_increment is already in absolute time)
            time_per_state = df_resource.set_index("Time_type")["time_increment"]
            
            # Availability: Operating Time / Planned Production Time
            # Get productive time (PR) - time actually producing parts
            productive_time = time_per_state.get("PR", 0)
            
            # Get dependency time (DP) - time waiting for dependencies
            dependency_time = time_per_state.get("DP", 0)

            standby_time = time_per_state.get("SB", 0)
            
            # Operating Time = PR + DP (time available for production)
            # Note: SB (standby) is an availability loss, not part of operating time
            operating_time = productive_time + dependency_time + standby_time
            
            # Get non-scheduled time (NS) - excluded from planned production time
            non_scheduled_time = time_per_state.get("NS", 0)
            
            # Planned Production Time = Resource Time - Non Scheduled Time
            # This represents all time where production is expected (excluding breaks, maintenance, etc.)
            planned_production_time = resource_time - non_scheduled_time
            
            # Availability losses (UD, ST, SB, CR) are in Planned Production Time but reduce Operating Time
            if planned_production_time > 0:
                availability = operating_time / planned_production_time
            else:
                availability = 0.0
            
            # Performance: (Ideal Cycle Time × Total Units Produced) / Operating Time
            # Get actual process end events for this resource (both production and transport) to count process occurrences
            df_prepared = self.df_prepared.copy()
            resource_process_ends = df_prepared[
                (df_prepared["Resource"] == resource) &
                (df_prepared["State Type"].isin([state.StateTypeEnum.production, state.StateTypeEnum.transport])) &
                (df_prepared["Activity"] == "end state")
            ]
            total_units_produced = len(resource_process_ends)
            
            # Get resource capacity
            resource_capacity = 1  # Default capacity
            process_capacities = {}  # Map process_id -> capacity
            for resource_data in self.production_system_data.resource_data:
                if resource_data.ID == resource:
                    resource_capacity = resource_data.capacity if hasattr(resource_data, 'capacity') else 1
                    # Get process-specific capacities if available
                    if hasattr(resource_data, 'process_capacities') and resource_data.process_capacities:
                        for i, process_id in enumerate(resource_data.process_ids):
                            if i < len(resource_data.process_capacities):
                                process_capacities[process_id] = resource_data.process_capacities[i]
                    break
            
            if total_units_produced > 0 and operating_time > 0:
                # Count how many times each process was performed
                process_counts = resource_process_ends["State"].value_counts()
                
                # Calculate weighted average ideal cycle time based on process counts and capacities
                weighted_cycle_time_sum = 0.0
                total_count = 0
                
                for process_id, count in process_counts.items():
                    # Find the process data for this process ID
                    for process_data in self.production_system_data.process_data:
                        if process_data.ID == process_id:
                            # Consider both production and transport processes
                            if hasattr(process_data, 'type'):
                                from prodsys.models.processes_data import ProcessTypeEnum
                                # Skip non-production and non-transport processes
                                if process_data.type not in [ProcessTypeEnum.ProductionProcesses, ProcessTypeEnum.TransportProcesses]:
                                    continue
                            
                            if hasattr(process_data, 'time_model_id'):
                                try:
                                    time_model = time_model_factory.get_time_model(process_data.time_model_id)
                                    # Skip distance models for resource-level OEE (they need origin/target)
                                    from prodsys.simulation.time_model import DistanceTimeModel
                                    if isinstance(time_model, DistanceTimeModel):
                                        # For transport with distance models, we can't get expected time without origin/target
                                        # This will fall through to the PR/Operating Time fallback
                                        break
                                    
                                    expected_time = time_model.get_expected_time()
                                    if expected_time > 0:
                                        # Get process-specific capacity, or use resource capacity as fallback
                                        process_capacity = process_capacities.get(process_id, resource_capacity)
                                        
                                        # Effective cycle time = cycle time / capacity
                                        # If capacity is 2, the resource can process 2 items simultaneously,
                                        # so the effective cycle time is halved
                                        effective_cycle_time = expected_time / process_capacity if process_capacity > 0 else expected_time
                                        
                                        # Weight by count: if P1 performed 1000x and P2 performed 2000x,
                                        # P2's cycle time gets 2x weight
                                        weighted_cycle_time_sum += effective_cycle_time * count
                                        total_count += count
                                except (ValueError, TypeError):
                                    pass
                            break
                
                if total_count > 0:
                    # Calculate weighted average effective ideal cycle time (already adjusted for capacity)
                    avg_ideal_cycle_time = weighted_cycle_time_sum / total_count
                    
                    # Performance = (Effective Ideal Cycle Time × Total Units Produced) / Operating Time
                    # Operating Time includes PR (productive) and DP (dependency)
                    # Effective cycle time already accounts for resource capacity
                    performance = (avg_ideal_cycle_time * total_units_produced) / operating_time
                else:
                    # No valid cycle times found - use fallback: PR / Operating Time
                    # This measures what fraction of operating time was actually productive
                    if operating_time > 0:
                        performance = productive_time / operating_time
                        logger.info(
                            f"No valid ideal cycle times found for resource {resource}. "
                            f"Performance calculated as PR/Operating Time ratio: {performance:.2%}"
                        )
                    else:
                        performance = 1.0
                        logger.info(
                            f"No valid ideal cycle times and no operating time for resource {resource}. "
                            "Performance will default to 100%."
                        )
            else:
                if total_units_produced == 0:
                    performance = 0.0
                else:
                    performance = 1.0
                    logger.info(
                        f"No operating time or units produced for resource {resource}. "
                        "Performance will default to 100%."
                    )
            
            # Quality - get scrap rate for this resource
            df_scrap_resource = self.df_scrap_per_resource.copy()
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
        KPIs = []
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
        for index, values in df.iterrows():
            KPIs.append(
                class_dict[values["Time_type"]][0](
                    name=class_dict[values["Time_type"]][1],
                    value=values["percentage"],
                    context=context,
                    resource=values["Resource"],
                )
            )
        return KPIs

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
        df = pd.DataFrame()
        primitive_types = self.get_primitive_types()
        for primitive_type in primitive_types:
            df_temp = self.df_prepared.loc[
                self.df_prepared["Primitive_type"] == primitive_type
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
        # Use df_prepared because it contains created/finished product activities
        # that are needed for WIP calculation
        df = self.df_prepared.copy()
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
        # Use df_prepared because it contains created/finished product activities
        # that are needed for WIP calculation
        df_base = self.df_prepared.copy()
        df_base = self.get_df_with_product_entries(df_base).copy()
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
        df = self.df_prepared.copy()
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

    @cached_property
    def df_scrap_per_product_type(self) -> pd.DataFrame:
        """
        Returns a data frame with the scrap rate for each product type.
        Scrap rate is calculated as: (Number of failed processes) / (Total number of processes) * 100
        
        Returns:
            pd.DataFrame: Data frame with scrap rate per product type. Columns: Product_type, Scrap_count, Total_count, Scrap_rate
        """
        df = self.df_prepared.copy()
        
        # Filter for production process end states only (where process_ok is relevant)
        production_end_condition = (
            (df["State Type"] == state.StateTypeEnum.production)
            & (df["Activity"] == "end state")
            & (df["Product"].notna())
        )
        df_production = df[production_end_condition].copy()
        
        if len(df_production) == 0:
            # Return empty dataframe with expected structure
            return pd.DataFrame(columns=["Product_type", "Scrap_count", "Total_count", "Scrap_rate"])
        
        # Get product types (filter out primitives)
        primitive_types = self.get_primitive_types()
        df_production = df_production[
            ~df_production["Product_type"].isin(primitive_types)
        ]
        
        if len(df_production) == 0:
            return pd.DataFrame(columns=["Product_type", "Scrap_count", "Total_count", "Scrap_rate"])
        
        # Handle process_ok column - default to True if not present or NaN
        if "process_ok" not in df_production.columns:
            df_production["process_ok"] = True
        else:
            # Convert to boolean, handling NaN values without triggering downcast warning
            # Use mask-based assignment to avoid fillna downcast warning
            mask = df_production["process_ok"].isna()
            df_production.loc[mask, "process_ok"] = True
            df_production["process_ok"] = df_production["process_ok"].astype(bool)
        
        # Count failed processes (process_ok == False) per product type
        df_failed = df_production[~df_production["process_ok"]].groupby("Product_type").size().reset_index(name="Scrap_count")
        
        # Count total processes per product type
        df_total = df_production.groupby("Product_type").size().reset_index(name="Total_count")
        
        # Merge and calculate scrap rate
        df_scrap = pd.merge(df_total, df_failed, on="Product_type", how="left")
        df_scrap["Scrap_count"] = df_scrap["Scrap_count"].fillna(0).astype(int)
        df_scrap["Scrap_rate"] = (df_scrap["Scrap_count"] / df_scrap["Total_count"] * 100).round(2)
        
        return df_scrap[["Product_type", "Scrap_count", "Total_count", "Scrap_rate"]]

    @cached_property
    def df_scrap_per_resource(self) -> pd.DataFrame:
        """
        Returns a data frame with the scrap rate for each resource.
        Scrap rate is calculated as: (Number of failed processes) / (Total number of processes) * 100
        
        Returns:
            pd.DataFrame: Data frame with scrap rate per resource. Columns: Resource, Scrap_count, Total_count, Scrap_rate
        """
        df = self.df_prepared.copy()
        
        # Filter for production process end states only (where process_ok is relevant)
        production_end_condition = (
            (df["State Type"] == state.StateTypeEnum.production)
            & (df["Activity"] == "end state")
            & (df["Resource"].notna())
        )
        df_production = df[production_end_condition].copy()
        
        if len(df_production) == 0:
            # Return empty dataframe with expected structure
            return pd.DataFrame(columns=["Resource", "Scrap_count", "Total_count", "Scrap_rate"])
        
        # Exclude sink and source resources
        sink_source_resources = df.loc[
            (df["State Type"] == state.StateTypeEnum.source)
            | (df["State Type"] == state.StateTypeEnum.sink),
            "Resource"
        ].unique()
        df_production = df_production[~df_production["Resource"].isin(sink_source_resources)]
        
        if len(df_production) == 0:
            return pd.DataFrame(columns=["Resource", "Scrap_count", "Total_count", "Scrap_rate"])
        
        # Handle process_ok column - default to True if not present or NaN
        if "process_ok" not in df_production.columns:
            df_production["process_ok"] = True
        else:
            # Convert to boolean, handling NaN values without triggering downcast warning
            # Use mask-based assignment to avoid fillna downcast warning
            mask = df_production["process_ok"].isna()
            df_production.loc[mask, "process_ok"] = True
            df_production["process_ok"] = df_production["process_ok"].astype(bool)
        
        # Count failed processes (process_ok == False) per resource
        df_failed = df_production[~df_production["process_ok"]].groupby("Resource").size().reset_index(name="Scrap_count")
        
        # Count total processes per resource
        df_total = df_production.groupby("Resource").size().reset_index(name="Total_count")
        
        # Merge and calculate scrap rate
        df_scrap = pd.merge(df_total, df_failed, on="Resource", how="left")
        df_scrap["Scrap_count"] = df_scrap["Scrap_count"].fillna(0).astype(int)
        df_scrap["Scrap_rate"] = (df_scrap["Scrap_count"] / df_scrap["Total_count"] * 100).round(2)
        
        return df_scrap[["Resource", "Scrap_count", "Total_count", "Scrap_rate"]]
