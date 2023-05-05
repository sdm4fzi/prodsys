from __future__ import annotations

from typing import Callable, List, Dict, TYPE_CHECKING

from numpy.random import exponential, normal, lognormal
from enum import Enum

if TYPE_CHECKING:
    from prodsim.data_structures.time_model_data import FunctionTimeModelData

class FunctionTimeModelEnum(str, Enum):
    Constant = "constant"
    Exponential = "exponential"
    Normal = "normal"
    Lognormal = "lognormal"


def get_constant_list(time_model_data: FunctionTimeModelData) -> List[float]:
    return [time_model_data.location] * time_model_data.batch_size


def get_exponential_list(time_model_data: FunctionTimeModelData) -> List[float]:
    return list(exponential(time_model_data.location, time_model_data.batch_size))


def get_normal_list(time_model_data: FunctionTimeModelData) -> List[float]:
    return list(normal(time_model_data.location, time_model_data.scale, time_model_data.batch_size))

def get_lognormal_list(time_model_data: FunctionTimeModelData) -> List[float]:
    return list(lognormal(time_model_data.location, time_model_data.scale, time_model_data.batch_size))

FUNCTION_DICT: Dict[str, Callable[[float, float, int], List[float]]] = {
    FunctionTimeModelEnum.Normal: get_normal_list,
    FunctionTimeModelEnum.Constant: get_constant_list,
    FunctionTimeModelEnum.Exponential: get_exponential_list,
    FunctionTimeModelEnum.Lognormal: get_lognormal_list,
}