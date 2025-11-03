from __future__ import annotations

from typing import Literal, Optional

import pandas as pd

import numpy as np

import logging

logger = logging.getLogger(__name__)

WARM_UP_CUT_OFF = 0.15


def mser5(data: pd.DataFrame, column: str) -> int:
    """
    Implements the MSER-5 method to determine the optimal truncation point
    for a given column in a DataFrame.

    Args:
        data (pd.DataFrame): The input DataFrame containing simulation output data.
        column (str): The name of the column to analyze.

    Returns:
        int: The index of the optimal truncation point.
    """
    if column not in data.columns:
        raise ValueError(f"Column '{column}' does not exist in the DataFrame.")

    if data[column].isnull().any():
        raise ValueError("Input column contains NaN values. Please clean the data.")

    values = data[column].to_numpy()
    n = len(values)

    if n < 5:
        return n
    # FIXME: this method is not working properly...
    # Divide data into batches of size 5
    batched_data = [
        values[i : i + 5] for i in range(0, n, 5) if len(values[i : i + 5]) == 5
    ]
    batch_means = np.array([np.mean(batch) for batch in batched_data])

    # Find truncation point that minimizes the standard error
    min_std_error = float("inf")
    optimal_index = None

    for i in range(len(batch_means)):
        truncated_means = batch_means[i:]
        std_error = np.std(truncated_means) / np.sqrt(len(truncated_means))

        if std_error < min_std_error:
            min_std_error = std_error
            optimal_index = i * 5  # Convert batch index back to original data index
    if optimal_index is None or optimal_index == (len(batch_means) - 1) * 5:
        return n
    return optimal_index


def threshold_stabilization(df: pd.DataFrame, column: str) -> int:
    """
    Determines the warm-up cutoff for steady-state simulations using the Method of Winter.

    Parameters:
        df (pd.DataFrame): The DataFrame containing the time series data.
        column (str): The name of the column with the performance metric data.

    Returns:
        int: Index of the warm-up cutoff.
    """
    # Extract the data for the specified column
    data = df[column].values

    # Compute the cumulative averages
    cumulative_avg = np.cumsum(data) / np.arange(1, len(data) + 1)

    # Compute moving range to detect stabilization
    moving_range = np.abs(np.diff(cumulative_avg))

    # Threshold for stabilization (e.g., small variation indicates steady state)
    threshold = np.mean(moving_range) / 10  # Adjust threshold as needed

    # Find the cutoff index where stabilization starts
    for i in range(1, len(moving_range)):
        if all(moving_range[i:] < threshold):
            cutoff_index = i
            break
    else:
        cutoff_index = len(data)  # If no steady state is found, use full data

    return cutoff_index


def static_ratio(df: pd.DataFrame, column: str) -> int:
    """
    Determines the warm-up cutoff for steady-state simulations using a static cutoff.

    Parameters:
        df (pd.DataFrame): The DataFrame containing the time series data.
        column (str): The name of the column with the performance metric data.

    Returns:
        int: Index of the warm-up cutoff.
    """
    data = df[column].values
    cutoff_index = int(len(data) * WARM_UP_CUT_OFF)
    return cutoff_index


def get_warm_up_cutoff_index(
    df: pd.DataFrame,
    column: str,
    method: Optional[Literal["mser5", "threshold_stabilization", "static_ratio"]] = None,
) -> int:
    """
    Calculates the warm up cutoff time for the simulation results.

    Args:
        df (pd.DataFrame): Data frame with the simulation results.
        max_time_column_name (str): The column where the maximum value is used to determine the warm up cutoff time.

    Returns:
        float: Warm up cutoff indexfor the input data frame and column.
    """
    if method is None:
        return 0
    if method == "mser5":
        cut_off_index = mser5(df, column)
    elif method == "threshold_stabilization":
        cut_off_index = threshold_stabilization(df, column)
    elif method == "static_ratio":
        cut_off_index = static_ratio(df, column)
    else:
        raise ValueError(
            "Invalid method specified for warm up cutoff index calculation. Please choose from 'mser5', 'threshold_stabilization', or 'static_ratio'."
        )

    return cut_off_index
