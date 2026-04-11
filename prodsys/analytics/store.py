"""
AnalyticsStore: the public query surface for the interval-based analytics pipeline.

Wraps IntervalBuilder, resolves interval overlaps, and computes KPIs
directly from the interval representation.
"""

from __future__ import annotations

from typing import Optional, Literal, Set

import pandas as pd
import numpy as np

from prodsys.simulation.state import StateTypeEnum
from prodsys.analytics.intervals import IntervalBuilder

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from prodsys.models.production_system_data import ProductionSystemData

import logging

logger = logging.getLogger(__name__)

# Map StateTypeEnum values to the resource-state time-type codes used in output
_STATE_TO_TIME_TYPE: dict[str, str] = {
    StateTypeEnum.production.value: "PR",
    StateTypeEnum.transport.value: "PR",
    StateTypeEnum.breakdown.value: "UD",
    StateTypeEnum.setup.value: "ST",
    StateTypeEnum.charging.value: "CR",
    StateTypeEnum.dependency.value: "DP",
    StateTypeEnum.non_scheduled.value: "NS",
}

# State types that represent productive work (used for resource states)
_PRODUCTIVE_STATE_TYPES = frozenset({
    StateTypeEnum.production.value,
    StateTypeEnum.transport.value,
})

# State types that are tracked as resource states (non-standby)
_RESOURCE_STATE_TYPES = frozenset({
    StateTypeEnum.production.value,
    StateTypeEnum.transport.value,
    StateTypeEnum.breakdown.value,
    StateTypeEnum.setup.value,
    StateTypeEnum.charging.value,
    StateTypeEnum.dependency.value,
    StateTypeEnum.non_scheduled.value,
})

# State types to exclude from resource state calculations
_EXCLUDED_STATE_TYPES = frozenset({
    StateTypeEnum.loading.value,
    StateTypeEnum.unloading.value,
    StateTypeEnum.source.value,
    StateTypeEnum.sink.value,
})


class AnalyticsStore:
    """
    Central analytics store that ingests raw simulation events, builds intervals,
    and provides KPI query methods.

    Usage::

        store = AnalyticsStore()
        store.ingest_events(df_raw)
        print(store.throughput())
        print(store.resource_states())
    """

    def __init__(
        self,
        time_range: Optional[float] = None,
        exclude_resources: Optional[Set[str]] = None,
        production_system_data: Optional["ProductionSystemData"] = None,
    ):
        self.builder = IntervalBuilder()
        self._intervals: Optional[pd.DataFrame] = None
        self._t_max: float = 0.0
        self._time_range = time_range
        self._exclude_resources: Set[str] = exclude_resources or set()
        self.production_system_data = production_system_data
        self._ri_cache: Optional[pd.DataFrame] = None
        self._ri_cache_key: Optional[tuple] = None

    @classmethod
    def from_raw(
        cls,
        df_raw: pd.DataFrame,
        time_range: Optional[float] = None,
        exclude_resources: Optional[Set[str]] = None,
        production_system_data: Optional["ProductionSystemData"] = None,
    ) -> "AnalyticsStore":
        store = cls(
            time_range=time_range,
            exclude_resources=exclude_resources,
            production_system_data=production_system_data,
        )
        store.ingest_events(df_raw)
        return store

    # ── Ingest ───────────────────────────────────────────────────────────

    def ingest_events(self, df_raw: pd.DataFrame) -> None:
        """Ingest a batch of raw simulation events."""
        if df_raw is None or len(df_raw) == 0:
            return

        self._t_max = max(self._t_max, df_raw["Time"].max())

        # Auto-detect source/sink resources to exclude
        source_sink = df_raw.loc[
            df_raw["State Type"].isin([
                StateTypeEnum.source, StateTypeEnum.sink,
                StateTypeEnum.source.value, StateTypeEnum.sink.value,
            ]),
            "Resource",
        ].dropna().unique()
        self._exclude_resources.update(source_sink)

        self._ri_cache = None
        self._ri_cache_key = None

        self.builder.ingest_dataframe(df_raw)
        new_intervals = self.builder.drain()

        if self._intervals is None or len(self._intervals) == 0:
            self._intervals = new_intervals
        elif len(new_intervals) > 0:
            self._intervals = pd.concat([self._intervals, new_intervals], ignore_index=True)

    def append_events(self, df_raw: pd.DataFrame) -> None:
        """Alias for ingest_events, for incremental append."""
        self.ingest_events(df_raw)

    def finalize_at(self, t: float) -> None:
        """Snapshot still-open intervals at time ``t`` and merge them into the
        closed-interval store for KPI computation.

        Use this when comparing a partial store (built from a truncated event
        log) against a full store queried at a split boundary.  The builder
        only closes resource intervals when their matching "end state" event
        arrives; intervals that straddle the split point are therefore absent
        from a standalone partial store.  ``finalize_at`` materialises those
        intervals so both stores see the same resource time in [0, t].

        .. warning::
            Do **not** call this on a store that will receive further events.
            The builder state is unchanged: if a real "end state" event later
            arrives the interval will be emitted a second time, causing
            double-counting.
        """
        snapshot = self.builder.snapshot_open(t)
        if len(snapshot) == 0:
            return
        self._t_max = max(self._t_max, t)
        if self._intervals is None or len(self._intervals) == 0:
            self._intervals = snapshot
        else:
            self._intervals = pd.concat([self._intervals, snapshot], ignore_index=True)
        self._ri_cache = None
        self._ri_cache_key = None

    # ── Interval access ──────────────────────────────────────────────────

    @property
    def simulation_end_time(self) -> float:
        if self._time_range is not None:
            return self._time_range
        return self._t_max

    @property
    def intervals(self) -> pd.DataFrame:
        """All closed intervals."""
        if self._intervals is None:
            from prodsys.analytics.intervals import INTERVAL_COLUMNS
            return pd.DataFrame(columns=INTERVAL_COLUMNS)
        return self._intervals

    def resource_intervals(
        self,
        t_from: float = 0.0,
        t_to: Optional[float] = None,
        resource: Optional[str] = None,
    ) -> pd.DataFrame:
        """Resource intervals, optionally filtered by time range and resource."""
        if t_to is None:
            t_to = self.simulation_end_time
        cache_key = (t_from, t_to)
        if self._ri_cache_key != cache_key:
            df = self.intervals
            df = df[df["entity_kind"] == "resource"]
            df = df[(df["t_end"] > t_from) & (df["t_start"] < t_to)]
            self._ri_cache = df
            self._ri_cache_key = cache_key
        df = self._ri_cache
        if resource is not None:
            df = df[df["entity_id"] == resource]
        return df

    def product_intervals(
        self,
        t_from: float = 0.0,
        t_to: Optional[float] = None,
    ) -> pd.DataFrame:
        """Product lifecycle intervals."""
        df = self.intervals
        df = df[df["entity_kind"] == "product"]
        if t_to is None:
            t_to = self.simulation_end_time
        df = df[(df["t_end"] >= t_from) & (df["t_start"] <= t_to)]
        return df

    # ── KPI: Throughput ──────────────────────────────────────────────────

    def throughput(
        self,
        t_from: float = 0.0,
        t_to: Optional[float] = None,
    ) -> pd.DataFrame:
        """
        Per-finished-product throughput time.

        Returns DataFrame with columns:
            Product, Product_type, Throughput_time, Start_time, End_time
        """
        df = self.product_intervals(t_from, t_to)
        df_in_system = df[df["state_type"] == "in_system"].copy()
        if len(df_in_system) == 0:
            return pd.DataFrame(columns=["Product", "Product_type", "Throughput_time", "Start_time", "End_time"])

        # Check which products actually finished (have a finished_product marker)
        finished_products = set(
            df[df["state_type"] == "finished_product"]["product_id"].dropna().unique()
        )
        df_in_system = df_in_system[df_in_system["product_id"].isin(finished_products)]

        if len(df_in_system) == 0:
            return pd.DataFrame(columns=["Product", "Product_type", "Throughput_time", "Start_time", "End_time"])

        result = pd.DataFrame({
            "Product": df_in_system["product_id"].values,
            "Product_type": df_in_system["product_type"].values,
            "Throughput_time": df_in_system["duration"].values,
            "Start_time": df_in_system["t_start"].values,
            "End_time": df_in_system["t_end"].values,
        })
        return result.reset_index(drop=True)

    def aggregated_throughput_time(
        self,
        t_from: float = 0.0,
        t_to: Optional[float] = None,
    ) -> pd.Series:
        """Mean throughput time per product type."""
        df = self.throughput(t_from, t_to)
        if len(df) == 0:
            return pd.Series(dtype=float, name="Throughput_time")
        return df.groupby("Product_type")["Throughput_time"].mean()

    def aggregated_output_and_throughput(
        self,
        t_from: float = 0.0,
        t_to: Optional[float] = None,
    ) -> pd.DataFrame:
        """Output count and throughput rate per product type."""
        df = self.throughput(t_from, t_to)
        if len(df) == 0:
            return pd.DataFrame(columns=["Output", "Throughput"])

        available_time = df["End_time"].max() - df["Start_time"].min()
        df_tp = df.groupby("Product_type")["Product"].count().to_frame()
        df_tp.rename(columns={"Product": "Output"}, inplace=True)
        if available_time > 0:
            df_tp["Throughput"] = df_tp["Output"] / available_time
        else:
            df_tp["Throughput"] = 0.0
        return df_tp

    def aggregated_output(
        self,
        t_from: float = 0.0,
        t_to: Optional[float] = None,
    ) -> pd.Series:
        """Total output per product type."""
        df = self.throughput(t_from, t_to)
        if len(df) == 0:
            return pd.Series(dtype=int, name="Output")
        return df.groupby("Product_type")["Product"].count()

    # ── KPI: Resource states ─────────────────────────────────────────────

    def resource_states(
        self,
        t_from: float = 0.0,
        t_to: Optional[float] = None,
        exclude_resources: Optional[Set[str]] = None,
    ) -> pd.DataFrame:
        """
        Aggregated resource states as percentages.

        Returns DataFrame with columns:
            Resource, Time_type, time_increment, resource_time, percentage
        """
        if t_to is None:
            t_to = self.simulation_end_time

        all_excluded = set(self._exclude_resources)
        if exclude_resources:
            all_excluded.update(exclude_resources)

        df = self.resource_intervals(t_from, t_to)
        if len(df) == 0:
            return pd.DataFrame(columns=["Resource", "Time_type", "time_increment", "resource_time", "percentage"])

        # Exclude source/sink/loading/unloading and configured exclusions
        df = df[df["entity_id"].notna()]
        df = df[~df["entity_id"].isin(all_excluded)]
        df = df[~df["state_type"].isin(_EXCLUDED_STATE_TYPES)]

        if len(df) == 0:
            return pd.DataFrame(columns=["Resource", "Time_type", "time_increment", "resource_time", "percentage"])

        # Clip intervals to the query window
        df = df.copy()
        df["clipped_start"] = df["t_start"].clip(lower=t_from)
        df["clipped_end"] = df["t_end"].clip(upper=t_to)
        df["clipped_duration"] = (df["clipped_end"] - df["clipped_start"]).clip(lower=0.0)

        # Map state_type → Time_type
        df["Time_type"] = df["state_type"].map(_STATE_TO_TIME_TYPE)
        df = df[df["Time_type"].notna()]

        # Handle NS/UD overlap: UD takes priority over NS
        df = self._resolve_ns_ud_overlap(df, t_from, t_to)

        # Sum duration per (resource, time_type)
        resource_time = t_to - t_from
        grouped = (
            df.groupby(["entity_id", "Time_type"])["clipped_duration"]
            .sum()
            .reset_index()
            .rename(columns={"entity_id": "Resource", "clipped_duration": "time_increment"})
        )

        # Add standby: resource_time minus sum of all other states
        all_resources = df["entity_id"].unique()
        rows = []
        for res in all_resources:
            res_data = grouped[grouped["Resource"] == res]
            total_active = res_data["time_increment"].sum()
            standby_time = max(0.0, resource_time - total_active)
            rows.append({
                "Resource": res,
                "Time_type": "SB",
                "time_increment": standby_time,
            })

        if rows:
            df_sb = pd.DataFrame(rows)
            grouped = pd.concat([grouped, df_sb], ignore_index=True)

        # Remove zero-duration rows
        grouped = grouped[grouped["time_increment"] > 1e-10].copy()

        grouped["resource_time"] = resource_time
        grouped["percentage"] = (grouped["time_increment"] / resource_time * 100)

        return grouped[["Resource", "Time_type", "time_increment", "resource_time", "percentage"]].reset_index(drop=True)

    def _resolve_ns_ud_overlap(self, df: pd.DataFrame, t_from: float, t_to: float) -> pd.DataFrame:
        """
        Resolve overlap between NonScheduled and Breakdown intervals.
        UD takes priority: NS duration is reduced by any UD overlap.
        Non-NS/UD states have their duration reduced by any NS overlap.

        Vectorized: uses a cross-join within each resource group instead of
        row-by-row Python iteration, eliminating O(N × resources) Python overhead.
        """
        ns_mask = df["Time_type"] == "NS"

        if not ns_mask.any():
            return df

        resources_with_ns = df.loc[ns_mask, "entity_id"].unique()
        has_ns_mask = df["entity_id"].isin(resources_with_ns)

        pass_through = df[~has_ns_mask].copy()
        res_df = df[has_ns_mask].copy()

        if len(res_df) == 0:
            return pass_through

        ns_rows = res_df[res_df["Time_type"] == "NS"].copy()
        ud_rows = res_df[res_df["Time_type"] == "UD"].copy()
        other_rows = res_df[(res_df["Time_type"] != "NS") & (res_df["Time_type"] != "UD")].copy()

        # NS rows: subtract overlap with (merged) UD intervals of same resource
        if len(ns_rows) > 0 and len(ud_rows) > 0:
            overlap = _compute_row_overlap_vectorized(ns_rows, ud_rows)
            ns_rows["clipped_duration"] = (ns_rows["clipped_duration"] - overlap).clip(lower=0.0)

        # Other rows: subtract overlap with (merged) NS intervals of same resource
        if len(other_rows) > 0 and len(ns_rows) > 0:
            overlap = _compute_row_overlap_vectorized(other_rows, ns_rows)
            other_rows["clipped_duration"] = (other_rows["clipped_duration"] - overlap).clip(lower=0.0)

        parts = [pass_through, ns_rows, ud_rows, other_rows]
        non_empty = [p for p in parts if len(p) > 0]
        if not non_empty:
            return df.iloc[0:0]
        return pd.concat(non_empty, ignore_index=True)

    def resource_states_by_interval(
        self,
        interval_minutes: float,
        t_from: float = 0.0,
        t_to: Optional[float] = None,
        exclude_resources: Optional[Set[str]] = None,
    ) -> pd.DataFrame:
        """
        Resource states aggregated by time intervals.

        Returns DataFrame with columns:
            Resource, Interval_start, Interval_end, Time_type,
            time_increment, interval_time, percentage
        """
        if t_to is None:
            t_to = self.simulation_end_time

        all_excluded = set(self._exclude_resources)
        if exclude_resources:
            all_excluded.update(exclude_resources)

        df = self.resource_intervals(t_from, t_to)
        if len(df) == 0:
            return pd.DataFrame(columns=[
                "Resource", "Interval_start", "Interval_end", "Time_type",
                "time_increment", "interval_time", "percentage",
            ])

        df = df[~df["entity_id"].isin(all_excluded)]
        df = df[~df["state_type"].isin(_EXCLUDED_STATE_TYPES)]

        if len(df) == 0:
            return pd.DataFrame(columns=[
                "Resource", "Interval_start", "Interval_end", "Time_type",
                "time_increment", "interval_time", "percentage",
            ])

        df = df.copy()
        df["Time_type"] = df["state_type"].map(_STATE_TO_TIME_TYPE)
        df = df[df["Time_type"].notna()].reset_index(drop=True)

        if len(df) == 0:
            return pd.DataFrame(columns=[
                "Resource", "Interval_start", "Interval_end", "Time_type",
                "time_increment", "interval_time", "percentage",
            ])

        # Vectorised interval-to-bucket splitting (replaces Python iterrows loop).
        iv_idx, bucket_nums, b_start, b_end, clipped = _split_intervals_to_buckets(
            df["t_start"].values, df["t_end"].values, t_from, t_to, interval_minutes
        )

        if len(iv_idx) == 0:
            return pd.DataFrame(columns=[
                "Resource", "Interval_start", "Interval_end", "Time_type",
                "time_increment", "interval_time", "percentage",
            ])

        result = pd.DataFrame({
            "Resource":       df["entity_id"].values[iv_idx],
            "Interval_start": b_start,
            "Interval_end":   b_end,
            "Time_type":      df["Time_type"].values[iv_idx],
            "time_increment": clipped,
        })

        result = result.groupby(
            ["Resource", "Interval_start", "Interval_end", "Time_type"],
            as_index=False,
        )["time_increment"].sum()

        result["interval_time"] = result["Interval_end"] - result["Interval_start"]
        result["percentage"] = (result["time_increment"] / result["interval_time"] * 100).clip(0, 100)

        return result.reset_index(drop=True)

    # ── KPI: Scrap ───────────────────────────────────────────────────────

    def scrap_per_product_type(
        self,
        t_from: float = 0.0,
        t_to: Optional[float] = None,
        primitive_types: Optional[Set[str]] = None,
    ) -> pd.DataFrame:
        """
        Scrap rate per product type.

        Returns DataFrame with columns:
            Product_type, Scrap_count, Total_count, Scrap_rate
        """
        df = self.resource_intervals(t_from, t_to)
        prod_end = df[
            (df["state_type"] == StateTypeEnum.production.value)
            & (~df["interrupted"])
            & (df["product_id"].notna())
        ].copy()

        if primitive_types:
            prod_end = prod_end[~prod_end["product_type"].isin(primitive_types)]

        if len(prod_end) == 0:
            return pd.DataFrame(columns=["Product_type", "Scrap_count", "Total_count", "Scrap_rate"])

        ok_col = prod_end["process_ok"].copy()
        ok_col = ok_col.where(ok_col.notna(), True)
        prod_end["_ok"] = ok_col.astype(bool)

        total = prod_end.groupby("product_type").size().reset_index(name="Total_count")
        failed = prod_end[~prod_end["_ok"]].groupby("product_type").size().reset_index(name="Scrap_count")

        result = pd.merge(total, failed, on="product_type", how="left")
        result["Scrap_count"] = result["Scrap_count"].fillna(0).astype(int)
        result["Scrap_rate"] = (result["Scrap_count"] / result["Total_count"] * 100).round(2)
        result = result.rename(columns={"product_type": "Product_type"})

        return result[["Product_type", "Scrap_count", "Total_count", "Scrap_rate"]].reset_index(drop=True)

    def scrap_per_resource(
        self,
        t_from: float = 0.0,
        t_to: Optional[float] = None,
    ) -> pd.DataFrame:
        """
        Scrap rate per resource.

        Returns DataFrame with columns:
            Resource, Scrap_count, Total_count, Scrap_rate
        """
        df = self.resource_intervals(t_from, t_to)
        prod_end = df[
            (df["state_type"] == StateTypeEnum.production.value)
            & (~df["interrupted"])
            & (df["entity_id"].notna())
            & (~df["entity_id"].isin(self._exclude_resources))
        ].copy()

        if len(prod_end) == 0:
            return pd.DataFrame(columns=["Resource", "Scrap_count", "Total_count", "Scrap_rate"])

        ok_col = prod_end["process_ok"].copy()
        ok_col = ok_col.where(ok_col.notna(), True)
        prod_end["_ok"] = ok_col.astype(bool)

        total = prod_end.groupby("entity_id").size().reset_index(name="Total_count")
        failed = prod_end[~prod_end["_ok"]].groupby("entity_id").size().reset_index(name="Scrap_count")

        result = pd.merge(total, failed, on="entity_id", how="left")
        result["Scrap_count"] = result["Scrap_count"].fillna(0).astype(int)
        result["Scrap_rate"] = (result["Scrap_count"] / result["Total_count"] * 100).round(2)
        result = result.rename(columns={"entity_id": "Resource"})

        return result[["Resource", "Scrap_count", "Total_count", "Scrap_rate"]].reset_index(drop=True)

    # ── KPI: Production flow ratio ───────────────────────────────────────

    def production_flow_ratio(
        self,
        t_from: float = 0.0,
        t_to: Optional[float] = None,
    ) -> pd.DataFrame:
        """
        Production flow ratio per product type.

        Returns DataFrame with columns:
            Product_type, Production, Transport, Idle
        (values as percentages of throughput time)
        """
        df_tpt = self.throughput(t_from, t_to)
        if len(df_tpt) == 0:
            return pd.DataFrame(columns=["Product_type", "Production ", "Transport ", "Idle "])

        ri = self.resource_intervals(t_from, t_to)

        # Get finished products
        finished_products = set(df_tpt["Product"].unique())

        # Production time per product
        prod_intervals = ri[
            (ri["state_type"] == StateTypeEnum.production.value)
            & (ri["product_id"].isin(finished_products))
            & (~ri["interrupted"])
        ]
        prod_time = prod_intervals.groupby("product_id")["duration"].sum().reset_index()
        prod_time.columns = ["Product", "Production Time"]

        # Transport time per product
        trans_intervals = ri[
            (ri["state_type"] == StateTypeEnum.transport.value)
            & (ri["product_id"].isin(finished_products))
            & (~ri["interrupted"])
        ]
        trans_time = trans_intervals.groupby("product_id")["duration"].sum().reset_index()
        trans_time.columns = ["Product", "Transport Time"]

        # Also add interrupted segments back (their net productive time)
        prod_interrupted = ri[
            (ri["state_type"] == StateTypeEnum.production.value)
            & (ri["product_id"].isin(finished_products))
            & (ri["interrupted"])
        ]
        if len(prod_interrupted) > 0:
            prod_int_time = prod_interrupted.groupby("product_id")["duration"].sum().reset_index()
            prod_int_time.columns = ["Product", "Production Time"]
            prod_time = pd.concat([prod_time, prod_int_time]).groupby("Product", as_index=False).sum()

        trans_interrupted = ri[
            (ri["state_type"] == StateTypeEnum.transport.value)
            & (ri["product_id"].isin(finished_products))
            & (ri["interrupted"])
        ]
        if len(trans_interrupted) > 0:
            trans_int_time = trans_interrupted.groupby("product_id")["duration"].sum().reset_index()
            trans_int_time.columns = ["Product", "Transport Time"]
            trans_time = pd.concat([trans_time, trans_int_time]).groupby("Product", as_index=False).sum()

        # Merge with throughput data
        merged = df_tpt[["Product", "Product_type", "Throughput_time"]].copy()
        merged = pd.merge(merged, prod_time, on="Product", how="left")
        merged = pd.merge(merged, trans_time, on="Product", how="left")
        merged["Production Time"] = merged["Production Time"].fillna(0)
        merged["Transport Time"] = merged["Transport Time"].fillna(0)
        merged["Idle Time"] = merged["Throughput_time"] - merged["Production Time"] - merged["Transport Time"]

        # Aggregate by product type (mean)
        agg = merged.groupby("Product_type")[["Production Time", "Transport Time", "Idle Time", "Throughput_time"]].mean()

        result = pd.DataFrame({
            "Product_type": agg.index,
            "Production ": (agg["Production Time"] / agg["Throughput_time"] * 100).values,
            "Transport ": (agg["Transport Time"] / agg["Throughput_time"] * 100).values,
            "Idle ": (agg["Idle Time"] / agg["Throughput_time"] * 100).values,
        })

        return result.reset_index(drop=True)

    # ── KPI: WIP ─────────────────────────────────────────────────────────

    def wip(
        self,
        t_from: float = 0.0,
        t_to: Optional[float] = None,
    ) -> pd.DataFrame:
        """
        System WIP over time.

        Returns DataFrame with columns: Time, WIP, WIP_Increment, Product_type
        """
        df = self.product_intervals(t_from, t_to)

        created = df[df["state_type"] == "created_product"][["product_id", "product_type", "t_start"]].copy()
        created.columns = ["Product", "Product_type", "Time"]
        created["WIP_Increment"] = 1

        finished = df[df["state_type"].isin(["finished_product", "consumed_product"])][["product_id", "product_type", "t_start"]].copy()
        finished.columns = ["Product", "Product_type", "Time"]
        finished["WIP_Increment"] = -1

        events = pd.concat([created, finished], ignore_index=True)
        events = events.sort_values("Time").reset_index(drop=True)

        if len(events) == 0:
            return pd.DataFrame(columns=["Time", "WIP", "WIP_Increment", "Product_type"])

        events["WIP"] = events["WIP_Increment"].cumsum().clip(lower=0).astype(float)
        return events[["Time", "WIP", "WIP_Increment", "Product_type", "Product"]].reset_index(drop=True)

    def aggregated_wip(
        self,
        t_from: float = 0.0,
        t_to: Optional[float] = None,
    ) -> pd.Series:
        """Mean WIP per product type (plus Total)."""
        df = self.wip(t_from, t_to)
        if len(df) == 0:
            return pd.Series(dtype=float, name="WIP")

        # Per product type
        results = {}
        for pt in df["Product_type"].dropna().unique():
            pt_df = df[df["Product_type"] == pt].copy()
            pt_df["WIP_pt"] = pt_df["WIP_Increment"].cumsum().clip(lower=0).astype(float)
            results[pt] = pt_df["WIP_pt"].mean()

        # Total
        results["Total"] = df["WIP"].mean()

        return pd.Series(results, name="WIP")

    # ── KPI: OEE ─────────────────────────────────────────────────────────

    def oee_per_resource(
        self,
        t_from: float = 0.0,
        t_to: Optional[float] = None,
    ) -> pd.DataFrame:
        """
        OEE per resource: Availability × Performance × Quality.

        Availability = (PR + ST + DP) / (Total - NS)
          For transport resources: includes SB in numerator.
        Performance = Total Ideal Time / Total Actual Time
          Requires production_system_data for ideal cycle times.
          Transport resources default to 100%.
        Quality = 1 - (scrap_rate / 100)

        Returns DataFrame with columns:
            Resource, Availability, Performance, Quality, OEE
        """
        rs = self.resource_states(t_from, t_to)
        if len(rs) == 0:
            return pd.DataFrame(columns=["Resource", "Availability", "Performance", "Quality", "OEE"])

        transport_ids = self._get_transport_resource_ids()
        process_ideal_times, resource_capacities, resource_process_caps = self._get_process_metadata()

        scrap_df = self.scrap_per_resource(t_from, t_to)
        scrap_rates = dict(zip(scrap_df["Resource"], scrap_df["Scrap_rate"])) if len(scrap_df) > 0 else {}

        results = []
        for resource in rs["Resource"].unique():
            res_data = rs[rs["Resource"] == resource].set_index("Time_type")
            time_by_type = res_data["time_increment"].to_dict()
            resource_time = res_data["resource_time"].iloc[0]

            pr_time = time_by_type.get("PR", 0)
            st_time = time_by_type.get("ST", 0)
            dp_time = time_by_type.get("DP", 0)
            sb_time = time_by_type.get("SB", 0)
            ns_time = time_by_type.get("NS", 0)
            is_transport = resource in transport_ids

            capacity = resource_capacities.get(resource, 1)
            scheduled_time = (resource_time - ns_time) * capacity
            if scheduled_time > 0:
                if is_transport:
                    availability = (pr_time + st_time + dp_time + sb_time) / scheduled_time
                else:
                    availability = (pr_time + st_time + dp_time) / scheduled_time
            else:
                availability = 0.0

            if is_transport or self.production_system_data is None:
                performance = 1.0
            else:
                performance = self._compute_performance(
                    resource, t_from, t_to, pr_time,
                    process_ideal_times, resource_capacities, resource_process_caps,
                )

            scrap_rate = scrap_rates.get(resource, 0)
            quality = 1 - (scrap_rate / 100)

            oee = availability * performance * quality
            results.append({
                "Resource": resource,
                "Availability": round(availability * 100, 2),
                "Performance": round(performance * 100, 2),
                "Quality": round(quality * 100, 2),
                "OEE": round(oee * 100, 2),
            })

        return pd.DataFrame(results)

    def oee_production_system(
        self,
        t_from: float = 0.0,
        t_to: Optional[float] = None,
    ) -> pd.DataFrame:
        """
        System-level OEE as weighted average of resource-level OEEs.

        Returns DataFrame with columns: KPI, Value
        """
        df_oee = self.oee_per_resource(t_from, t_to)
        if len(df_oee) == 0:
            return pd.DataFrame({
                "KPI": ["Availability", "Performance", "Quality", "OEE"],
                "Value": [100.0, 100.0, 100.0, 100.0],
            })

        rs = self.resource_states(t_from, t_to)
        _, resource_capacities, _ = self._get_process_metadata()
        resource_weights = {}
        for resource in rs["Resource"].unique():
            res_data = rs[rs["Resource"] == resource].set_index("Time_type")
            resource_time = res_data["resource_time"].iloc[0]
            ns_time = res_data["time_increment"].to_dict().get("NS", 0)
            capacity = resource_capacities.get(resource, 1)
            resource_weights[resource] = (resource_time - ns_time) * capacity

        total_weight = sum(resource_weights.values())
        if total_weight > 0:
            availability = sum(
                (row["Availability"] / 100.0) * resource_weights.get(row["Resource"], 0)
                for _, row in df_oee.iterrows()
            ) / total_weight
        else:
            availability = df_oee["Availability"].mean() / 100.0

        if self.production_system_data is None:
            performance = 1.0
        else:
            total_time = self.simulation_end_time
            from prodsys.factories.time_model_factory import TimeModelFactory
            time_model_factory = TimeModelFactory()
            time_model_factory.create_time_models(self.production_system_data)

            expected_output = 0.0
            for source_data in self.production_system_data.source_data:
                try:
                    time_model = time_model_factory.get_time_model(source_data.time_model_id)
                    from prodsys.simulation.time_model import ScheduledTimeModel
                    if isinstance(time_model, ScheduledTimeModel):
                        schedule = time_model.data.schedule
                        if time_model.data.absolute:
                            expected_output += len([t for t in schedule if t <= total_time])
                        else:
                            cumulative = 0.0
                            for interval in schedule:
                                cumulative += interval
                                if cumulative <= total_time:
                                    expected_output += 1
                                else:
                                    break
                    else:
                        eit = time_model.get_expected_time()
                        if eit > 0:
                            expected_output += total_time / eit
                except (ValueError, TypeError, AttributeError):
                    continue

            actual_output = self.aggregated_output(t_from, t_to).sum()
            performance = (actual_output / expected_output) if expected_output > 0 else 1.0

        df_output = self.aggregated_output_and_throughput(t_from, t_to)
        total_units = df_output["Output"].sum() if len(df_output) > 0 else 0
        if total_units > 0:
            scrap = self.scrap_per_product_type(t_from, t_to)
            if len(scrap) > 0:
                total_scrap = (scrap["Scrap_count"]).sum()
                quality = (total_units - total_scrap) / total_units
            else:
                quality = 1.0
        else:
            quality = 1.0

        oee = availability * performance * quality
        return pd.DataFrame({
            "KPI": ["Availability", "Performance", "Quality", "OEE"],
            "Value": [
                round(availability * 100, 2),
                round(performance * 100, 2),
                round(quality * 100, 2),
                round(oee * 100, 2),
            ],
        })

    def _get_transport_resource_ids(self) -> set:
        if self.production_system_data is None:
            return set()
        try:
            from prodsys.models.production_system_data import get_transport_resources
            return {r.ID for r in get_transport_resources(self.production_system_data)}
        except (ImportError, AttributeError):
            return set()

    def _get_process_metadata(self) -> tuple[dict, dict, dict]:
        """Returns (process_ideal_times, resource_capacities, resource_process_capacities)."""
        process_ideal_times: dict[str, float] = {}
        resource_capacities: dict[str, int] = {}
        resource_process_caps: dict[str, dict[str, int]] = {}

        if self.production_system_data is None:
            return process_ideal_times, resource_capacities, resource_process_caps

        from prodsys.factories.time_model_factory import TimeModelFactory
        tmf = TimeModelFactory()
        tmf.create_time_models(self.production_system_data)

        for proc in self.production_system_data.process_data:
            if hasattr(proc, "time_model_id"):
                try:
                    tm = tmf.get_time_model(proc.time_model_id)
                    ict = tm.get_expected_time()
                    if ict > 0:
                        process_ideal_times[proc.ID] = ict
                except (ValueError, TypeError):
                    pass

        for res in self.production_system_data.resource_data:
            resource_capacities[res.ID] = getattr(res, "capacity", 1) or 1
            if hasattr(res, "process_capacities") and res.process_capacities and hasattr(res, "process_ids"):
                rpc = {}
                for i, pid in enumerate(res.process_ids):
                    if i < len(res.process_capacities):
                        rpc[pid] = res.process_capacities[i]
                resource_process_caps[res.ID] = rpc

        return process_ideal_times, resource_capacities, resource_process_caps

    def oee_per_resource_by_interval(
        self,
        interval_minutes: float,
        t_from: float = 0.0,
        t_to: Optional[float] = None,
    ) -> pd.DataFrame:
        """
        OEE per resource aggregated by time intervals.

        Returns DataFrame with columns:
            Resource, Interval_start, Interval_end, Availability,
            Performance, Quality, OEE
        """
        rs = self.resource_states_by_interval(interval_minutes, t_from, t_to)
        if len(rs) == 0:
            return pd.DataFrame(columns=[
                "Resource", "Interval_start", "Interval_end",
                "Availability", "Performance", "Quality", "OEE",
            ])

        transport_ids = self._get_transport_resource_ids()
        process_ideal_times, resource_capacities, resource_process_caps = self._get_process_metadata()

        scrap_df = self.scrap_per_resource(t_from, t_to)
        scrap_rates = dict(zip(scrap_df["Resource"], scrap_df["Scrap_rate"])) if len(scrap_df) > 0 else {}

        pivot = rs.pivot_table(
            index=["Resource", "Interval_start", "Interval_end"],
            columns="Time_type",
            values="time_increment",
            fill_value=0,
        ).reset_index()

        for col in ("PR", "ST", "DP", "SB", "NS", "UD", "CR"):
            if col not in pivot.columns:
                pivot[col] = 0.0

        pivot["interval_time"] = pivot["Interval_end"] - pivot["Interval_start"]
        pivot["_capacity"] = pivot["Resource"].map(resource_capacities).fillna(1).astype(int)
        pivot["scheduled_time"] = (pivot["interval_time"] - pivot["NS"]) * pivot["_capacity"]

        is_transport = pivot["Resource"].isin(transport_ids)
        avail_num = np.where(
            is_transport,
            pivot["PR"] + pivot["ST"] + pivot["DP"] + pivot["SB"],
            pivot["PR"] + pivot["ST"] + pivot["DP"],
        )
        pivot["availability"] = np.where(
            pivot["scheduled_time"] > 0,
            avail_num / pivot["scheduled_time"],
            0.0,
        )

        # Performance per interval — fully vectorised (no Python loop per bucket).
        #
        # Strategy:
        #   1. Pull all non-transport production intervals once from the full window.
        #   2. Split each interval across bucket boundaries (same numpy ragged-repeat
        #      technique used by resource_states_by_interval).
        #   3. Compute ideal-time contribution for every segment in bulk:
        #        • state_id unknown           → neutral credit (clipped duration)
        #        • resumed-tail (actual < 80% of ideal lot time) → neutral credit
        #        • genuine lot               → full_lot_ideal × (clipped / actual)
        #      Note: full_lot_ideal = process_ideal_times[sid] because the capacity
        #      factor pc cancels: ideal_per_unit = ideal/pc, full = ideal_per_unit×pc.
        #   4. groupby(resource, bucket) → total_actual and total_ideal per bucket.
        #   5. performance = total_ideal / total_actual; default 1.0 where no data.
        if self.production_system_data is not None and len(process_ideal_times) > 0:
            ri_all = self.resource_intervals(t_from, t_to)
            prod_all = ri_all[
                (ri_all["state_type"] == StateTypeEnum.production.value)
                & (~ri_all["interrupted"])
                & (~ri_all["entity_id"].isin(transport_ids))
            ].reset_index(drop=True)

            if len(prod_all) > 0:
                p_t_s   = prod_all["t_start"].values
                p_t_e   = prod_all["t_end"].values
                p_dur   = prod_all["duration"].values
                p_res   = prod_all["entity_id"].values
                p_sid   = prod_all["state_id"].values

                # Lookup ideal lot time per row (0.0 when state_id not known)
                p_ideal = np.array([process_ideal_times.get(s, 0.0) for s in p_sid])
                # Resumed-tail flag: actual duration < 80 % of ideal lot time
                p_tail  = (p_ideal > 0) & (p_dur < p_ideal * 0.80)

                # Vectorised bucket splitting
                iv_idx, bucket_nums, b_start_p, _, clipped_p = _split_intervals_to_buckets(
                    p_t_s, p_t_e, t_from, t_to if t_to is not None else self.simulation_end_time, interval_minutes
                )

                if len(iv_idx) > 0:
                    dur_seg   = p_dur[iv_idx]
                    ideal_seg = p_ideal[iv_idx]
                    tail_seg  = p_tail[iv_idx]

                    # Proportional ideal contribution per segment:
                    #   unknown state → neutral (clipped)
                    #   resumed tail  → neutral (clipped)
                    #   genuine lot   → full_lot_ideal × clipped / actual
                    proportion = np.where(dur_seg > 0, clipped_p / dur_seg, 0.0)
                    ideal_contrib = np.where(
                        ideal_seg <= 0,
                        clipped_p,                      # state_id not in model
                        np.where(
                            tail_seg,
                            clipped_p,                  # resumed-tail: neutral credit
                            ideal_seg * proportion,     # genuine lot: proportional
                        ),
                    )

                    perf_df = pd.DataFrame({
                        "Resource":       p_res[iv_idx],
                        "Interval_start": b_start_p,
                        "actual":         clipped_p,
                        "ideal":          ideal_contrib,
                    })
                    perf_grouped = (
                        perf_df
                        .groupby(["Resource", "Interval_start"], as_index=False)
                        .agg(total_actual=("actual", "sum"), total_ideal=("ideal", "sum"))
                    )
                    perf_grouped["performance"] = np.where(
                        (perf_grouped["total_actual"] > 0) & (perf_grouped["total_ideal"] > 0),
                        perf_grouped["total_ideal"] / perf_grouped["total_actual"],
                        1.0,
                    )
                    pivot = pivot.merge(
                        perf_grouped[["Resource", "Interval_start", "performance"]],
                        on=["Resource", "Interval_start"],
                        how="left",
                    )
                    pivot["performance"] = pivot["performance"].fillna(1.0)
                else:
                    pivot["performance"] = 1.0
            else:
                pivot["performance"] = 1.0
        else:
            pivot["performance"] = 1.0

        pivot["scrap_rate"] = pivot["Resource"].map(scrap_rates).fillna(0)
        pivot["quality"] = 1 - (pivot["scrap_rate"] / 100)
        pivot["oee"] = pivot["availability"] * pivot["performance"] * pivot["quality"]

        return pd.DataFrame({
            "Resource": pivot["Resource"],
            "Interval_start": pivot["Interval_start"],
            "Interval_end": pivot["Interval_end"],
            "Availability": (pivot["availability"] * 100).round(2),
            "Performance": (pivot["performance"] * 100).round(2),
            "Quality": (pivot["quality"] * 100).round(2),
            "OEE": (pivot["oee"] * 100).round(2),
        }).reset_index(drop=True)

    def _compute_performance(
        self,
        resource: str,
        t_from: float,
        t_to: Optional[float],
        pr_time: float,
        process_ideal_times: dict,
        resource_capacities: dict,
        resource_process_caps: dict,
    ) -> float:
        ri = self.resource_intervals(t_from, t_to, resource=resource)
        prod = ri[
            (ri["state_type"] == StateTypeEnum.production.value)
            & (~ri["interrupted"])
        ]
        if len(prod) == 0:
            return 0.0

        durations  = prod["duration"].values
        state_ids  = prod["state_id"].values
        valid      = durations > 0
        total_actual = float(durations[valid].sum())

        # Vectorised ideal-time sum.
        # full_lot_ideal = process_ideal_times[sid] because pc cancels:
        #   ideal_per_unit = ideal/pc  →  ideal_per_unit × pc = ideal.
        # When state_id is unknown, fall back to the actual duration (neutral).
        ideal_times = np.array([process_ideal_times.get(s, 0.0) for s in state_ids[valid]])
        dur_valid   = durations[valid]
        total_ideal = float(np.where(ideal_times > 0, ideal_times, dur_valid).sum())

        if total_actual > 0 and total_ideal > 0:
            return total_ideal / total_actual
        elif pr_time > 0 and total_ideal > 0:
            return total_ideal / pr_time
        return 0.0


# ── Helper functions ─────────────────────────────────────────────────────

def _split_intervals_to_buckets(
    t_start: np.ndarray,
    t_end: np.ndarray,
    t_from: float,
    t_to: float,
    bucket_size: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Vectorised interval-to-fixed-bucket splitting using the numpy ragged-repeat
    pattern.  No Python loops — O(total_segments) in pure numpy.

    For every input interval that overlaps the query window [t_from, t_to] and
    at least one bucket boundary, emits one output row per overlapping bucket.

    Parameters
    ----------
    t_start, t_end : numpy arrays of interval start / end times.
    t_from, t_to   : query window boundaries.
    bucket_size    : width of each bucket in the same time unit.

    Returns
    -------
    iv_idx      : index into the *input* arrays for each output segment.
    bucket_nums : zero-based bucket index for each output segment.
    b_start     : bucket start time for each output segment.
    b_end       : bucket end time  for each output segment (capped at t_to).
    clipped     : duration of the segment's overlap with its bucket (> 0 always).
    """
    n = len(t_start)
    if n == 0:
        empty_i = np.empty(0, dtype=np.int64)
        empty_f = np.empty(0, dtype=np.float64)
        return empty_i, empty_i, empty_f, empty_f, empty_f

    eff_start = np.maximum(t_start, t_from)
    eff_end   = np.minimum(t_end,   t_to)

    first_bkt = np.floor((eff_start - t_from) / bucket_size).astype(np.int64)
    last_bkt  = np.ceil((eff_end    - t_from) / bucket_size).astype(np.int64)  # exclusive
    n_segs    = np.maximum(last_bkt - first_bkt, 0)

    valid = n_segs > 0
    if not valid.any():
        empty_i = np.empty(0, dtype=np.int64)
        empty_f = np.empty(0, dtype=np.float64)
        return empty_i, empty_i, empty_f, empty_f, empty_f

    orig_idx    = np.where(valid)[0]          # positions in the input arrays
    n_segs_v    = n_segs[valid]
    first_bkt_v = first_bkt[valid]
    t_s_v       = t_start[valid]
    t_e_v       = t_end[valid]

    total = int(n_segs_v.sum())

    # Ragged-repeat trick: generate local offsets [0..n_segs[i]-1] for every i
    # without any Python-level loop.
    cumsum_v   = np.concatenate([[0], np.cumsum(n_segs_v[:-1])])
    row_idx    = np.arange(total)
    resets     = np.repeat(cumsum_v, n_segs_v)
    local_off  = row_idx - resets                              # offset within each interval's range

    bucket_nums  = np.repeat(first_bkt_v, n_segs_v) + local_off
    iv_local_idx = np.repeat(np.arange(len(orig_idx)), n_segs_v)  # index into valid subset

    b_start = t_from + bucket_nums * bucket_size
    b_end   = np.minimum(t_from + (bucket_nums + 1) * bucket_size, t_to)

    seg_start = np.maximum(t_s_v[iv_local_idx], b_start)
    seg_end   = np.minimum(t_e_v[iv_local_idx], b_end)
    clipped   = np.maximum(0.0, seg_end - seg_start)

    # Discard zero-duration segments (rare, but possible at exact boundaries)
    pos = clipped > 0
    iv_idx = orig_idx[iv_local_idx[pos]]  # map back to original input indices

    return iv_idx, bucket_nums[pos], b_start[pos], b_end[pos], clipped[pos]


def _compute_row_overlap_vectorized(rows: pd.DataFrame, ref: pd.DataFrame) -> pd.Series:
    """
    For each row in `rows`, compute the total overlap duration with all intervals
    in `ref` (merged per entity_id to avoid double-counting) sharing the same
    entity_id.

    Uses a NumPy cross-join within entity groups — fully vectorised, no Python
    row iteration.  Returns a Series with the same index as `rows`.
    """
    if len(rows) == 0 or len(ref) == 0:
        return pd.Series(0.0, index=rows.index)

    # Merge ref intervals per resource so overlapping ref intervals are not
    # double-counted (e.g. two UD intervals that overlap each other).
    merged_ref_list: list[dict] = []
    for resource, group in ref.groupby("entity_id", sort=False):
        for s, e in _merge_intervals(group[["clipped_start", "clipped_end"]].values.tolist()):
            merged_ref_list.append({"entity_id": resource, "ref_start": s, "ref_end": e})

    if not merged_ref_list:
        return pd.Series(0.0, index=rows.index)

    ref_merged = pd.DataFrame(merged_ref_list)

    # Attach a positional key so we can group-sum back to the original rows.
    rows_keyed = rows[["entity_id", "clipped_start", "clipped_end"]].copy()
    rows_keyed["_pos"] = np.arange(len(rows_keyed))

    # Cross-join within entity_id
    joined = rows_keyed.merge(ref_merged, on="entity_id")

    # Vectorised overlap arithmetic
    ol_start = np.maximum(joined["clipped_start"].values, joined["ref_start"].values)
    ol_end = np.minimum(joined["clipped_end"].values, joined["ref_end"].values)
    joined["_ol"] = np.maximum(0.0, ol_end - ol_start)

    overlap_sums = joined.groupby("_pos")["_ol"].sum()

    result = pd.Series(0.0, index=rows.index)
    result.iloc[overlap_sums.index.to_numpy()] = overlap_sums.to_numpy()
    return result


def _merge_intervals(intervals: list[list | tuple]) -> list[tuple[float, float]]:
    """Merge overlapping intervals into non-overlapping set."""
    if not intervals:
        return []
    sorted_iv = sorted(intervals, key=lambda x: x[0])
    merged = [list(sorted_iv[0])]
    for start, end in sorted_iv[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(s, e) for s, e in merged]


def _overlap_duration(
    intervals_a: list[list | tuple],
    intervals_b: list[tuple[float, float]],
) -> float:
    """Calculate total overlap duration between two sets of intervals."""
    total = 0.0
    for a_start, a_end in intervals_a:
        for b_start, b_end in intervals_b:
            overlap_start = max(a_start, b_start)
            overlap_end = min(a_end, b_end)
            if overlap_start < overlap_end:
                total += overlap_end - overlap_start
    return total
