"""
Throughput analytics module.

This module handles all throughput-related analytics calculations.
"""

from __future__ import annotations

from functools import cached_property
from typing import List

import pandas as pd

from prodsys.models import performance_indicators
from prodsys.analytics.base import AnalyticsContext
from prodsys.analytics.data_preparation import DataPreparation
from prodsys.util.warm_up_post_processing import get_warm_up_cutoff_index

import logging

logger = logging.getLogger(__name__)


class ThroughputAnalytics:
    """
    Handles throughput-related analytics calculations.
    """
    
    def __init__(self, context: AnalyticsContext, data_prep: DataPreparation):
        """
        Initialize throughput analytics.
        
        Args:
            context: Analytics context containing raw data and configuration.
            data_prep: Data preparation instance for accessing prepared data.
        """
        self.context = context
        self.data_prep = data_prep
    
    @cached_property
    def df_throughput(self) -> pd.DataFrame:
        """
        Returns a data frame with the throughput time for each finished product.
        
        Returns:
            pd.DataFrame: Data frame with the throughput time for each finished product.
        """
        df = self.data_prep.df_prepared.copy()
        df_finished_product = self.data_prep.df_finished_product.copy()
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
        if df["Start_time"].min() == self.data_prep.df_finished_product["Time"].min():
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
                df_product_type, "Throughput_time", self.context.cut_off_method
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
    def df_aggregated_throughput_time(self) -> pd.DataFrame:
        """
        Returns a data frame with the average throughput time for each product type.
        
        Returns:
            pd.DataFrame: Data frame with the average throughput time for each product type.
        """
        if self.context.warm_up_cutoff:
            df = self.df_throughput_with_warum_up_cutoff.copy()
        else:
            df = self.df_throughput.copy()
        df = df.groupby(by=["Product_type"])["Throughput_time"].mean()
        return df
    
    @cached_property
    def df_aggregated_output_and_throughput(self) -> pd.DataFrame:
        """
        Returns a data frame with the average throughput and output for each product type.
        
        Returns:
            pd.DataFrame: Data frame with the average throughput and output for each product type.
        """
        if self.context.warm_up_cutoff:
            df = self.df_throughput_with_warum_up_cutoff.copy()
        else:
            df = self.df_throughput.copy()
        
        available_time = df["End_time"].max() - df["Start_time"].min()
        df_tp = df.groupby(by="Product_type")["Product"].count().to_frame()
        df_tp.rename(columns={"Product": "Output"}, inplace=True)
        df_tp["Throughput"] = df_tp["Output"] / available_time
        
        return df_tp
    
    @cached_property
    def df_aggregated_output(self) -> pd.DataFrame:
        """
        Returns a data frame with the total output for each product type.
        
        Returns:
            pd.DataFrame: Data frame with the total output for each product type.
        """
        if self.context.warm_up_cutoff:
            df = self.df_throughput_with_warum_up_cutoff.copy()
        else:
            df = self.df_throughput.copy()
        df_tp = df.groupby(by="Product_type")["Product"].count()
        
        return df_tp

