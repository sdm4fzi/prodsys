"""
Base classes and shared utilities for analytics calculations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal

import pandas as pd

from prodsys.models.production_system_data import ProductionSystemData
from prodsys.models.resource_data import SystemResourceData
from prodsys.simulation import state

import logging

logger = logging.getLogger(__name__)


@dataclass
class AnalyticsContext:
    """
    Context object that holds shared data and configuration for analytics calculations.
    
    This class provides a centralized way to access:
    - Raw simulation data
    - Production system data
    - Configuration (warm-up cutoff, time range, etc.)
    - System resource mappings
    - Sink/source queue names
    """
    
    df_raw: pd.DataFrame
    production_system_data: Optional[ProductionSystemData] = None
    time_range: Optional[float] = None
    warm_up_cutoff: bool = False
    cut_off_method: Optional[Literal["mser5", "threshold_stabilization", "static_ratio"]] = None
    _system_resource_mapping: Optional[dict] = None
    _sink_input_queues: Optional[set] = None
    _source_output_queues: Optional[set] = None
    
    def set_production_system_data(self, production_system_data: ProductionSystemData):
        """Set the production system data and clear manual mappings."""
        self.production_system_data = production_system_data
        self._system_resource_mapping = None
        self._sink_input_queues = None
        self._source_output_queues = None
    
    def set_system_resource_mapping(self, mapping: dict):
        """Set the system resource mapping directly."""
        self._system_resource_mapping = mapping
    
    def set_sink_source_queue_names(self, sink_input_queues: set, source_output_queues: set):
        """Set sink input queue names and source output queue names directly."""
        self._sink_input_queues = sink_input_queues
        self._source_output_queues = source_output_queues
    
    def get_system_resource_mapping(self) -> dict:
        """
        Get mapping of system resource IDs to their subresource IDs.
        
        Returns:
            dict: Mapping from system resource ID to list of subresource IDs.
        """
        if self._system_resource_mapping is not None:
            return self._system_resource_mapping
        
        if self.production_system_data is None:
            return {}
        
        system_resource_mapping = {}
        for resource_data in self.production_system_data.resource_data:
            if isinstance(resource_data, SystemResourceData):
                system_resource_mapping[resource_data.ID] = resource_data.subresource_ids
        
        return system_resource_mapping
    
    def get_sink_source_queue_names(self) -> tuple[set, set]:
        """
        Get names of sink input queues and source output queues.
        
        Returns:
            tuple[set, set]: (sink_input_queues, source_output_queues)
        """
        if self._sink_input_queues is not None and self._source_output_queues is not None:
            return self._sink_input_queues, self._source_output_queues
        
        sink_input_queues = set()
        source_output_queues = set()
        
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


def get_conditions_for_interface_state(df: pd.DataFrame) -> pd.Series:
    """
    Returns a boolean series indicating whether a row belongs to an interface state.
    
    An interface state is a state where a resource does not perform a process,
    i.e. either setup, breakdown, creation (source) or finish (sink) of products.
    
    Args:
        df: Data frame with the simulation results.
    
    Returns:
        pd.Series: Boolean series indicating interface states.
    """
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


def get_conditions_for_process_state(df: pd.DataFrame) -> pd.Series:
    """
    Returns a boolean series indicating whether a row belongs to a process state.
    
    A process state is a state where a resource performs a process,
    i.e. either production or transport.
    
    Args:
        df: Data frame with the simulation results.
    
    Returns:
        pd.Series: Boolean series indicating process states.
    """
    return df["State Type"].isin(
        [
            state.StateTypeEnum.production,
            state.StateTypeEnum.transport,
            state.StateTypeEnum.dependency,
        ]
    )

