from __future__ import annotations
from collections.abc import Iterable

import random
import os

import numpy as np
from typing import Any, List, Generator
import warnings

import prodsys.models.production_system_data

warnings.filterwarnings("ignore", category=RuntimeWarning)

from os import listdir
from os.path import isfile, join

import simpy
from prodsys import adapters


def get_class_from_str(name: str, cls_dict: dict):
    """
    Returns the class for a given name from a dictionary containing classes.

    Args:
        name (str): Name of the class.
        cls_dict (dict): Dictionary containing classes.

    Raises:
        ValueError: If the class is not implemented.

    Returns:
        _type_: The class.
    """
    if name not in cls_dict.keys():
        raise ValueError(f"Class '{name}' is not implemented.")
    return cls_dict[name]


def set_seed(seed: int) -> None:
    """
    Sets the seed for numpy and random.

    Args:
        seed (int): The seed.
    """
    np.random.seed(seed)
    random.seed(seed)


def trivial_process(env: simpy.Environment) -> Generator:
    """
    Trivial process that does nothing and is immediately finished.

    Args:
        env (simpy.Environment): The simulation environment.

    Yields:
        Generator: 0 timeout.
    """
    yield env.timeout(0.0)


def read_initial_solutions(
    folder_path: str, base_configuration: adapters.ProductionSystemData
) -> List[adapters.ProductionSystemData]:
    """
    Reads all initial solutions from a folder and returns them as a list of adapters.

    Args:
        folder_path (str): The folder path where the initial solutions are stored.
        base_configuration (adapters.ProductionSystemAdapter): The base configuration for optimization containing the scenario data.

    Returns:
        List[adapters.ProductionSystemAdapter]: List of adapters of the initial solutions.
    """
    file_paths = [f for f in listdir(folder_path) if isfile(join(folder_path, f))]
    adapter_objects = []
    for counter, file_path in enumerate(file_paths):
        if ".json" not in file_path or file_path == "optimization_results.json":
            continue
        adapter = prodsys.models.production_system_data.ProductionSystemData()
        adapter.read_data(join(folder_path, file_path))
        adapter.scenario_data = base_configuration.scenario_data.model_copy()
        if not adapter.ID:
            adapter.ID = f"initial_solution_{counter}"
        adapter_objects.append(adapter)
    return adapter_objects


def get_initial_solution_file_pth(folder_path: str) -> str:
    """
    Chooses an initial solution file path from initial solution folder path.

    Args:
        folder_path (str): The folder path where the initial solutions are stored.

    Returns:
        str: The file path of the initial solution.
    """
    file_paths = [
        join(folder_path, f)
        for f in listdir(folder_path)
        if isfile(join(folder_path, f))
    ]
    return random.choice(file_paths)


def prepare_save_folder(file_paths: str):
    """
    Creates a folder if it does not exist.

    Args:
        file_paths (str): The file path where the folder should be created.
    """
    isExist = os.path.exists(file_paths)
    if not isExist:
        os.makedirs(file_paths)


def flatten(xs: Iterable) -> Iterable:
    """
    Flattens a nested Iterable containing at the lowest level only str or bytes.

    Args:
        xs (Iterable): The nested list.

    Yields:
        Iterable: The flattened list.
    """
    for x in xs:
        if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
            yield from flatten(x)
        else:
            yield x


def flatten_object(xs: list) -> Generator[Any, Any, list]:
    """
    Flattens a nested list.

    Args:
        xs (list): The nested list.

    Yields:
        list: The flattened list.
    """
    for x in xs:
        if isinstance(x, list):
            yield from flatten_object(x)
        else:
            yield x


def run_from_ipython() -> bool:
    """
    Checks if the code is run from an ipython notebook.

    Returns:
        bool: True if run from ipython notebook, False otherwise.
    """
    try:
        __IPYTHON__  # type: ignore
        return True
    except NameError:
        return False
