from __future__ import annotations

from typing import Callable, List, Dict

from numpy.random import exponential, normal
from enum import Enum

class FunctionTimeModelEnum(str, Enum):
    Constant = "constant"
    Exponential = "exponential"
    Normal = "normal"


def get_constant_list(parameters: List[float], size: int) -> List[float]:
    return [parameters[0]] * size


def get_exponential_list(parameters: List[float], size: int) -> List[float]:
    return list(exponential(parameters[0], size))


def get_normal_list(parameters: List[float], size: int) -> List[float]:
    return list(normal(parameters[0], parameters[1], size))


FUNCTION_DICT: Dict[str, Callable[[List[float], int], List[float]]] = {
    FunctionTimeModelEnum.Normal: get_normal_list,
    FunctionTimeModelEnum.Constant: get_constant_list,
    FunctionTimeModelEnum.Exponential: get_exponential_list,
}