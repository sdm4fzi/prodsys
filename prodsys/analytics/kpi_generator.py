"""
KPI generator module.

This module handles KPI generation from analytics results.
"""

from __future__ import annotations

from functools import cached_property
from typing import List

import pandas as pd

from prodsys.models import performance_indicators
from prodsys.analytics.base import AnalyticsContext
from prodsys.analytics.data_preparation import DataPreparation
from prodsys.analytics.throughput import ThroughputAnalytics
from prodsys.analytics.resource_states import ResourceStatesAnalytics

import logging

logger = logging.getLogger(__name__)


class KPIGenerator:
    """
    Handles KPI generation from analytics results.
    """
    
    def __init__(
        self,
        context: AnalyticsContext,
        data_prep: DataPreparation,
        throughput_analytics: ThroughputAnalytics,
        resource_states_analytics: ResourceStatesAnalytics,
    ):
        """
        Initialize KPI generator.
        
        Args:
            context: Analytics context containing raw data and configuration.
            data_prep: Data preparation instance.
            throughput_analytics: Throughput analytics instance.
            resource_states_analytics: Resource states analytics instance.
        """
        self.context = context
        self.data_prep = data_prep
        self.throughput_analytics = throughput_analytics
        self.resource_states_analytics = resource_states_analytics
    
    @cached_property
    def dynamic_thoughput_time_KPIs(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of Dynamic Throughput KPI values for the throughput time of each finished product.

        Returns:
            List[performance_indicators.KPI]: List of Dynamic Throughput KPI values.
        """
        df_tp = self.throughput_analytics.df_throughput.copy()
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
    def aggregated_throughput_time_KPIs(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of average Throughput Time KPI values for each product type.

        Returns:
            List[performance_indicators.KPI]: List of average Throughput Time KPI values.
        """
        ser = self.throughput_analytics.df_aggregated_throughput_time.copy()
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
    def throughput_and_output_KPIs(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of average Throughput and Output KPI values for each product type.

        Returns:
            List[performance_indicators.KPI]: List of average Throughput and Output KPI values.
        """
        df = self.throughput_analytics.df_aggregated_output_and_throughput.copy()
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
    def machine_state_KPIS(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of KPI values for the time spent in each state of each resource.

        Returns:
            List[performance_indicators.KPI]: List of KPI values for the time spent in each state of each resource.
        """
        df = self.resource_states_analytics.df_aggregated_resource_states.copy()
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
