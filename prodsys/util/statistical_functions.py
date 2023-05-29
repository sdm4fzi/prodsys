from __future__ import annotations

from typing import Callable, List, Dict, TYPE_CHECKING

from numpy.random import exponential, normal, lognormal
from enum import Enum

if TYPE_CHECKING:
    from prodsys.models.time_model_data import FunctionTimeModelData

class FunctionTimeModelEnum(str, Enum):
    Constant = "constant"
    Exponential = "exponential"
    Normal = "normal"
    Lognormal = "lognormal"


def get_constant_list(time_model_data: FunctionTimeModelData) -> List[float]:
    """
    Returns a list of constant values.

    Args:
        time_model_data (FunctionTimeModelData): The time model data.

    Returns:
        List[float]: A list of constant values.
    """
    return [time_model_data.location] * time_model_data.batch_size


def get_exponential_list(time_model_data: FunctionTimeModelData) -> List[float]:
    """
    Returns a list of exponentially distributed values.

    Args:
        time_model_data (FunctionTimeModelData): The time model data.

    Returns:
        List[float]: A list of exponentially distributed values.
    """
    return list(exponential(time_model_data.location, time_model_data.batch_size))


def get_normal_list(time_model_data: FunctionTimeModelData) -> List[float]:
    """
    Returns a list of normally distributed values.

    Args:
        time_model_data (FunctionTimeModelData): The time model data.

    Returns:
        List[float]: A list of normally distributed values.
    """
    return list(normal(time_model_data.location, time_model_data.scale, time_model_data.batch_size))

def get_lognormal_list(time_model_data: FunctionTimeModelData) -> List[float]:
    """
    Returns a list of lognormally distributed values.

    Args:
        time_model_data (FunctionTimeModelData): The time model data.

    Returns:
        List[float]: A list of lognormally distributed values.
    """
    return list(lognormal(time_model_data.location, time_model_data.scale, time_model_data.batch_size))

FUNCTION_DICT: Dict[str, Callable[[float, float, int], List[float]]] = {
    FunctionTimeModelEnum.Normal: get_normal_list,
    FunctionTimeModelEnum.Constant: get_constant_list,
    FunctionTimeModelEnum.Exponential: get_exponential_list,
    FunctionTimeModelEnum.Lognormal: get_lognormal_list,
}
"""
Dictionary that maps the time model function enum to the corresponding function.
"""