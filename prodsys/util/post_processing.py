from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

from prodsys.models.production_system_data import ProductionSystemData
from prodsys.models.resource_data import SystemResourceData
from prodsys.simulation import state
from prodsys.models import performance_indicators

from typing import List, Literal, Optional

import pandas as pd

import logging

# Import analytics modules
from prodsys.analytics.base import AnalyticsContext
from prodsys.analytics.data_preparation import DataPreparation
from prodsys.analytics.throughput import ThroughputAnalytics
from prodsys.analytics.scrap import ScrapAnalytics
from prodsys.analytics.resource_states import ResourceStatesAnalytics
from prodsys.analytics.wip import WIPAnalytics
from prodsys.analytics.oee import OEEAnalytics
from prodsys.analytics.production_flow import ProductionFlowAnalytics
from prodsys.analytics.kpi_generator import KPIGenerator

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
    _analytics_context: Optional[AnalyticsContext] = field(default=None, init=False, repr=False)
    _data_prep: Optional[DataPreparation] = field(default=None, init=False, repr=False)
    _throughput_analytics: Optional[ThroughputAnalytics] = field(default=None, init=False, repr=False)
    _scrap_analytics: Optional[ScrapAnalytics] = field(default=None, init=False, repr=False)
    _resource_states_analytics: Optional[ResourceStatesAnalytics] = field(default=None, init=False, repr=False)
    _wip_analytics: Optional[WIPAnalytics] = field(default=None, init=False, repr=False)
    _oee_analytics: Optional[OEEAnalytics] = field(default=None, init=False, repr=False)
    _production_flow_analytics: Optional[ProductionFlowAnalytics] = field(default=None, init=False, repr=False)
    _kpi_generator: Optional[KPIGenerator] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        if self.filepath:
            self.read_df_from_csv()
        self._initialize_analytics()
    
    def _initialize_analytics(self):
        """Initialize analytics modules."""
        if self.df_raw is not None:
            self._analytics_context = AnalyticsContext(
                df_raw=self.df_raw,
                production_system_data=self.production_system_data,
                time_range=self.time_range,
                warm_up_cutoff=self.warm_up_cutoff,
                cut_off_method=self.cut_off_method,
                _system_resource_mapping=self._system_resource_mapping,
                _sink_input_queues=self._sink_input_queues,
                _source_output_queues=self._source_output_queues,
            )
            self._data_prep = DataPreparation(self._analytics_context)
            self._throughput_analytics = ThroughputAnalytics(self._analytics_context, self._data_prep)
            self._scrap_analytics = ScrapAnalytics(self._analytics_context, self._data_prep)
            self._resource_states_analytics = ResourceStatesAnalytics(
                self._analytics_context, self._data_prep, self._throughput_analytics
            )
            self._wip_analytics = WIPAnalytics(
                self._analytics_context, self._data_prep, self._throughput_analytics
            )
            self._oee_analytics = OEEAnalytics(
                self._analytics_context,
                self._data_prep,
                self._throughput_analytics,
                self._scrap_analytics,
                self._resource_states_analytics,
            )
            self._production_flow_analytics = ProductionFlowAnalytics(
                self._analytics_context,
                self._data_prep,
                self._throughput_analytics,
            )
            self._kpi_generator = KPIGenerator(
                self._analytics_context,
                self._data_prep,
                self._throughput_analytics,
                self._resource_states_analytics,
            )
    
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
        # Update analytics context if it exists
        if self._analytics_context is not None:
            self._analytics_context.set_production_system_data(production_system_data)
        # Reinitialize analytics to update context with new production_system_data
        self._initialize_analytics()
    
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
        # Update analytics context if it exists
        if self._analytics_context is not None:
            self._analytics_context.set_system_resource_mapping(mapping)
        # Reinitialize analytics to update context with new system resource mapping
        self._initialize_analytics()
    
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
        # Update analytics context if it exists
        if self._analytics_context is not None:
            self._analytics_context.set_sink_source_queue_names(sink_input_queues, source_output_queues)
        # Reinitialize analytics to update context with new sink/source queue names
        self._initialize_analytics()

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
        # Reinitialize analytics with new data
        self._initialize_analytics()

    def get_conditions_for_interface_state(self, df: pd.DataFrame) -> pd.Series:
        """Delegate to base module."""
        from prodsys.analytics.base import get_conditions_for_interface_state
        return get_conditions_for_interface_state(df)

    def get_conditions_for_process_state(self, df: pd.DataFrame) -> pd.Series:
        """Delegate to base module."""
        from prodsys.analytics.base import get_conditions_for_process_state
        return get_conditions_for_process_state(df)

    def get_total_simulation_time(self) -> float:
        """Delegate to AnalyticsContext."""
        if self._analytics_context is None:
            self._initialize_analytics()
        return self._analytics_context.get_total_simulation_time()

    @cached_property
    def df_prepared(self) -> pd.DataFrame:
        """Delegate to DataPreparation module."""
        if self._data_prep is None:
            self._initialize_analytics()
        return self._data_prep.df_prepared

    @cached_property
    def df_finished_product(self) -> pd.DataFrame:
        """Delegate to DataPreparation module."""
        if self._data_prep is None:
            self._initialize_analytics()
        return self._data_prep.df_finished_product

    def get_df_with_product_entries(self, input_df: pd.DataFrame) -> pd.DataFrame:
        """Delegate to DataPreparation module."""
        if self._data_prep is None:
            self._initialize_analytics()
        return self._data_prep.get_df_with_product_entries(input_df)
    
    def get_primitive_types(self) -> List[str]:
        """Delegate to DataPreparation module."""
        if self._data_prep is None:
            self._initialize_analytics()
        return self._data_prep.get_primitive_types()

    @cached_property
    def df_throughput(self) -> pd.DataFrame:
        """Delegate to ThroughputAnalytics module."""
        if self._throughput_analytics is None:
            self._initialize_analytics()
        return self._throughput_analytics.df_throughput

    @cached_property
    def warm_up_cutoff_time(self) -> float:
        """Delegate to ThroughputAnalytics module."""
        if self._throughput_analytics is None:
            self._initialize_analytics()
        return self._throughput_analytics.warm_up_cutoff_time

    @cached_property
    def df_throughput_with_warum_up_cutoff(self) -> pd.DataFrame:
        """Delegate to ThroughputAnalytics module."""
        if self._throughput_analytics is None:
            self._initialize_analytics()
        return self._throughput_analytics.df_throughput_with_warum_up_cutoff

    @cached_property
    def dynamic_thoughput_time_KPIs(self) -> List[performance_indicators.KPI]:
        """Delegate to KPIGenerator module."""
        if self._kpi_generator is None:
            self._initialize_analytics()
        return self._kpi_generator.dynamic_thoughput_time_KPIs

    @cached_property
    def df_aggregated_throughput_time(self) -> pd.DataFrame:
        """Delegate to ThroughputAnalytics module."""
        if self._throughput_analytics is None:
            self._initialize_analytics()
        return self._throughput_analytics.df_aggregated_throughput_time

    @cached_property
    def aggregated_throughput_time_KPIs(self) -> List[performance_indicators.KPI]:
        """Delegate to KPIGenerator module."""
        if self._kpi_generator is None:
            self._initialize_analytics()
        return self._kpi_generator.aggregated_throughput_time_KPIs

    @cached_property
    def df_aggregated_output_and_throughput(self) -> pd.DataFrame:
        """Delegate to ThroughputAnalytics module."""
        if self._throughput_analytics is None:
            self._initialize_analytics()
        return self._throughput_analytics.df_aggregated_output_and_throughput

    @cached_property
    def throughput_and_output_KPIs(self) -> List[performance_indicators.KPI]:
        """Delegate to KPIGenerator module."""
        if self._kpi_generator is None:
            self._initialize_analytics()
        return self._kpi_generator.throughput_and_output_KPIs

    @cached_property
    def df_aggregated_output(self) -> pd.DataFrame:
        """Delegate to ThroughputAnalytics module."""
        if self._throughput_analytics is None:
            self._initialize_analytics()
        return self._throughput_analytics.df_aggregated_output

    @cached_property
    def df_resource_states(self) -> pd.DataFrame:
        """Delegate to ResourceStatesAnalytics module."""
        if self._resource_states_analytics is None:
            self._initialize_analytics()
        return self._resource_states_analytics.df_resource_states
    
    def get_resource_states_by_interval(self, interval_minutes: float) -> pd.DataFrame:
        """Delegate to ResourceStatesAnalytics module."""
        if self._resource_states_analytics is None:
            self._initialize_analytics()
        return self._resource_states_analytics.get_resource_states_by_interval(interval_minutes)
    
    def get_aggregated_resource_states_by_interval(self, interval_minutes: float) -> pd.DataFrame:
        """Delegate to ResourceStatesAnalytics module."""
        if self._resource_states_analytics is None:
            self._initialize_analytics()
        return self._resource_states_analytics.get_aggregated_resource_states_by_interval(interval_minutes)
    
    def get_oee_per_resource_by_interval(self, interval_minutes: float) -> pd.DataFrame:
        """Delegate to OEEAnalytics module."""
        if self._oee_analytics is None:
            self._initialize_analytics()
        return self._oee_analytics.get_oee_per_resource_by_interval(interval_minutes)

    @cached_property
    def df_aggregated_resource_states(self) -> pd.DataFrame:
        """Delegate to ResourceStatesAnalytics module."""
        if self._resource_states_analytics is None:
            self._initialize_analytics()
        return self._resource_states_analytics.df_aggregated_resource_states

    @cached_property
    def df_oee_production_system(self) -> pd.DataFrame:
        """Delegate to OEEAnalytics module."""
        if self._oee_analytics is None:
            self._initialize_analytics()
        return self._oee_analytics.df_oee_production_system

    @cached_property
    def df_oee_per_resource(self) -> pd.DataFrame:
        """Delegate to OEEAnalytics module."""
        if self._oee_analytics is None:
            self._initialize_analytics()
        return self._oee_analytics.df_oee_per_resource

    @cached_property
    def df_production_flow_ratio(self) -> pd.DataFrame:
        """Delegate to ProductionFlowAnalytics module."""
        if self._production_flow_analytics is None:
            self._initialize_analytics()
        return self._production_flow_analytics.df_production_flow_ratio

    @cached_property
    def machine_state_KPIS(self) -> List[performance_indicators.KPI]:
        """Delegate to KPIGenerator module."""
        if self._kpi_generator is None:
            self._initialize_analytics()
        return self._kpi_generator.machine_state_KPIS

    def get_WIP_KPI(self, df: pd.DataFrame) -> pd.DataFrame:
        """Delegate to WIPAnalytics module."""
        if self._wip_analytics is None:
            self._initialize_analytics()
        return self._wip_analytics.get_WIP_KPI(df)

    def get_primitive_WIP_KPI(self, df: pd.DataFrame) -> pd.DataFrame:
        """Delegate to WIPAnalytics module."""
        if self._wip_analytics is None:
            self._initialize_analytics()
        return self._wip_analytics.get_primitive_WIP_KPI(df)

    @cached_property
    def df_primitive_WIP(self) -> pd.DataFrame:
        """Delegate to WIPAnalytics module."""
        if self._wip_analytics is None:
            self._initialize_analytics()
        return self._wip_analytics.df_primitive_WIP

    @cached_property
    def df_primitive_WIP_per_primitive_type(self) -> pd.DataFrame:
        """Delegate to WIPAnalytics module."""
        if self._wip_analytics is None:
            self._initialize_analytics()
        return self._wip_analytics.df_primitive_WIP_per_primitive_type

    @cached_property
    def df_aggregated_primitive_WIP(self) -> pd.DataFrame:
        """Delegate to WIPAnalytics module."""
        if self._wip_analytics is None:
            self._initialize_analytics()
        return self._wip_analytics.df_aggregated_primitive_WIP

    @cached_property
    def df_WIP(self) -> pd.DataFrame:
        """Delegate to WIPAnalytics module."""
        if self._wip_analytics is None:
            self._initialize_analytics()
        return self._wip_analytics.df_WIP


    @cached_property
    def df_WIP_per_product(self) -> pd.DataFrame:
        """Delegate to WIPAnalytics module."""
        if self._wip_analytics is None:
            self._initialize_analytics()
        return self._wip_analytics.df_WIP_per_product

    def get_WIP_per_resource_KPI(self, df: pd.DataFrame) -> pd.DataFrame:
        """Delegate to WIPAnalytics module."""
        if self._wip_analytics is None:
            self._initialize_analytics()
        return self._wip_analytics.get_WIP_per_resource_KPI(df)

    @cached_property
    def df_WIP_per_resource(self) -> pd.DataFrame:
        """Delegate to WIPAnalytics module."""
        if self._wip_analytics is None:
            self._initialize_analytics()
        return self._wip_analytics.df_WIP_per_resource

    @cached_property
    def dynamic_WIP_per_resource_KPIs(self) -> List[performance_indicators.KPI]:
        """Delegate to WIPAnalytics module."""
        if self._wip_analytics is None:
            self._initialize_analytics()
        return self._wip_analytics.dynamic_WIP_per_resource_KPIs

    @cached_property
    def dynamic_system_WIP_KPIs(self) -> List[performance_indicators.KPI]:
        """Delegate to WIPAnalytics module."""
        if self._wip_analytics is None:
            self._initialize_analytics()
        return self._wip_analytics.dynamic_system_WIP_KPIs

    @cached_property
    def df_aggregated_WIP(self) -> pd.DataFrame:
        """Delegate to WIPAnalytics module."""
        if self._wip_analytics is None:
            self._initialize_analytics()
        return self._wip_analytics.df_aggregated_WIP

    @cached_property
    def WIP_KPIs(self) -> List[performance_indicators.KPI]:
        """Delegate to WIPAnalytics module."""
        if self._wip_analytics is None:
            self._initialize_analytics()
        return self._wip_analytics.WIP_KPIs

    @cached_property
    def primitive_WIP_KPIs(self) -> List[performance_indicators.KPI]:
        """Delegate to WIPAnalytics module."""
        if self._wip_analytics is None:
            self._initialize_analytics()
        return self._wip_analytics.primitive_WIP_KPIs

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
        """Delegate to ScrapAnalytics module."""
        if self._scrap_analytics is None:
            self._initialize_analytics()
        return self._scrap_analytics.df_scrap_per_product_type
    
    @cached_property
    def df_scrap_per_product_type_original(self) -> pd.DataFrame:
        """
        Original implementation (kept for reference).
        """
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
        """Delegate to ScrapAnalytics module."""
        if self._scrap_analytics is None:
            self._initialize_analytics()
        return self._scrap_analytics.df_scrap_per_resource
    
    @cached_property
    def df_scrap_per_resource_original(self) -> pd.DataFrame:
        """
        Original implementation (kept for reference).
        """
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
