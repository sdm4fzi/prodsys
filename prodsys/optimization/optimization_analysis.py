import pandas as pd
from typing import List
import json
import plotly
import plotly.graph_objects as go
import numpy as np
from copy import copy

from prodsys.optimization.optimization_data import OptimizationResults


def transform_optimization_results_to_df(data: OptimizationResults, label: str) -> pd.DataFrame:
    """
    Function reads the results of an optimization run from a json file and returns a pandas dataframe.

    Args:
        filepath (str): Filepath to the json file.
        label (str): Label to specify the utilized optimizer.

    Returns:
        pd.DataFrame: Dataframe containing the optimization results.
    """
    new_data = {}
    row_number = 1
    for generation, values in data.items():
        population_number = 0
        for adapter_id, individual_values in values.items():
            population_number += 1
            row_value = {
                "Generation": int(generation),
                "population_number": population_number,
                "ID": adapter_id,
                "agg_fitness": individual_values.agg_fitness,
                "time": individual_values.time_stamp,
            }
            for counter, KPI in enumerate(individual_values.fitness):
                row_value.update({f"KPI_{counter}": KPI})
            new_data.update(
                {
                    str(row_number): row_value,
                }
            )
            row_number += 1
    df = pd.DataFrame(new_data)
    df = df.T
    df["optimizer"] = label
    if label == "anneal":
        df["agg_fitness"] = -1 * df["agg_fitness"]
    return df.copy()


def is_pareto_efficient_simple(costs: np.ndarray) -> np.ndarray:
    """
    Find the pareto-efficient points

    Args:
        costs (np.ndarray): An (n_points, n_costs) array

    Returns:
        np.ndarray: A (n_points, ) boolean array, indicating whether each point is Pareto efficient
    """
    is_efficient = np.ones(costs.shape[0], dtype=bool)
    for i, c in enumerate(costs):
        if is_efficient[i]:
            is_efficient[is_efficient] = np.any(
                costs[is_efficient] < c, axis=1
            )  # Keep any point with a lower cost
            is_efficient[i] = True  # And keep self
    return is_efficient


# Faster than is_pareto_efficient_simple, but less readable.
def is_pareto_efficient(costs):
    """
    Find the pareto-efficient points

    Args:
        costs (np.ndarray): An (n_points, n_costs) array

    Returns:
        np.ndarray: A (n_points, ) boolean array, indicating whether each point is Pareto efficient
    """
    is_efficient = np.arange(costs.shape[0])
    n_points = costs.shape[0]
    next_point_index = 0  # Next index in the is_efficient array to search for
    while next_point_index < len(costs):
        nondominated_point_mask = np.any(costs < costs[next_point_index], axis=1)
        nondominated_point_mask[next_point_index] = True
        is_efficient = is_efficient[nondominated_point_mask]  # Remove dominated points
        costs = costs[nondominated_point_mask]
        next_point_index = np.sum(nondominated_point_mask[:next_point_index]) + 1
    is_efficient_mask = np.zeros(n_points, dtype=bool)
    is_efficient_mask[is_efficient] = True
    return is_efficient_mask


def get_pareto_solutions_from_result_files(
    optimization_results: OptimizationResults
) -> List[str]:
    """
    Analyses an optimization result file and returns the IDs of the pareto efficient solutions.

    Args:
        file_path (str): Filepath of the json file containing the optimization results.

    Returns:
        List[str]: List of IDs of the pareto efficient solutions.
    """
    df = transform_optimization_results_to_df(optimization_results, label="optimizer")
    relevant_cols = ["agg_fitness", "cost", "throughput", "wip", "optimizer"]
    relevant_cols = [col for col in relevant_cols if col in df.columns]
    df = df.drop_duplicates(subset=relevant_cols)
    # TODO: update here method to not use all kpis but those which are in optimizarion_results[generation][ID].objective_names
    if "cost" in relevant_cols:
        df["cost"] = df["cost"].astype(float)
    df["agg_fitness"] = df["agg_fitness"].astype(float)
    # df = df.loc[df["wip"] < 150]
    # df = df.loc[df["throughput"] > 100]
    # # df = df.loc[df["throughput_time"] < 100]
    pareto_columns = [col for col in relevant_cols if col not in ["agg_fitness", "optimizer"]]
    df_for_pareto = df[pareto_columns].copy()
    if "throughput" in pareto_columns:
        df_for_pareto["throughput"] = -df_for_pareto["throughput"]
    is_efficient = is_pareto_efficient(df_for_pareto.values)
    df["is_efficient"] = is_efficient
    return df.loc[df["is_efficient"]]["ID"].to_list()
