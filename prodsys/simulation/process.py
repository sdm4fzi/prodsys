from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Union, List

from pydantic import BaseModel

from prodsys.simulation import time_model
from prodsys.data_structures import processes_data


class Process(ABC, BaseModel):
    """
    Abstract process base class that defines the interface for all processes.
    """

    process_data: processes_data.PROCESS_DATA_UNION
    time_model: time_model.TimeModel

    @abstractmethod
    def get_process_time(self, *args) -> float:
        """
        Returns the time it takes to execute the process.

        Returns:
            float: Time it takes to execute the process.
        """
        pass

    @abstractmethod
    def get_expected_process_time(self, *args) -> float:
        """
        Returns the expected time it takes to execute the process.
        
        Returns:
            float: Expected time it takes to execute the process.
        """
        pass


class ProductionProcess(Process):
    """Class that represents a production process."""
    process_data: processes_data.ProductionProcessData

    def get_process_time(self) -> float:
        return self.time_model.get_next_time()

    def get_expected_process_time(self) -> float:
        return self.time_model.get_expected_time()
    

class CapabilityProcess(Process):
    """Class that represents a capability process."""
    process_data: processes_data.CapabilityProcessData

    def get_process_time(self) -> float:
        return self.time_model.get_next_time()

    def get_expected_process_time(self) -> float:
        return self.time_model.get_expected_time()


class TransportProcess(Process):
    """Class that represents a transport process."""
    process_data: processes_data.TransportProcessData

    def get_process_time(
        self, origin: List[float], target: List[float]
    ) -> float:
        return self.time_model.get_next_time(origin=origin, target=target)

    def get_expected_process_time(self, *args) -> float:
        return self.time_model.get_expected_time(*args)

PROCESS_UNION = Union[ProductionProcess, TransportProcess, CapabilityProcess]
