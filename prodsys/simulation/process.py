from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Union, List, Optional

from pydantic import BaseModel

from prodsys.simulation import time_model, request
from prodsys.models import processes_data


class Process(ABC, BaseModel):
    """
    Abstract process base class that defines the interface for all processes.
    """

    process_data: processes_data.PROCESS_DATA_UNION
    time_model: Optional[time_model.TimeModel]

    @abstractmethod
    def matches_request(self, request: request.Request) -> bool:
        """
        Returns True if the process matches the request.

        Args:
            request (request.Request): The request.

        Returns:
            bool: True if the process matches the request.
        """
        pass

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
    """Class that represents a production process.

    Args:
        process_data (processes_data.ProductionProcessData): The process data.
        time_model (time_model.TimeModel): The time model.
    """

    process_data: processes_data.ProductionProcessData

    def matches_request(self, request: request.Request) -> bool:
        requested_process = request.process
        if not isinstance(requested_process, ProductionProcess) and not isinstance(
            requested_process, CompoundProcess
        ):
            return False
        if isinstance(requested_process, CompoundProcess):
            return self.process_data.ID in requested_process.process_data.process_ids
        return requested_process.process_data.ID == self.process_data.ID

    def get_process_time(self) -> float:
        return self.time_model.get_next_time()

    def get_expected_process_time(self) -> float:
        return self.time_model.get_expected_time()


class CapabilityProcess(Process):
    """
    Class that represents a capability process.

    Args:
        process_data (processes_data.CapabilityProcessData): The process data.
        time_model (time_model.TimeModel): The time model.
    """
    process_data: processes_data.CapabilityProcessData

    def matches_request(self, request: request.Request) -> bool:
        requested_process = request.process
        if (
            not isinstance(requested_process, CapabilityProcess)
            and not isinstance(requested_process, CompoundProcess)
            and not isinstance(requested_process, RequiredCapabilityProcess)
        ):
            return False
        if isinstance(requested_process, CompoundProcess):
            return self.process_data.capability in [
                p.process_data.capability
                for p in requested_process.contained_processes_data
                if isinstance(p, CapabilityProcess)
            ]
        return requested_process.process_data.capability == self.process_data.capability

    def get_process_time(self) -> float:
        return self.time_model.get_next_time()

    def get_expected_process_time(self) -> float:
        return self.time_model.get_expected_time()


class TransportProcess(Process):
    """
    Class that represents a transport process.

    Args:
        process_data (processes_data.TransportProcessData): The process data.
        time_model (time_model.TimeModel): The time model.
    """
    process_data: processes_data.TransportProcessData

    def matches_request(self, request: request.Request) -> bool:
        requested_process = request.process
        if not isinstance(requested_process, TransportProcess) and not isinstance(
            requested_process, CompoundProcess
        ):
            return False
        if isinstance(requested_process, TransportProcess):
            return requested_process.process_data.ID == self.process_data.ID
        return self.process_data.ID in requested_process.process_data.process_ids

    def get_process_time(self, origin: List[float], target: List[float]) -> float:
        return self.time_model.get_next_time(origin=origin, target=target)

    def get_expected_process_time(self, *args) -> float:
        return self.time_model.get_expected_time(*args)


class CompoundProcess(Process):
    """
    Class that represents a compound process.

    Args:
        process_data (processes_data.CompoundProcessData): The process data.
        processes (List[Union[ProductionProcess, TransportProcess, CapabilityProcess, RequiredCapabilityProcess]]): The processes.
    """
    process_data: processes_data.CompoundProcessData
    contained_processes_data: List[
        Union[
            processes_data.ProductionProcessData,
            processes_data.TransportProcessData,
            processes_data.CapabilityProcessData,
            processes_data.RequiredCapabilityProcessData,
        ]
    ]

    def matches_request(self, request: request.Request) -> bool:
        requested_process = request.process
        if isinstance(requested_process, ProductionProcess) or isinstance(
            requested_process, TransportProcess
        ):
            return requested_process.process_data.ID in self.process_data.process_ids
        elif isinstance(requested_process, CapabilityProcess) or isinstance(
            requested_process, RequiredCapabilityProcess
        ):
            return requested_process.process_data.capability in [
                p.process_data.capability
                for p in self.contained_processes_data
                if isinstance(p, CapabilityProcess)
            ]
        elif isinstance(requested_process, CompoundProcess):
            return any(
                p.ID in self.process_data.process_ids
                for p in requested_process.contained_processes_data
                if isinstance(p, ProductionProcess)
            ) or any(
                p.capability
                in [
                    p.process_data.capability
                    for p in self.contained_processes_data
                    if isinstance(p, CapabilityProcess)
                ]
                for p in requested_process.contained_processes_data
                if isinstance(p, CapabilityProcess)
            )

    def get_process_time(self) -> float:
        raise NotImplementedError("CompoundProcess does not have a process time.")

    def get_expected_process_time(self) -> float:
        raise NotImplementedError("CompoundProcess does not have a process time.")


class RequiredCapabilityProcess(Process):
    """
    Class that represents a required capability process.

    Args:
        process_data (processes_data.RequiredCapabilityProcessData): The process data.
        time_model (time_model.TimeModel): The time model.
    """

    process_data: processes_data.RequiredCapabilityProcessData

    def matches_request(self, request: request.Request) -> bool:
        raise NotImplementedError(
            "RequiredCapabilityProcess cannot be matched but should only request."
        )

    def get_process_time(self) -> float:
        raise NotImplementedError(
            "RequiredCapabilityProcess does not have a process time."
        )

    def get_expected_process_time(self) -> float:
        raise NotImplementedError(
            "RequiredCapabilityProcess does not have a process time."
        )

# TODO: Implement LinkTransportProcess and RouteTransportProcess and their associatd data models.

PROCESS_UNION = Union[
    CompoundProcess,
    RequiredCapabilityProcess,
    ProductionProcess,
    TransportProcess,
    CapabilityProcess,
]
"""
Union type for all processes.
"""
