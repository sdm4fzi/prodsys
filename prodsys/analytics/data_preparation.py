"""
Data preparation module for analytics calculations.

This module handles the preparation and enrichment of raw simulation data.
"""

from __future__ import annotations

from functools import cached_property

import pandas as pd

from prodsys.simulation import state
from prodsys.analytics.base import AnalyticsContext, get_conditions_for_interface_state, get_conditions_for_process_state

import logging

logger = logging.getLogger(__name__)


class DataPreparation:
    """
    Handles data preparation and enrichment for analytics calculations.
    """
    
    def __init__(self, context: AnalyticsContext):
        """
        Initialize data preparation with analytics context.
        
        Args:
            context: Analytics context containing raw data and configuration.
        """
        self.context = context
    
    @cached_property
    def df_prepared(self) -> pd.DataFrame:
        """
        Prepares the raw data frame by adding enriched columns.
        
        Adds the following columns:
            - DateTime: Time of the event
            - Combined_activity: Activity and state of the event combined for easier filtering
            - Product_type: Type of the product
            - State_type: Type of the state according to the StateTypeEnum
            - State_sorting_Index: Index to sort the states in the correct order
        
        Returns:
            pd.DataFrame: Data frame with the simulation results and the added columns.
        """
        df = self.context.df_raw.copy()
        df["DateTime"] = pd.to_datetime(df["Time"], unit="m")
        df["Combined_activity"] = df["State"] + " " + df["Activity"]
        df["Product_type"] = df["Product"].str.rsplit("_", n=1).str[0]
        if "Primitive" not in df.columns:
            df["Primitive"] = None
        df["Primitive_type"] = df["Primitive"].str.rsplit("_", n=1).str[0]
        df.loc[
            get_conditions_for_interface_state(df),
            "State_type",
        ] = "Interface State"
        df.loc[
            get_conditions_for_process_state(df),
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
        Returns a prepared data frame with only finished products.
        
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
        """
        Filters dataframe to only include product entries (excluding primitives).
        
        Args:
            input_df: Input dataframe to filter.
        
        Returns:
            pd.DataFrame: Filtered dataframe with only product entries.
        """
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
    
    def get_primitive_types(self) -> list[str]:
        """
        Returns a list of primitive types of the resources.
        
        Returns:
            list[str]: List of primitive types of the resources.
        """
        return self.df_prepared["Primitive_type"].dropna().unique().tolist()

