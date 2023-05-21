from __future__ import annotations
from collections.abc import Iterable

import random
import os

import numpy as np
from typing import List
import warnings

warnings.filterwarnings("ignore", category=RuntimeWarning)

from os import listdir
from os.path import isfile, join


from prodsys import adapters


def get_class_from_str(name: str, cls_dict: dict):
    if name not in cls_dict.keys():
        raise ValueError(f"Class '{name}' is not implemented.")
    return cls_dict[name]


def set_seed(seed: int) -> None:
    np.random.seed(seed)
    random.seed(seed)


def trivial_process(env):
    yield env.timeout(0.0)


def read_initial_solutions(
    folder_path: str, base_configuration: adapters.Adapter
) -> List[adapters.Adapter]:
    """Reads all initial solutions from a folder and returns them as a list of adapters."""
    file_paths = [f for f in listdir(folder_path) if isfile(join(folder_path, f))]
    adapter_objects = []
    for file_path in file_paths:
        if ".json" not in file_path or file_path == "optimization_results.json":
            continue
        adapter = adapters.JsonAdapter()
        adapter.read_data(join(folder_path, file_path))
        adapter.scenario_data = base_configuration.scenario_data.copy()
        adapter_objects.append(adapter)
    return adapter_objects

def get_initial_solution_file_pth(
        folder_path: str
) -> str:
    """Chooses an initial solution file path from initial solution folder path."""
    file_paths = [join(folder_path, f) for f in listdir(folder_path) if isfile(join(folder_path, f))]
    return random.choice(file_paths)

def prepare_save_folder(file_paths: str):
    isExist = os.path.exists(file_paths)
    if not isExist:
        os.makedirs(file_paths)


def flatten(xs):
    for x in xs:
        if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
            yield from flatten(x)
        else:
            yield x

def flatten_object(xs):
    for x in xs:
        if isinstance(x, list):
            yield from flatten_object(x)
        else:
            yield x



