from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Tuple, List, Set
from util import get_class_from_str

import numpy as np
from numpy.random import exponential, normal

from base import IDEntity


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


class TimeModel(ABC, IDEntity):

    @abstractmethod
    def get_next_time(self) -> float:
        pass


@dataclass
class FunctionTimeModel(TimeModel):
    parameters: Tuple
    batch_size: int
    distribution_function: str
    _distribution_function: Callable[[Tuple, int], List] = field(default=None, init=False)
    _statistics_buffer: List[float] = field(default_factory=list, init=False)

    def __post_init__(self):
        self._distribution_function = FUNCTION_DICT[self.distribution_function]

    def get_next_time(self) -> float:
        try:
            value = self._statistics_buffer.pop()
            if value < 0:
                return 0
            return value
        except IndexError:
            self._fill_buffer()
            return self.get_next_time()

    def _fill_buffer(self):
        self._statistics_buffer = self._distribution_function(self.parameters, self.batch_size)


@dataclass
class HistoryTimeModel(TimeModel):
    history: List[float]

    def get_next_time(self) -> float:
        return np.random.choice(self.history, 1)[0]


@dataclass
class MarkovTimeModel(TimeModel):

    def get_next_time(self) -> float:
        pass


TIME_MODEL_DICT: dict = {
    'HistoryTimeModels': HistoryTimeModel,
    'MarkovTimeModel': MarkovTimeModel,
    'FunctionTimeModels': FunctionTimeModel,
}


@dataclass
class TimeModelFactory:
    data: dict
    time_models: List[TimeModel] = field(default_factory=list)

    def create_time_models(self):
        time_models = self.data['time_models']
        for cls_name, items in time_models.items():
            cls = get_class_from_str(cls_name, TIME_MODEL_DICT)
            for values in items.values():
                self.add_time_model(cls, values)

    def add_time_model(self, cls, values):
        self.time_models.append(cls(**values))

    def get_time_models(self, IDs: List[str]) -> List[TimeModel]:
        return [tm for tm in self.time_models if tm.ID in IDs]

    def get_time_model(self, ID: str) -> TimeModel:
        return [tm for tm in self.time_models if tm.ID == ID].pop()
