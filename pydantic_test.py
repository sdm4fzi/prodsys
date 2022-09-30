from typing import Callable, List, Literal, Optional, Union
from pydantic import BaseModel, ValidationError, validator, parse_obj_as

from abc import ABC, abstractmethod


def exponential(parameters: List[float], batch_size: int=3):
    return [parameters[0]] * batch_size

def normal(parameters: List[float], batch_size: int=2):
    return [parameters[0]] * batch_size + [parameters[1]]*batch_size

class Asset(BaseModel):
    ID: str
    description: str

class TimeModel(Asset, ABC):
    type: str

    @abstractmethod
    def get_value(self) -> float:
        pass

FUNC_DICT = {
    'exp': exponential,
    'norm': normal
}

class FunctionTimeModel(TimeModel):
    type: Literal['FunctionTimeModel']
    distribution_type: Literal['exp', 'norm'] = 'exp'
    parameters: List[float]
    distribution_function: Callable[[List[float], Optional[int]], int] = None

    @validator("distribution_function", always=True)
    def initialize_distribution_function(cls, v, values):
        return FUNC_DICT[values['distribution_type']]

    def get_value(self) -> float:
        return self.distribution_function(self.parameters)

class HistoryTimeModel(TimeModel):
    type: Literal['HistoryTimeModel']
    time_values: List[float]

    def get_value(self) -> float:
        return self.time_values

if __name__ == '__main__':
    kwargs={
        'ID': 'F',
        'description': 'FTMO',
        'type': 'FunctionTimeModel',
        'distribution_type': 'norm',
        'parameters': [1.3, 2.0]
    }

    f = FunctionTimeModel(**kwargs)
    print(f)
    print(f.get_value())

    print("_______________")

    kwargs2={
        'ID': 'H',
        'description': 'HTMO',
        'type': 'HistoryTimeModel',
        'time_values': [4.4, 4.5, 40]
    }

    h = HistoryTimeModel(**kwargs2)

    print(h)
    print(h.get_value())

    print("__________")

    Context = Union[HistoryTimeModel, FunctionTimeModel]

    kwargs3 = {
        'ID': 'M',
        'description': 'jaaa',
        'type': 'HistoryTimeModel',
        'time_values': [7.8, 8, 9]
    }

    # context = parse_raw_as(Context, **kwargs3)
    m = parse_obj_as(Context, kwargs)

    print(m)
    print(m.get_value())