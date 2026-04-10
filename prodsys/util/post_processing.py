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

from prodsys.analytics.store import AnalyticsStore
from prodsys.analytics.warm_up import detect_warm_up

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
    _store: Optional[AnalyticsStore] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        if self.filepath:
            self.read_df_from_csv()
        self._initialize_analytics()

    def _initialize_analytics(self):
        """Initialize the v2 AnalyticsStore."""
        if self.df_raw is not None:
            exclude = set()
            sink_queues, source_queues = self._get_sink_source_queue_names()
            exclude.update(sink_queues)
            exclude.update(source_queues)
            self._store = AnalyticsStore(
                time_range=self.time_range,
                exclude_resources=exclude,
                production_system_data=self.production_system_data,
            )
            self._store.ingest_events(self.df_raw)

    def _invalidate_cached_properties(self):
        """Clear all cached_property caches so they recompute from the new store."""
        cls = type(self)
        for attr_name in list(vars(cls)):
            if isinstance(getattr(cls, attr_name, None), cached_property):
                self.__dict__.pop(attr_name, None)

    @property
    def store(self) -> AnalyticsStore:
        """Access the v2 AnalyticsStore for interval-based queries."""
        if self._store is None:
            self._initialize_analytics()
        return self._store

    def set_production_system_data(self, production_system_data: ProductionSystemData):
        self.production_system_data = production_system_data
        self._system_resource_mapping = None
        self._sink_input_queues = None
        self._source_output_queues = None
        self._invalidate_cached_properties()
        self._initialize_analytics()

    def set_system_resource_mapping(self, mapping: dict):
        self._system_resource_mapping = mapping
        self._invalidate_cached_properties()
        self._initialize_analytics()

    def set_sink_source_queue_names(self, sink_input_queues: set, source_output_queues: set):
        self._sink_input_queues = sink_input_queues
        self._source_output_queues = source_output_queues
        self._invalidate_cached_properties()
        self._initialize_analytics()

    def _get_system_resource_mapping(self) -> dict:
        if self._system_resource_mapping is not None:
            return self._system_resource_mapping
        if self.production_system_data is None:
            return {}
        system_resource_mapping = {}
        for resource_data in self.production_system_data.resource_data:
            if isinstance(resource_data, SystemResourceData):
                system_resource_mapping[resource_data.ID] = resource_data.subresource_ids
        return system_resource_mapping

    def _get_sink_source_queue_names(self) -> tuple[set, set]:
        if self._sink_input_queues is not None and self._source_output_queues is not None:
            return self._sink_input_queues, self._source_output_queues
        sink_input_queues = set()
        source_output_queues = set()
        if self.production_system_data is None:
            return sink_input_queues, source_output_queues
        for sink_data in self.production_system_data.sink_data:
            if sink_data.ports:
                sink_input_queues.update(sink_data.ports)
        for source_data in self.production_system_data.source_data:
            if source_data.ports:
                source_output_queues.update(source_data.ports)
        return sink_input_queues, source_output_queues

    def read_df_from_csv(self, filepath_input: str = None):
        if filepath_input:
            self.filepath = filepath_input
        self.df_raw = pd.read_csv(self.filepath)
        self.df_raw.drop(columns=["Unnamed: 0"], inplace=True)
        self._invalidate_cached_properties()
        self._initialize_analytics()

    def get_total_simulation_time(self) -> float:
        return self.store.simulation_end_time

    # ── Throughput ────────────────────────────────────────────────────────

    @cached_property
    def df_throughput(self) -> pd.DataFrame:
        return self.store.throughput()

    @cached_property
    def warm_up_cutoff_time(self) -> float:
        if not self.warm_up_cutoff:
            return 0.0
        return detect_warm_up(self.store, self.cut_off_method)

    @cached_property
    def df_throughput_with_warum_up_cutoff(self) -> pd.DataFrame:
        return self.store.throughput(t_from=self.warm_up_cutoff_time)

    @cached_property
    def df_aggregated_throughput_time(self) -> pd.Series:
        return self.store.aggregated_throughput_time()

    @cached_property
    def df_aggregated_output_and_throughput(self) -> pd.DataFrame:
        return self.store.aggregated_output_and_throughput()

    @cached_property
    def df_aggregated_output(self) -> pd.Series:
        return self.store.aggregated_output()

    # ── Resource states ──────────────────────────────────────────────────

    @cached_property
    def df_resource_states(self) -> pd.DataFrame:
        """Raw resource intervals (replacement for the old event-based resource states)."""
        return self.store.resource_intervals()

    @cached_property
    def df_aggregated_resource_states(self) -> pd.DataFrame:
        df = self._compute_resource_states_merged()
        system_mapping = self._get_system_resource_mapping()
        if system_mapping:
            df_system = self._compute_system_resource_states(system_mapping)
            if len(df_system) > 0:
                df = pd.concat([df, df_system], ignore_index=True)
        return df

    def _compute_resource_states_merged(self) -> pd.DataFrame:
        """
        Compute resource states with proper handling of overlapping intervals
        for multi-capacity resources: merge overlapping intervals of the same
        type before summing durations.
        """
        from prodsys.simulation.state import StateTypeEnum

        _STATE_TO_TT = {
            StateTypeEnum.production.value: "PR",
            StateTypeEnum.transport.value: "PR",
            StateTypeEnum.breakdown.value: "UD",
            StateTypeEnum.setup.value: "ST",
            StateTypeEnum.charging.value: "CR",
            StateTypeEnum.dependency.value: "DP",
            StateTypeEnum.non_scheduled.value: "NS",
        }
        _EXCLUDED = frozenset({
            StateTypeEnum.loading.value, StateTypeEnum.unloading.value,
            StateTypeEnum.source.value, StateTypeEnum.sink.value,
        })

        t_to = self.store.simulation_end_time
        df = self.store.resource_intervals(0.0, t_to)
        if len(df) == 0:
            return pd.DataFrame(columns=["Resource", "Time_type", "time_increment", "resource_time", "percentage"])

        excluded = set(self.store._exclude_resources)
        df = df[~df["entity_id"].isin(excluded)]
        df = df[~df["state_type"].isin(_EXCLUDED)]
        if len(df) == 0:
            return pd.DataFrame(columns=["Resource", "Time_type", "time_increment", "resource_time", "percentage"])

        df = df.copy()
        df["Time_type"] = df["state_type"].map(_STATE_TO_TT)
        df = df[df["Time_type"].notna()]

        resource_time = t_to
        rows = []
        for resource in df["entity_id"].unique():
            res_df = df[df["entity_id"] == resource]
            for tt in res_df["Time_type"].unique():
                tt_df = res_df[res_df["Time_type"] == tt]
                intervals = tt_df[["t_start", "t_end"]].values.tolist()
                intervals.sort(key=lambda x: x[0])
                # Merge overlapping intervals
                merged = [[intervals[0][0], intervals[0][1]]]
                for s, e in intervals[1:]:
                    if s <= merged[-1][1]:
                        merged[-1][1] = max(merged[-1][1], e)
                    else:
                        merged.append([s, e])
                total = sum(min(e, t_to) - max(s, 0.0) for s, e in merged)
                if total > 0:
                    rows.append({
                        "Resource": resource, "Time_type": tt,
                        "time_increment": total, "resource_time": resource_time,
                        "percentage": total / resource_time * 100,
                    })
            # Resolve NS/UD overlap: UD takes priority
            res_rows = [r for r in rows if r["Resource"] == resource]
            ns_time = sum(r["time_increment"] for r in res_rows if r["Time_type"] == "NS")
            ud_time = sum(r["time_increment"] for r in res_rows if r["Time_type"] == "UD")
            if ns_time > 0 and ud_time > 0:
                ns_intervals = res_df[res_df["Time_type"] == "NS"][["t_start", "t_end"]].values.tolist()
                ud_intervals = res_df[res_df["Time_type"] == "UD"][["t_start", "t_end"]].values.tolist()
                ns_intervals.sort(key=lambda x: x[0])
                ud_intervals.sort(key=lambda x: x[0])
                ns_merged = self._merge_interval_list(ns_intervals)
                ud_merged = self._merge_interval_list(ud_intervals)
                overlap = self._overlap_duration(ns_merged, ud_merged)
                if overlap > 0:
                    for r in rows:
                        if r["Resource"] == resource and r["Time_type"] == "NS":
                            r["time_increment"] = max(0.0, r["time_increment"] - overlap)
                            r["percentage"] = r["time_increment"] / resource_time * 100
            # Subtract NS time from other non-UD states
            if ns_time > 0:
                ns_intervals = res_df[res_df["Time_type"] == "NS"][["t_start", "t_end"]].values.tolist()
                ns_merged = self._merge_interval_list(ns_intervals)
                for r in rows:
                    if r["Resource"] == resource and r["Time_type"] not in ("NS", "UD"):
                        other_intervals = res_df[res_df["Time_type"] == r["Time_type"]][["t_start", "t_end"]].values.tolist()
                        other_merged = self._merge_interval_list(other_intervals)
                        overlap = self._overlap_duration(other_merged, ns_merged)
                        if overlap > 0:
                            r["time_increment"] = max(0.0, r["time_increment"] - overlap)
                            r["percentage"] = r["time_increment"] / resource_time * 100
            # Add standby
            total_active = sum(r["time_increment"] for r in rows if r["Resource"] == resource)
            sb = max(0.0, resource_time - total_active)
            if sb > 1e-10:
                rows.append({
                    "Resource": resource, "Time_type": "SB",
                    "time_increment": sb, "resource_time": resource_time,
                    "percentage": sb / resource_time * 100,
                })

        if not rows:
            return pd.DataFrame(columns=["Resource", "Time_type", "time_increment", "resource_time", "percentage"])
        result = pd.DataFrame(rows)
        result = result[result["time_increment"] > 1e-10].reset_index(drop=True)
        return result

    @staticmethod
    def _merge_interval_list(intervals: list) -> list[tuple[float, float]]:
        if not intervals:
            return []
        intervals = sorted(intervals, key=lambda x: x[0])
        merged = [[intervals[0][0], intervals[0][1]]]
        for s, e in intervals[1:]:
            if s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        return [(s, e) for s, e in merged]

    @staticmethod
    def _overlap_duration(a: list, b: list) -> float:
        total = 0.0
        for a_s, a_e in a:
            for b_s, b_e in b:
                o_s = max(a_s, b_s)
                o_e = min(a_e, b_e)
                if o_s < o_e:
                    total += o_e - o_s
        return total

    def get_resource_states_by_interval(self, interval_minutes: float) -> pd.DataFrame:
        return self.store.resource_states_by_interval(interval_minutes)

    def get_aggregated_resource_states_by_interval(self, interval_minutes: float) -> pd.DataFrame:
        return self.store.resource_states_by_interval(interval_minutes)

    # ── OEE ──────────────────────────────────────────────────────────────

    def get_oee_per_resource_by_interval(self, interval_minutes: float) -> pd.DataFrame:
        return self.store.oee_per_resource_by_interval(interval_minutes)

    @cached_property
    def df_oee_production_system(self) -> pd.DataFrame:
        return self.store.oee_production_system()

    @cached_property
    def df_oee_per_resource(self) -> pd.DataFrame:
        return self.store.oee_per_resource()

    # ── Production flow ──────────────────────────────────────────────────

    @cached_property
    def df_production_flow_ratio(self) -> pd.DataFrame:
        return self.store.production_flow_ratio()

    # ── Scrap ────────────────────────────────────────────────────────────

    @cached_property
    def df_scrap_per_product_type(self) -> pd.DataFrame:
        return self.store.scrap_per_product_type(
            primitive_types=set(self.get_primitive_types())
        )

    @cached_property
    def df_scrap_per_resource(self) -> pd.DataFrame:
        return self.store.scrap_per_resource()

    # ── WIP ──────────────────────────────────────────────────────────────

    @cached_property
    def df_WIP(self) -> pd.DataFrame:
        return self.store.wip()

    @cached_property
    def df_WIP_per_product(self) -> pd.DataFrame:
        df = self.store.wip()
        if len(df) == 0:
            return pd.DataFrame(columns=["Product_type", "Time", "WIP", "WIP_Increment"])
        result_dfs = []
        for product_type in df["Product_type"].dropna().unique():
            df_pt = df[df["Product_type"] == product_type].copy()
            df_pt = df_pt.sort_values("Time").reset_index(drop=True)
            df_pt["WIP"] = df_pt["WIP_Increment"].cumsum().clip(lower=0).astype(float)
            result_dfs.append(df_pt)
        if result_dfs:
            return pd.concat(result_dfs, ignore_index=True)
        return pd.DataFrame(columns=["Product_type", "Time", "WIP", "WIP_Increment"])

    @cached_property
    def df_WIP_per_resource(self) -> pd.DataFrame:
        """WIP per resource over time, computed from raw event data."""
        if self.df_raw is None:
            return pd.DataFrame(columns=["Time", "WIP", "WIP_resource", "WIP_Increment"])
        return self._compute_wip_per_resource(self.df_raw)

    @cached_property
    def df_aggregated_WIP(self) -> pd.Series:
        return self.store.aggregated_wip()

    # ── Primitive WIP ────────────────────────────────────────────────────

    def get_primitive_types(self) -> List[str]:
        if self.df_raw is None:
            return []
        if "Primitive_type" not in self.df_raw.columns:
            return []
        return self.df_raw["Primitive_type"].dropna().unique().tolist()

    @cached_property
    def df_primitive_WIP(self) -> pd.DataFrame:
        return self._compute_primitive_wip(self.df_raw)

    @cached_property
    def df_primitive_WIP_per_primitive_type(self) -> pd.DataFrame:
        if self.df_raw is None:
            return pd.DataFrame()
        primitive_types = self.get_primitive_types()
        if not primitive_types:
            return pd.DataFrame()
        result_dfs = []
        for pt in primitive_types:
            df_pt = self.df_raw[self.df_raw.get("Primitive_type") == pt].copy()
            df_pt = self._compute_primitive_wip(df_pt)
            if len(df_pt) > 0:
                result_dfs.append(df_pt)
        if result_dfs:
            return pd.concat(result_dfs, ignore_index=True)
        return pd.DataFrame()

    @cached_property
    def df_aggregated_primitive_WIP(self) -> pd.Series:
        df = self.df_primitive_WIP_per_primitive_type.copy()
        df_total = self.df_primitive_WIP.copy()
        if len(df_total) == 0:
            return pd.Series(dtype=float, name="primitive_WIP")
        df_total["Primitive_type"] = "Total"
        df = pd.concat([df, df_total])
        if self.warm_up_cutoff:
            df = df.loc[df["Time"] >= self.warm_up_cutoff_time]
        return df.groupby("Primitive_type")["primitive_WIP"].mean()

    # ── Aggregated data convenience ──────────────────────────────────────

    def get_aggregated_data(self) -> dict:
        data = {}
        data["Throughput"] = (
            self.df_aggregated_output_and_throughput.copy().reset_index().to_dict()
        )
        data["WIP"] = self.df_aggregated_WIP.copy().reset_index().to_dict() if isinstance(self.df_aggregated_WIP, pd.DataFrame) else self.df_aggregated_WIP.to_frame().reset_index().to_dict()
        data["Throughput time"] = (
            self.df_aggregated_throughput_time.copy().reset_index().to_dict() if isinstance(self.df_aggregated_throughput_time, pd.DataFrame) else self.df_aggregated_throughput_time.to_frame().reset_index().to_dict()
        )
        data["Resource states"] = (
            self.df_aggregated_resource_states.copy()
            .set_index(["Resource", "Time_type"])
            .reset_index()
            .to_dict()
        )
        return data

    def get_aggregated_throughput_time_data(self) -> List[float]:
        s = self.df_aggregated_throughput_time
        return list(s.values) if len(s) > 0 else []

    def get_aggregated_throughput_data(self) -> List[float]:
        s = self.df_aggregated_output
        return list(s.values) if len(s) > 0 else []

    def get_aggregated_wip_data(self) -> List[float]:
        s = self.df_aggregated_WIP.copy()
        if isinstance(s, pd.Series):
            s = s.drop(labels=["Total"], errors="ignore")
            return list(s.values)
        return []

    # ── KPI generators ───────────────────────────────────────────────────

    @cached_property
    def dynamic_thoughput_time_KPIs(self) -> List[performance_indicators.KPI]:
        df_tp = self.df_throughput.copy()
        KPIs = []
        context = (
            performance_indicators.KPILevelEnum.SYSTEM,
            performance_indicators.KPILevelEnum.PRODUCT,
        )
        for _, values in df_tp.iterrows():
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
    def throughput_and_output_KPIs(self) -> List[performance_indicators.KPI]:
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
    def machine_state_KPIS(self) -> List[performance_indicators.KPI]:
        df = self.df_aggregated_resource_states.copy()
        KPIs = []
        context = (performance_indicators.KPILevelEnum.RESOURCE,)
        class_dict = {
            "SB": (performance_indicators.StandbyTime, performance_indicators.KPIEnum.STANDBY_TIME),
            "PR": (performance_indicators.ProductiveTime, performance_indicators.KPIEnum.PRODUCTIVE_TIME),
            "UD": (performance_indicators.UnscheduledDowntime, performance_indicators.KPIEnum.UNSCHEDULED_DOWNTIME),
            "ST": (performance_indicators.SetupTime, performance_indicators.KPIEnum.SETUP_TIME),
            "CR": (performance_indicators.ChargingTime, performance_indicators.KPIEnum.CHARGING_TIME),
            "DP": (performance_indicators.DependencyTime, performance_indicators.KPIEnum.DEPENDENCY_TIME),
        }
        for _, values in df.iterrows():
            tt = values["Time_type"]
            if tt not in class_dict:
                continue
            KPIs.append(
                class_dict[tt][0](
                    name=class_dict[tt][1],
                    value=values["percentage"],
                    context=context,
                    resource=values["Resource"],
                )
            )
        return KPIs

    def get_WIP_KPI(self, df: pd.DataFrame) -> pd.DataFrame:
        """Kept for backward compatibility."""
        return self.df_WIP

    def get_primitive_WIP_KPI(self, df: pd.DataFrame) -> pd.DataFrame:
        """Kept for backward compatibility."""
        return self.df_primitive_WIP

    @cached_property
    def dynamic_WIP_per_resource_KPIs(self) -> List[performance_indicators.KPI]:
        df = self.df_WIP_per_resource.copy()
        df = df.loc[df["WIP_Increment"] != 0]
        KPIs = []
        df["next_Time"] = df.groupby("WIP_resource")["Time"].shift(-1)
        df["next_Time"] = df["next_Time"].fillna(df["Time"])
        for _, row in df.iterrows():
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
        df = self.df_WIP.copy()
        df["Product_type"] = "Total"
        df_per_product = self.df_WIP_per_product.copy()
        df = pd.concat([df, df_per_product])
        df = df.loc[~df["WIP_Increment"].isnull()]
        KPIs = []
        df["next_Time"] = df.groupby("Product_type")["Time"].shift(-1)
        df["next_Time"] = df["next_Time"].fillna(df["Time"])
        for _, row in df.iterrows():
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
    def WIP_KPIs(self) -> List[performance_indicators.KPI]:
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

    # ── Internal helpers ─────────────────────────────────────────────────

    def _compute_wip_per_resource(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        """Compute WIP per resource from raw event data."""
        df = df_raw.copy()
        df = df.loc[df["Time"] != 0].copy()
        df["WIP_Increment"] = 0
        df["WIP_resource"] = None

        sink_resources = df[df["State Type"].isin([state.StateTypeEnum.sink, state.StateTypeEnum.sink.value])]["Resource"].unique()
        sink_resources_set = set(sink_resources)
        sink_queues = set()

        unloading_types = {state.StateTypeEnum.unloading, state.StateTypeEnum.unloading.value, "Unloading"}
        loading_types = {state.StateTypeEnum.loading, state.StateTypeEnum.loading.value, "Loading"}

        unloading_to_sinks = df[
            (df["State Type"].isin(unloading_types))
            & (df["Resource"].isin(sink_resources_set))
            & (df["Target location"].notna())
        ]["Target location"].unique()
        sink_queues.update(unloading_to_sinks)

        if self._sink_input_queues:
            sink_queues.update(self._sink_input_queues)

        CREATED_CONDITION = df["Activity"] == state.StateEnum.created_product
        created_mask = CREATED_CONDITION & ~df["Resource"].isin(sink_resources_set)
        df.loc[created_mask, "WIP_Increment"] = 1
        df.loc[created_mask, "WIP_resource"] = df.loc[created_mask, "Resource"]

        CONSUMED_CONDITION = df["Activity"] == state.StateEnum.consumed_product
        consumed_mask = CONSUMED_CONDITION & ~df["Resource"].isin(sink_resources_set)
        df.loc[consumed_mask, "WIP_Increment"] = -1
        df.loc[consumed_mask, "WIP_resource"] = df.loc[consumed_mask, "Resource"]

        end_loading = (df["State Type"].isin(loading_types)) & (df["Activity"] == "end state")
        end_loading_valid = end_loading & ~df["Resource"].isin(sink_resources_set)

        parts = [df]

        if end_loading_valid.any():
            el_res = df[end_loading_valid].copy()
            el_res["WIP_Increment"] = 1
            el_res["WIP_resource"] = el_res["Resource"]
            parts.append(el_res)

            el_queue = df[end_loading_valid].copy()
            el_queue = el_queue[~el_queue["Origin location"].isin(sink_queues)]
            if len(el_queue) > 0:
                el_queue["WIP_Increment"] = -1
                el_queue["WIP_resource"] = el_queue["Origin location"]
                parts.append(el_queue)

        end_unloading = (df["State Type"].isin(unloading_types)) & (df["Activity"] == "end state")
        end_unloading_valid = end_unloading & ~df["Resource"].isin(sink_resources_set)

        if end_unloading_valid.any():
            eu_res = df[end_unloading_valid].copy()
            eu_res["WIP_Increment"] = -1
            eu_res["WIP_resource"] = eu_res["Resource"]
            parts.append(eu_res)

            eu_queue = df[end_unloading_valid].copy()
            eu_queue = eu_queue[~eu_queue["Target location"].isin(sink_queues)]
            if len(eu_queue) > 0:
                eu_queue["WIP_Increment"] = 1
                eu_queue["WIP_resource"] = eu_queue["Target location"]
                parts.append(eu_queue)

        df = pd.concat(parts, ignore_index=True)
        df = df.sort_values(by=["Time", "WIP_Increment"], ascending=[True, False], ignore_index=True)
        df = df[df["WIP_resource"].notna()]
        df = df[~df["WIP_resource"].isin(sink_resources_set)]
        df = df[~df["WIP_resource"].isin(sink_queues)]
        df = df.sort_values(by=["WIP_resource", "Time"]).reset_index(drop=True)
        df["WIP"] = df.groupby("WIP_resource")["WIP_Increment"].cumsum().clip(lower=0)
        return df

    @staticmethod
    def _compute_primitive_wip(df_raw: pd.DataFrame) -> pd.DataFrame:
        """Compute primitive WIP from raw event data."""
        if df_raw is None or len(df_raw) == 0:
            return pd.DataFrame(columns=["Time", "primitive_WIP", "Primitive_type"])
        if "Primitive_type" not in df_raw.columns:
            return pd.DataFrame(columns=["Time", "primitive_WIP", "Primitive_type"])

        df = df_raw.copy()
        dep_type_vals = {state.StateTypeEnum.dependency, state.StateTypeEnum.dependency.value, "Dependency"}
        start_cond = (df["Activity"] == "start state") & (df["State Type"].isin(dep_type_vals)) & (df["Primitive_type"].notna())
        end_cond = (df["Activity"] == "end state") & (df["State Type"].isin(dep_type_vals)) & (df["Primitive_type"].notna())

        df["primitive_WIP_Increment"] = 0
        df.loc[start_cond, "primitive_WIP_Increment"] = 1
        df.loc[end_cond, "primitive_WIP_Increment"] = -1
        df["primitive_WIP"] = df["primitive_WIP_Increment"].cumsum()
        return df

    def _compute_system_resource_states(self, system_mapping: dict) -> pd.DataFrame:
        """
        Aggregate subresource intervals into system-level resource states.
        A system resource is PR if any subresource has an active production/transport interval.
        """
        from prodsys.simulation.state import StateTypeEnum

        t_end = self.store.simulation_end_time
        productive_types = frozenset({
            StateTypeEnum.production.value,
            StateTypeEnum.transport.value,
        })
        rows = []
        for sys_id, sub_ids in system_mapping.items():
            ri = self.store.resource_intervals(0.0, t_end)
            sub_ri = ri[
                (ri["entity_id"].isin(sub_ids))
                & (ri["state_type"].isin(productive_types))
                & (~ri["interrupted"])
            ]
            if len(sub_ri) == 0:
                rows.append({
                    "Resource": sys_id, "Time_type": "SB",
                    "time_increment": t_end, "resource_time": t_end,
                    "percentage": 100.0,
                })
                continue

            # Merge overlapping productive intervals across subresources
            intervals = sub_ri[["t_start", "t_end"]].values.tolist()
            intervals.sort(key=lambda x: x[0])
            merged = [[intervals[0][0], intervals[0][1]]]
            for s, e in intervals[1:]:
                if s <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], e)
                else:
                    merged.append([s, e])
            pr_time = sum(e - s for s, e in merged)
            sb_time = max(0.0, t_end - pr_time)

            if pr_time > 0:
                rows.append({
                    "Resource": sys_id, "Time_type": "PR",
                    "time_increment": pr_time, "resource_time": t_end,
                    "percentage": pr_time / t_end * 100,
                })
            if sb_time > 0:
                rows.append({
                    "Resource": sys_id, "Time_type": "SB",
                    "time_increment": sb_time, "resource_time": t_end,
                    "percentage": sb_time / t_end * 100,
                })
        if not rows:
            return pd.DataFrame(columns=["Resource", "Time_type", "time_increment", "resource_time", "percentage"])
        return pd.DataFrame(rows)

    def get_WIP_per_resource_KPI(self, df: pd.DataFrame) -> pd.DataFrame:
        """Kept for backward compatibility."""
        return self.df_WIP_per_resource
