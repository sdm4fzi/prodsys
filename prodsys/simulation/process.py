from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Union, List, Optional, Dict
import typing

from prodsys.models.processes_data import ProcessTypeEnum
from prodsys.simulation import request as request_module

if TYPE_CHECKING:
    from prodsys.simulation.resources import Resource
    from prodsys.simulation.source import Source
    from prodsys.simulation.sink import Sink
    from prodsys.simulation.node import Node
    from prodsys.simulation.dependency import Dependency
    from prodsys.simulation import route_finder, time_model
    

from prodsys.models import processes_data


class Process(ABC):
    """
    Abstract process base class that defines the interface for all processes.
    """

    def __init__(
        self,
        data: processes_data.PROCESS_DATA_UNION,
        time_model: Optional[time_model.TimeModel] = None,
        dependencies: Optional[
            typing.List[Dependency]
        ] = None,
    ):
        """
        Initializes the process with the given process data and time model.

        Args:
            data (processes_data.PROCESS_DATA_UNION): The process data.
            time_model (Optional[time_model.TimeModel], optional): The time model. Defaults to None.
        """
        self.data = data
        self.time_model = time_model
        self.dependencies: List[Dependency] = dependencies if dependencies else []


    @abstractmethod
    def matches_request(self, request: request_module.Request) -> bool:
        """
        Returns True if the process matches the request.

        Args:
            request (request.Request): The request.

        Returns:
            bool: True if the process matches the request.
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

    def get_process_signature(self) -> str:
        """
        Returns a unique signature for this process that can be used for lookup tables.

        Returns:
            str: A string signature representing the unique properties of this process.
        """
        if hasattr(self.data, "ID"):
            return f"{self.__class__.__name__}:{self.data.ID}"
        elif hasattr(self.data, "capability"):
            return f"{self.__class__.__name__}:{self.data.capability}"
        return f"{self.__class__.__name__}:{id(self)}"


class DependencyProcess:
    """
    Class that represents a dependency process.

    Args:
        data (processes_data.DependencyProcessData): The process data.
        time_model (time_model.TimeModel): The time model.
    """

    def __init__(
        self,
    ):
        """
        Initializes the dependency process with the given process data and time model.

        Args:
            data (processes_data.DependencyProcessData): The process data.
            time_model (Optional[time_model.TimeModel], optional): The time model. Defaults to None.
        """
        self.data = processes_data.ProductionProcessData(
            ID="DependencyProcess",
            description="",
            time_model_id="",
            dependency_ids=[],
            type=ProcessTypeEnum.ProductionProcesses,
            failure_rate=0.0,
        )
        self.dependencies = []

    def matches_request(self, request: request_module.Request) -> bool:
        raise NotImplementedError(
            "DependencyProcess does not match requests but only generates them."
        )
    
    def get_expected_process_time(self) -> float:
        raise NotImplementedError(
            "DependencyProcess does not have a process time."
        )


class ProductionProcess(Process):
    """Class that represents a production process.

    Args:
        data (processes_data.ProductionProcessData): The process data.
        time_model (time_model.TimeModel): The time model.
    """

    def __init__(
        self,
        data: processes_data.ProductionProcessData,
        time_model: Optional[time_model.TimeModel] = None,
        dependencies: Optional[
            typing.List[Dependency]
        ] = None,
    ):
        """
        Initializes the production process with the given process data and time model.

        Args:
            data (processes_data.ProductionProcessData): The process data.
            time_model (Optional[time_model.TimeModel], optional): The time model. Defaults to None.
        """
        super().__init__(data, time_model, dependencies)

    def matches_request(self, request: request_module.Request) -> bool:
        requested_process = request.process
        if not isinstance(requested_process, ProductionProcess) and not isinstance(
            requested_process, CompoundProcess
        ):
            return False
        if isinstance(requested_process, CompoundProcess):
            return self.data.ID in requested_process.data.process_ids
        return requested_process.data.ID == self.data.ID

    def get_expected_process_time(self) -> float:
        return self.time_model.get_expected_time()


class CapabilityProcess(Process):
    """
    Class that represents a capability process.

    Args:
        data (processes_data.CapabilityProcessData): The process data.
        time_model (time_model.TimeModel): The time model.
    """

    def __init__(
        self,
        data: processes_data.CapabilityProcessData,
        time_model: Optional[time_model.TimeModel] = None,
        dependencies: Optional[
            typing.List[Dependency]
        ] = None,
    ):
        """
        Initializes the capability process with the given process data and time model.

        Args:
            data (processes_data.CapabilityProcessData): The process data.
            time_model (Optional[time_model.TimeModel], optional): The time model. Defaults to None.
        """
        super().__init__(data, time_model, dependencies)

    def matches_request(self, request: request_module.Request) -> bool:
        requested_process = request.process
        if not is_process_with_capability(requested_process) and not isinstance(
            requested_process, CompoundProcess
        ):
            return False
        if isinstance(requested_process, CompoundProcess):
            return self.data.capability in [
                p.data.capability
                for p in requested_process.contained_processes_data
                if isinstance(p, CapabilityProcess)
            ]
        return requested_process.data.capability == self.data.capability

    def get_expected_process_time(self) -> float:
        return self.time_model.get_expected_time()


class TransportProcess(Process):
    """
    Class that represents a transport process.

    Args:
        data (processes_data.TransportProcessData): The process data.
        time_model (time_model.TimeModel): The time model.
    """

    def __init__(
        self,
        data: processes_data.TransportProcessData,
        time_model: Optional[time_model.TimeModel] = None,
        loading_time_model: Optional[time_model.TimeModel] = None,
        unloading_time_model: Optional[time_model.TimeModel] = None,
        dependencies: Optional[
            typing.List[Dependency]
        ] = None,
    ):
        """
        Initializes the transport process with the given process data and time model.

        Args:
            data (processes_data.TransportProcessData): The process data.
            time_model (Optional[time_model.TimeModel], optional): The time model. Defaults to None.
        """
        super().__init__(data, time_model, dependencies)
        self.loading_time_model = loading_time_model
        self.unloading_time_model = unloading_time_model

    def matches_request(self, request: request_module.Request) -> bool:
        requested_process = request.process
        if not isinstance(requested_process, TransportProcess) and not isinstance(
            requested_process, CompoundProcess
        ):
            return False
        if (
            isinstance(requested_process, TransportProcess)
            and not requested_process.data.ID == self.data.ID
        ):
            return False
        if (
            isinstance(requested_process, CompoundProcess)
            and self.data.ID not in requested_process.data.process_ids
        ):
            return False
        request.set_route(route=[request.origin, request.target])
        return True

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
    return (
        isinstance(process, CapabilityProcess)
        or isinstance(process, RequiredCapabilityProcess)
        or (
            isinstance(process, LinkTransportProcess)
            and process.data.capability
        )
    )


def is_available_process_with_capability(process: "PROCESS_UNION") -> bool:
    """
    Returns True if the given process is an available process with capability.

    Args:
        process (PROCESS_UNION): The process.

    Returns:
        bool: True if the given process is an available process with capability.
    """
    return isinstance(process, CapabilityProcess) or (
        isinstance(process, LinkTransportProcess) and process.data.capability
    )


class CompoundProcess(Process):
    """
    Class that represents a compound process.

    Args:
        data (processes_data.CompoundProcessData): The process data.
        processes (List[Union[ProductionProcess, TransportProcess, CapabilityProcess, RequiredCapabilityProcess]]): The processes.
    """

    def __init__(
        self,
        data: processes_data.CompoundProcessData,
        contained_processes_data: List[
            Union[
                processes_data.ProductionProcessData,
                processes_data.TransportProcessData,
                processes_data.CapabilityProcessData,
                processes_data.RequiredCapabilityProcessData,
                processes_data.LinkTransportProcessData,
                processes_data.ReworkProcessData,
            ]
        ],
        time_model: Optional[time_model.TimeModel] = None,
        dependencies: Optional[
            typing.List[Dependency]
        ] = None,
    ):
        """
        Initializes the compound process with the given process data and time model.

        Args:
            data (processes_data.CompoundProcessData): The process data.
            contained_processes_data (List[Union[ProductionProcess, TransportProcess, CapabilityProcess, RequiredCapabilityProcess]]): The processes.
            time_model (Optional[time_model.TimeModel], optional): The time model. Defaults to None.
        """
        super().__init__(data, time_model, dependencies)
        self.contained_processes_data = contained_processes_data

    def matches_request(self, request: request_module.Request) -> bool:
        requested_process = request.process
        if (
            isinstance(requested_process, ProductionProcess)
            or isinstance(requested_process, TransportProcess)
            or (
                isinstance(requested_process, LinkTransportProcess)
                and not requested_process.data.capability
            )
        ):
            return requested_process.data.ID in self.data.process_ids
        elif is_process_with_capability(requested_process):
            return requested_process.data.capability in [
                p.data.capability
                for p in self.contained_processes_data
                if is_available_process_with_capability(p)
            ]
        elif isinstance(requested_process, CompoundProcess):
            return any(
                p.ID in self.data.process_ids
                for p in requested_process.contained_processes_data
                if isinstance(p, ProductionProcess)
            ) or any(
                p.capability
                in [
                    p.data.capability
                    for p in self.contained_processes_data
                    if is_available_process_with_capability(p)
                ]
                for p in requested_process.contained_processes_data
                if is_available_process_with_capability(p)
            )
        return False

    def get_expected_process_time(self) -> float:
        raise NotImplementedError("CompoundProcess does not have a process time.")


class RequiredCapabilityProcess(Process):
    """
    Class that represents a required capability process.

    Args:
        data (processes_data.RequiredCapabilityProcessData): The process data.
    """

    def __init__(
        self,
        data: processes_data.RequiredCapabilityProcessData,
        time_model: Optional[time_model.TimeModel] = None,
        dependencies: Optional[
            typing.List[Dependency]
        ] = None,
    ):
        super().__init__(data, time_model, dependencies)

    def matches_request(self, request: request_module.Request) -> bool:
        raise NotImplementedError(
            "RequiredCapabilityProcess does not match requests but only generates them."
        )

    def get_expected_process_time(self) -> float:
        raise NotImplementedError(
            "RequiredCapabilityProcess does not have a process time."
        )


class ReworkProcess(Process):
    """
    Class that represents a rework process.
    """

    data: processes_data.ReworkProcessData
    reworked_process_ids: List[str]
    blocking: bool

    def __init__(
        self,
        data: processes_data.ReworkProcessData,
        time_model: Optional[time_model.TimeModel] = None,
        dependencies: Optional[
            typing.List[Dependency]
        ] = None,
        reworked_process_ids: Optional[List[str]] = None,
        blocking: Optional[bool] = None,
    ):
        super().__init__(data, time_model, dependencies)
        self.reworked_process_ids = reworked_process_ids or []
        self.blocking = blocking if blocking is not None else True

    def matches_request(self, request: request_module.Request) -> bool:
        requested_process = request.process
        if request.request_type != request_module.RequestType.REWORK:
            if not isinstance(requested_process, ReworkProcess):
                return False
            return requested_process.data.ID == self.data.ID

        if not isinstance(
            requested_process, (ProductionProcess, CapabilityProcess, CompoundProcess)
        ):
            return False

        if isinstance(requested_process, CompoundProcess):
            return any(
                reworked_process_id in requested_process.data.process_ids
                for reworked_process_id in self.reworked_process_ids
            )
        else:
            return requested_process.data.ID in self.reworked_process_ids

    def get_expected_process_time(self) -> float:
        return self.time_model.get_expected_time()


class LinkTransportProcess(TransportProcess):
    """
    Class that represents a transport link process.
    """

    data: processes_data.LinkTransportProcessData
    links: Optional[List[List[Union[Node, Source, Sink, Resource]]]]

    def __init__(
        self,
        data: processes_data.LinkTransportProcessData,
        time_model: Optional[time_model.TimeModel] = None,
        loading_time_model: Optional[time_model.TimeModel] = None,
        unloading_time_model: Optional[time_model.TimeModel] = None,
        dependencies: Optional[
            typing.List[Dependency]
        ] = None,
        links: Optional[List[List[Union[Node, Source, Sink, Resource]]]] = None,
    ):
        """
        Initializes the link transport process with the given process data and time model.

        Args:
            data (processes_data.LinkTransportProcessData): The process data.
            time_model (Optional[time_model.TimeModel], optional): The time model. Defaults to None.
        """
        super().__init__(
            data,
            time_model,
            loading_time_model,
            unloading_time_model,
            dependencies,
        )
        self.links = links if links else []

    def matches_request(
        self,
        request: request_module.Request
    ) -> bool:
        requested_process = request.process

        if (
            not isinstance(requested_process, LinkTransportProcess)
            and not isinstance(requested_process, RequiredCapabilityProcess)
            and not isinstance(requested_process, CompoundProcess)
        ):
            return False

        if isinstance(requested_process, CompoundProcess):
            possible_processes = []
            for process_data_instance in requested_process.contained_processes_data:
                if (
                    is_process_with_capability(process_data_instance)
                    and self.data.capability
                    and self.data.capability == process_data_instance.capability
                ):
                    possible_processes.append(process_data_instance)
                if (
                    isinstance(process_data_instance, LinkTransportProcess)
                    and process_data_instance.ID == self.data.ID
                ):
                    possible_processes.append(process_data_instance)
            if not possible_processes:
                return False

        if is_process_with_capability(requested_process):
            if not requested_process.data.capability == self.data.capability:
                return False
            else:
                # Check if a valid route exists for this transport request
                route = route_finder.find_route(request=request, process=self)
                if not route:
                    return False
                return True

        if isinstance(requested_process, LinkTransportProcess):
            if not requested_process.data.ID == self.data.ID:
                return False
            else:
                # Check if a valid route exists for this transport request
                route = route_finder.find_route(request=request, process=self)
                if not route:
                    return False
                return True

        return False

    def get_expected_process_time(self, *args) -> float:
        return self.time_model.get_expected_time(*args)


class ProcessModelProcess(Process):
    """
    Class that represents a process model process.

    Args:
        data (processes_data.ProcessModelData): The process data.
        time_model (time_model.TimeModel): The time model.
        contained_processes (List[PROCESS_UNION]): The processes contained in this process model.
    """

    def __init__(
        self,
        data: processes_data.ProcessModelData,
        time_model: Optional[time_model.TimeModel] = None,
        dependencies: Optional[
            typing.List[Dependency]
        ] = None,
        contained_processes: Optional[List[PROCESS_UNION]] = None,
        adjacency_matrix: Optional[Dict[str, List[str]]] = None,
    ):
        super().__init__(data, time_model, dependencies)
        self.contained_processes = contained_processes or []
        self.processes_per_id = {process.data.ID: process for process in contained_processes}
        self.adjacency_matrix = adjacency_matrix
        self.precedence_graph = PrecedenceGraphProcessModel()
        self.build_precedence_graph()


    def build_precedence_graph(self):
        successors_per_id = {process_id: [] for process_id in self.adjacency_matrix.keys()}
        predecessors_per_id = {process_id: [] for process_id in self.adjacency_matrix.keys()}
        for process_id, successors in self.adjacency_matrix.items():
            for successor in successors:
                successors_per_id[process_id].append(self.processes_per_id[successor])
                predecessors_per_id[successor].append(self.processes_per_id[process_id])
        for process_id, successors in successors_per_id.items():
            self.precedence_graph.add_node(self.processes_per_id[process_id], successors, predecessors_per_id[process_id])

    def matches_request(self, request: request_module.Request) -> bool:
        requested_process = request.process
        if not isinstance(requested_process, ProcessModelProcess) and not isinstance(
            requested_process, CompoundProcess
        ):
            return False
        if isinstance(requested_process, CompoundProcess):
            return any(
                p.data.ID in self.data.process_ids
                for p in requested_process.contained_processes_data
            )
        return requested_process.data.ID == self.data.ID

    def get_expected_process_time(self) -> float:
        # For process models, we might need to calculate based on contained processes
        # For now, return the time model's expected time
        return self.time_model.get_expected_time() if self.time_model else 0.0


class LoadingProcess(Process):
    """
    Class that represents a loading process.

    Args:
        data (processes_data.LoadingProcessData): The process data.
        time_model (time_model.TimeModel): The time model.
    """

    def __init__(
        self,
        data: processes_data.LoadingProcessData,
        time_model: Optional[time_model.TimeModel] = None,
        dependencies: Optional[
            typing.List[Dependency]
        ] = None,
    ):
        super().__init__(data, time_model, dependencies)

    def matches_request(self, request: request_module.Request) -> bool:
        requested_process = request.process
        if not isinstance(requested_process, LoadingProcess) and not isinstance(
            requested_process, CompoundProcess
        ):
            return False
        if isinstance(requested_process, CompoundProcess):
            return requested_process.data.ID in self.data.process_ids
        return requested_process.data.ID == self.data.ID

    def get_expected_process_time(self) -> float:
        return self.time_model.get_expected_time()


PROCESS_UNION = Union[
    CompoundProcess,
    RequiredCapabilityProcess,
    ProductionProcess,
    TransportProcess,
    CapabilityProcess,
    LinkTransportProcess,
    ReworkProcess,
    ProcessModelProcess,
    LoadingProcess,
]
"""
Union type for all processes.
"""

from prodsys.simulation import route_finder
from prodsys.simulation.process_models import PrecedenceGraphProcessModel