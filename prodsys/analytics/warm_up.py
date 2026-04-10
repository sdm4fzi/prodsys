"""
Warm-up detection operating on bucketed KPI series.

Warm-up is a query parameter, not a preprocessing phase:
  t_from = detect_warm_up(store)
  store.resource_states(t_from=t_from)
"""

from __future__ import annotations

from typing import Optional, Literal

import numpy as np

from prodsys.analytics.store import AnalyticsStore


def detect_warm_up(
    store: AnalyticsStore,
    method: Optional[Literal["mser5", "threshold_stabilization", "static_ratio"]] = None,
) -> float:
    """
    Detect the warm-up cutoff time from throughput data.

    Returns the simulation time after which the system is in steady state.
    """
    if method is None:
        return 0.0

    df = store.throughput()
    if len(df) == 0:
        return 0.0

    df = df.sort_values("Start_time").reset_index(drop=True)
    values = df["Throughput_time"].values

    if method == "mser5":
        idx = _mser5(values)
    elif method == "threshold_stabilization":
        idx = _threshold_stabilization(values)
    elif method == "static_ratio":
        idx = int(len(values) * 0.15)
    else:
        raise ValueError(f"Unknown warm-up method: {method}")

    if idx >= len(df):
        return 0.0

    return float(df.iloc[idx]["Start_time"])


def _mser5(values: np.ndarray) -> int:
    n = len(values)
    if n < 5:
        return n

    batched_data = [
        values[i:i + 5] for i in range(0, n, 5) if len(values[i:i + 5]) == 5
    ]
    batch_means = np.array([np.mean(b) for b in batched_data])

    min_std_error = float("inf")
    optimal_index = None

    for i in range(len(batch_means)):
        truncated = batch_means[i:]
        std_error = np.std(truncated) / np.sqrt(len(truncated))
        if std_error < min_std_error:
            min_std_error = std_error
            optimal_index = i * 5

    if optimal_index is None or optimal_index == (len(batch_means) - 1) * 5:
        return n
    return optimal_index


def _threshold_stabilization(values: np.ndarray) -> int:
    cumulative_avg = np.cumsum(values) / np.arange(1, len(values) + 1)
    moving_range = np.abs(np.diff(cumulative_avg))
    threshold = np.mean(moving_range) / 10

    for i in range(1, len(moving_range)):
        if all(moving_range[i:] < threshold):
            return i

    return len(values)
