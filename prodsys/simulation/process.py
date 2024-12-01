from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Union, List, Optional

from pydantic import BaseModel



if TYPE_CHECKING:
    from prodsys.simulation.resources import ProductionResource, TransportResource
    from prodsys.simulation.source import Source
    from prodsys.simulation.sink import Sink
    from prodsys.simulation.node import Node
    from prodsys.simulation import request
from prodsys.simulation import route_finder, time_model

from prodsys.models import processes_data


class Process(ABC, BaseModel):
    """
    Abstract process base class that defines the interface for all processes.
    """

    process_data: processes_data.PROCESS_DATA_UNION
    time_model: Optional[time_model.TimeModel]
    failure_rate: Optional[float] = None

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
            not is_process_with_capability(requested_process) and not isinstance(requested_process, CompoundProcess)
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

    def matches_request(self, request: request.TransportResquest) -> bool:
        requested_process = request.process
        if not isinstance(requested_process, TransportProcess) and not isinstance(
            requested_process, CompoundProcess
        ):
            return False
        if isinstance(requested_process, TransportProcess) and not requested_process.process_data.ID == self.process_data.ID:
            return False
        if isinstance(requested_process, CompoundProcess) and not self.process_data.ID in requested_process.process_data.process_ids:
            return False
        request.set_route(route=[request.origin, request.target])
        return True

    def get_process_time(self, origin: List[float], target: List[float]) -> float:
        return self.time_model.get_next_time(origin=origin, target=target)

    def get_expected_process_time(self, *args) -> float:
        return self.time_model.get_expected_time(*args)
    
def is_process_with_capability(process: "PROCESS_UNION") -> bool:
    """
    Returns True if the given process is a process with capability.

    Args:
        process (PROCESS_UNION): The process.

    Returns:
        bool: True if the given process is a process with capability.
    """
    return isinstance(process, CapabilityProcess) or isinstance(process, RequiredCapabilityProcess) or (isinstance(process, LinkTransportProcess) and process.process_data.capability)

def is_available_process_with_capability(process: "PROCESS_UNION") -> bool:
    """
    Returns True if the given process is an available process with capability.

    Args:
        process (PROCESS_UNION): The process.

    Returns:
        bool: True if the given process is an available process with capability.
    """
    return isinstance(process, CapabilityProcess) or (isinstance(process, LinkTransportProcess) and process.process_data.capability)

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
            processes_data.LinkTransportProcessData,
            processes_data.ReworkProcessData,
        ]
    ]

    def matches_request(self, request: request.Request) -> bool:
        requested_process = request.process
        if isinstance(requested_process, ProductionProcess) or isinstance(
            requested_process, TransportProcess
        ) or (isinstance(requested_process, LinkTransportProcess) and not requested_process.process_data.capability):
            return requested_process.process_data.ID in self.process_data.process_ids
        elif is_process_with_capability(requested_process):
            return requested_process.process_data.capability in [
                p.process_data.capability
                for p in self.contained_processes_data
                if is_available_process_with_capability(p)
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
                    if is_available_process_with_capability(p)
                ]
                for p in requested_process.contained_processes_data
                if is_available_process_with_capability(p)
            )
        return False

    def get_process_time(self) -> float:
        raise NotImplementedError("CompoundProcess does not have a process time.")

    def get_expected_process_time(self) -> float:
        raise NotImplementedError("CompoundProcess does not have a process time.")


class RequiredCapabilityProcess(Process):
    """
    Class that represents a required capability process.

    Args:
        process_data (processes_data.RequiredCapabilityProcessData): The process data.
    """
    process_data: processes_data.RequiredCapabilityProcessData

    def matches_request(self, request: request.Request) -> bool:
        raise NotImplementedError("RequiredCapabilityProcess does not match requests but only generates them.")

    def get_process_time(self) -> float:
        raise NotImplementedError(
            "RequiredCapabilityProcess does not have a process time."
        )

    def get_expected_process_time(self) -> float:
        raise NotImplementedError(
            "RequiredCapabilityProcess does not have a process time."
        )
    
class ReworkProcess(Process):
    """
    Class that represents a rework process.
    """
    process_data: processes_data.ReworkProcessData
    reworked_process_ids: List[str]
    blocking: bool 

    def matches_request(self, request: request.Request) -> bool:
        requested_process = request.process
        if not isinstance(requested_process, ProductionProcess) and not isinstance(requested_process, CompoundProcess) and not isinstance(requested_process, ReworkProcess):
            return False
        if isinstance(requested_process, CompoundProcess):
            return any(reworked_process_id in requested_process.process_data.process_ids for reworked_process_id in self.reworked_process_ids)
        if isinstance(requested_process, ReworkProcess):
            return True
        return requested_process.process_data.ID in self.reworked_process_ids

    def get_process_time(self) -> float:
        return self.time_model.get_next_time()

    def get_expected_process_time(self) -> float:
        return self.time_model.get_expected_time()

class LinkTransportProcess(TransportProcess):
    """
    Class that represents a transport link process.
    """
    process_data: processes_data.LinkTransportProcessData
    links: Optional[List[List[Union[Node, Source, Sink, ProductionResource]]]]

    def matches_request(self, request: Union[request.TransportResquest, request.AuxiliaryRequest]) -> bool:
        requested_process = request.process

        if not isinstance(requested_process, LinkTransportProcess) and not isinstance(requested_process, RequiredCapabilityProcess) and not isinstance(
            requested_process, CompoundProcess
        ):
            return False
        
        if isinstance(requested_process, CompoundProcess):
            possible_processes = []
            for process_data_instance in requested_process.contained_processes_data:
                if is_process_with_capability(process_data_instance) and self.process_data.capability and self.process_data.capability == process_data_instance.capability:
                    possible_processes.append(process_data_instance)
                if isinstance(process_data_instance, LinkTransportProcess) and process_data_instance.ID == self.process_data.ID:
                    possible_processes.append(process_data_instance)
            if not possible_processes:
                return False

        if is_process_with_capability(requested_process):
            if not requested_process.process_data.capability == self.process_data.capability:
                return False
            elif hasattr(request, "auxiliary") and requested_process.process_data.capability == self.process_data.capability:
                return True
        
        if isinstance(requested_process, LinkTransportProcess):
            if not requested_process.process_data.ID == self.process_data.ID:
                return False
            elif hasattr(request, "auxiliary") and requested_process.process_data.ID == self.process_data.ID:
                return True
            
        route = route_finder.find_route(request=request, process=self)
        if not route:
            return False
        return True
    
    def get_process_time(self, request: request.TransportResquest) -> float:
        route = request.get_route()
        total_time = 0
        link_route = [route[i:i+2] for i in range(len(route)-1)]

        for link in link_route:
            time = self.time_model.get_next_time(origin=link[0].get_location(), target=link[1].get_location())
            total_time += time
        return total_time

    def get_expected_process_time(self, *args) -> float:
        return self.time_model.get_expected_time(*args)
    
    

PROCESS_UNION = Union[
    CompoundProcess,
    RequiredCapabilityProcess,
    ProductionProcess,
    TransportProcess,
    CapabilityProcess,
    LinkTransportProcess,
    ReworkProcess,
]
"""
Union type for all processes.
"""
from prodsys.simulation.resources import ProductionResource, TransportResource
from prodsys.simulation.source import Source
from prodsys.simulation.sink import Sink
from prodsys.simulation.node import Node
from prodsys.simulation import request
# LinkTransportProcess.model_rebuild()
Process.model_rebuild()
