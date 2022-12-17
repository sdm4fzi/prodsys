from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple, Union

from pydantic import BaseModel

from prodsim import time_model
from prodsim.data_structures import processes_data


class Process(ABC, BaseModel):
    """
    Abstract process base class
    """

    process_data: processes_data.PROCESS_DATA_UNION
    time_model: time_model.TimeModel

    @abstractmethod
    def get_process_time(self, *args) -> float:
        pass

    @abstractmethod
    def get_expected_process_time(self, *args) -> float:
        pass


class ProductionProcess(Process):
    process_data: processes_data.ProductionProcessData

    def get_process_time(self) -> float:
        return self.time_model.get_next_time()

    def get_expected_process_time(self) -> float:
        return self.time_model.get_expected_time()


class TransportProcess(Process):
    process_data: processes_data.TransportProcessData

    def get_process_time(
        self, origin: Tuple[float, float], target: Tuple[float, float]
    ) -> float:
        return self.time_model.get_next_time(origin=origin, target=target)

    def get_expected_process_time(self, *args) -> float:
        return self.time_model.get_expected_time(*args)


PROCESS_UNION = Union[ProductionProcess, TransportProcess]
