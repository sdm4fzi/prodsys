import numpy as np
from numpy.random import exponential, normal
from typing import Tuple, List
from collections.abc import Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


def get_constant_list(parameters: Tuple[float], size: int) -> List[float]:
    return [parameters[0]] * size


def get_exponential_list(parameters: Tuple[float], size: int) -> List[float]:
    return list(exponential(parameters[0], size))


def get_normal_list(parameters: Tuple[float], size: int) -> List[float]:
    return list(normal(parameters[0], parameters[1], size))


FUNCTION_DICT: dict = {'normal': get_normal_list,
                       'constant': get_constant_list,
                       'exponential': get_exponential_list
                       }


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
    history: List[float]

    def get_next_time(self) -> float:
        return np.random.choice(self.history, 1)


@dataclass
class MarkovTimeModel(TimeModel):

    def get_next_time(self) -> float:
        pass


@dataclass
class TimeModelFactory:
    data: dict
    time_models: List[TimeModel] = field(default_factory=list)
    time_model_ids: List[int] = field(default_factory=list)

    def create_time_models(self):
        time_models = self.data['time_models']
        for _id, values in time_models.items():
            self.add_time_model(_id, values)

    def add_time_model(self, _id, values):
        self.time_models.append(FunctionTimeModel(parameters=values['parameters'],
                                                  batch_size=values['batch_size'],
                                                  distribution_function=FUNCTION_DICT[values['distribution_function']]
                                                  ))
        self.time_model_ids.append(_id)

    def get_time_model(self, _id):
        if _id not in self.time_model_ids:
            raise ValueError("The _id ist not available for time models.")
        idx = self.time_model_ids.index(_id)
        return self.time_models[idx]
