"""
Analytics module: Incremental, interval-queryable KPI pipeline.

Provides an interval-based architecture that supports efficient interval queries
and cheap event appends. All KPIs are computed from closed intervals built by
the IntervalBuilder pairing state machine.

Usage::

    from prodsys.analytics import AnalyticsStore

    store = AnalyticsStore.from_raw(df_raw, time_range=1000)
    print(store.throughput())
    print(store.resource_states())
    print(store.oee_per_resource())
"""

from prodsys.analytics.intervals import IntervalBuilder
from prodsys.analytics.store import AnalyticsStore
from prodsys.analytics.warm_up import detect_warm_up

__all__ = [
    "IntervalBuilder",
    "AnalyticsStore",
    "detect_warm_up",
]
