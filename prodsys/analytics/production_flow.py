"""
Production flow analytics module.

This module handles production flow ratio calculations.
"""

from __future__ import annotations

from functools import cached_property

import pandas as pd

from prodsys.analytics.base import AnalyticsContext
from prodsys.analytics.data_preparation import DataPreparation
from prodsys.analytics.throughput import ThroughputAnalytics

import logging

logger = logging.getLogger(__name__)


class ProductionFlowAnalytics:
    """
    Handles production flow ratio calculations.
    """
    
    def __init__(self, context: AnalyticsContext, data_prep: DataPreparation, throughput_analytics: ThroughputAnalytics):
        """
        Initialize production flow analytics.
        
        Args:
            context: Analytics context containing raw data and configuration.
            data_prep: Data preparation instance for accessing prepared data.
            throughput_analytics: Throughput analytics instance.
        """
        self.context = context
        self.data_prep = data_prep
        self.throughput_analytics = throughput_analytics
    
    @cached_property
    def df_production_flow_ratio(self) -> pd.DataFrame:
        """
        Calculates the production flow ratio for each product type.
        
        Returns:
            pd.DataFrame: DataFrame containing the production flow ratio for each product type.
                The DataFrame has the following columns:
                - Product_type: The type of the product.
                - Production: The percentage of time spent in production activities.
                - Transport: The percentage of time spent in transport activities.
                - Idle: The percentage of idle time.
        """
        df_finished_product = self.data_prep.df_finished_product.copy()
        
        if self.context.warm_up_cutoff:
            df_finished_product = df_finished_product.loc[
                df_finished_product["Time"] >= self.throughput_analytics.warm_up_cutoff_time
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
        
        df_aggregated_throughput_time_copy = self.throughput_analytics.df_aggregated_throughput_time.copy()
        
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
