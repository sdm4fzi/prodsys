"""
Scrap analytics module.

This module handles scrap rate calculations.
"""

from __future__ import annotations

from functools import cached_property

import pandas as pd

from prodsys.simulation import state
from prodsys.analytics.base import AnalyticsContext
from prodsys.analytics.data_preparation import DataPreparation

import logging

logger = logging.getLogger(__name__)


class ScrapAnalytics:
    """
    Handles scrap rate calculations.
    """
    
    def __init__(self, context: AnalyticsContext, data_prep: DataPreparation):
        """
        Initialize scrap analytics.
        
        Args:
            context: Analytics context containing raw data and configuration.
            data_prep: Data preparation instance for accessing prepared data.
        """
        self.context = context
        self.data_prep = data_prep
    
    @cached_property
    def df_scrap_per_product_type(self) -> pd.DataFrame:
        """
        Returns a data frame with the scrap rate for each product type.
        Scrap rate is calculated as: (Number of failed processes) / (Total number of processes) * 100
        
        Returns:
            pd.DataFrame: Data frame with scrap rate per product type. Columns: Product_type, Scrap_count, Total_count, Scrap_rate
        """
        df = self.data_prep.df_prepared.copy()
        
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
        primitive_types = self.data_prep.get_primitive_types()
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
        df = self.data_prep.df_prepared.copy()
        
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

