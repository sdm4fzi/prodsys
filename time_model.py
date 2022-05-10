import numpy as np
from numpy.random import exponential, normal
from typing import Tuple, List
from collections.abc import Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


def get_constant_list(parameters : Tuple[float], size: int) -> List[float]:
    return [parameters[0]] * size

def get_exponential_list(parameters : Tuple[float], size : int) -> List[float]:
    return list(exponential(parameters[0], size))

def get_normal_list(parameters : Tuple[float], size : int) -> List[float]:
    return list(normal(parameters[0], parameters[1], size))

class TimeModel(ABC):

    @abstractmethod
    def get_next_time(self) -> float:
        pass

@dataclass
class FunctionTimeModel(TimeModel):
    parameters: Tuple
    batch_size: int
    distribution_function: Callable[[Tuple, int], List]
    _statistics_buffer: List[float] = field(default_factory=list)

    def get_next_time(self) -> float:
        try:
            return self._statistics_buffer.pop()
        except IndexError:
            self._fill_buffer()
            return self._statistics_buffer.pop()


    def _fill_buffer(self):
        self._statistics_buffer = self.distribution_function(self.parameters, self.batch_size)

@dataclass
class HistoryTimeModel(TimeModel):
    history : List[float]

    def get_next_time(self) -> float:
        return np.random.choice(self.history, 1)

@dataclass
class MarkovTimeModel(TimeModel):

    def get_next_time(self) -> float:
        pass