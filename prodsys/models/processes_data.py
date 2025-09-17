"""
The `processes_data` module contains the `prodsys.models` classes to represent the processes that can
be performed on products by resources.

The following processes are possible:
- `ProductionProcessData`: A process that can be performed on a product by a production resource.
- `CapabilityProcessData`: A process that can be performed on a product by a resource, based on the capability of the resource.
- `TransportProcessData`: A process that can be performed on a product by a transport resource.
"""

from __future__ import annotations
from hashlib import md5
from enum import Enum
from typing import Literal, Union, List, TYPE_CHECKING, Optional, Dict
from pydantic import ConfigDict, Field

from prodsys.models.core_asset import CoreAsset

if TYPE_CHECKING:
    from prodsys.models.production_system_data import ProductionSystemData


class ProcessTypeEnum(str, Enum):
    """
    Enum that represents the different kind of processes.

    - ProductionProcesses: A process that can be performed on a product by a production resource.
    - TransportProcesses: A process that can be performed on a product by a transport resource.
    - CapabilityProcesses: A process that can be performed on a product by a resource, based on the capability of the resource.
    """

    ProductionProcesses = "ProductionProcesses"
    TransportProcesses = "TransportProcesses"
    CapabilityProcesses = "CapabilityProcesses"
    CompoundProcesses = "CompoundProcesses"
    RequiredCapabilityProcesses = "RequiredCapabilityProcesses"
    LinkTransportProcesses = "LinkTransportProcesses"
    ReworkProcesses = "ReworkProcesses"
    ProcessModels = "ProcessModels"
    SequentialProcesses = "SequentialProcesses"
    LoadingProcesses = "LoadingProcesses"


class ProcessData(CoreAsset):
    """
    Class that represents process data. Acts as a base class for all process data classes.

    Args:
        ID (str): ID of the process.
        description (str): Description of the process.
        time_model_id (str): ID of the time model of the process.
    """

    time_model_id: str
    dependency_ids: list[str] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ID": "P1",
                    "description": "Process 1",
                    "time_model_id": "function_time_model_1",
                }
            ]
        }
    )

    def hash(self, adapter: ProductionSystemData) -> str:
        """
        Returns a unique hash for the process data considering the time model data. Can be used to compare two process data objects for equal functionality.

        Args:
            adapter (ProductionSystemAdapter): Adapter to access the time model data.
        Raises:
            ValueError: If the time model with the ID of the process is not found.

        Returns:
            str: hash of the process data.
        """
        for time_model in adapter.time_model_data:
            if time_model.ID == self.time_model_id:
                time_model_hash = time_model.hash()
                break
        else:
            raise ValueError(
                f"Time model with ID {self.time_model_id} not found for process {self.ID}."
            )
        return md5((time_model_hash).encode("utf-8")).hexdigest()


class ProductionProcessData(ProcessData):
    """
    Class that represents production process data.

    Args:
        ID (str): ID of the process.
        description (str): Description of the process.
        time_model_id (str): ID of the time model of the process.
        type (Literal[ProcessTypeEnum.ProductionProcesses]): Type of the process.
        failure_rate (Optional[float], optional): Failure rate of the process. Defaults to 0.0.

    Examples:
        A production process with ID "P1", description "Process 1" and time model ID "function_time_model_1":
        ``` py
        import prodsys
        prodsys.processes_data.ProductionProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="function_time_model_1",
            type="ProductionProcesses",
        )
        ```
    """

    type: Literal[ProcessTypeEnum.ProductionProcesses]
    failure_rate: Optional[float] = 0.0

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ID": "P1",
                    "description": "Process 1",
                    "time_model_id": "function_time_model_1",
                    "type": "ProductionProcesses",
                }
            ]
        }
    )

    def hash(self, adapter: ProductionSystemData) -> str:
        """
        Returns a unique hash for the production process data considering the time model data. Can be used to compare two process data objects for equal functionality.

        Args:
            adapter (ProductionSystemAdapter): Adapter to access the time model data.

        Returns:
            str: hash of the production process data.
        """
        base_class_hash = super().hash(adapter)
        failure_rate_hash = str(self.failure_rate)
        return md5((base_class_hash + failure_rate_hash).encode("utf-8")).hexdigest()


class CapabilityProcessData(ProcessData):
    """
    Class that represents capability process data. Capability processes are not compared by their IDs but their Capabilities.

    Args:
        ID (str): ID of the process.
        description (str): Description of the process.
        time_model_id (str): ID of the time model of the process.
        type (Literal[ProcessTypeEnum.CapabilityProcesses]): Type of the process.
        capability (str): Capability of the process.
        failure_rate (Optional[float], optional): Failure rate of the process. Defaults to 0.0.

    Examples:
        A capability process with ID "P1", description "Process 1", time model ID "function_time_model_1" and capability "C1":
        ``` py
        import prodsys
        prodsys.processes_data.CapabilityProcessData(
            ID="P1",
            description="Process 1",
            time_model_id="function_time_model_1",
            type="CapabilityProcesses",
            capability="C1",
        )
        ```
    """

    type: Literal[ProcessTypeEnum.CapabilityProcesses]
    capability: str
    failure_rate: Optional[float] = 0.0

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ID": "P1",
                    "description": "Process 1",
                    "time_model_id": "function_time_model_1",
                    "type": "CapabilityProcesses",
                    "capability": "C1",
                }
            ]
        }
    )

    def hash(self, adapter: ProductionSystemData) -> str:
        """
        Returns a unique hash for the capability process data considering the capability, time model and type of the process. Can be used to compare two process data objects for equal functionality.

        Args:
            adapter (ProductionSystemAdapter): Adapter to access the time model data.

        Returns:
            str: hash of the capability process data.
        """
        base_class_hash = super().hash(adapter)
        return md5(
            (base_class_hash + self.capability + str(self.failure_rate)).encode("utf-8")
        ).hexdigest()


class TransportProcessData(ProcessData):
    """
    Class that represents transport process data.

    Args:
        ID (str): ID of the process.
        description (str): Description of the process.
        time_model_id (str): ID of the time model of the process
        type (Literal[ProcessTypeEnum.TransportProcesses]): Type of the process.
        loading_time_model_id (Optional[str], optional): ID of the loading time model of the process. Defaults to None.
        unloading_time_model_id (Optional[str], optional): ID of the loading time model of the process. Defaults to None.

    Examples:
        A transport process with ID "TP1", description "Transport Process 1" and time model ID "manhattan_time_model_1":
        ``` py
        import prodsys
        prodsys.processes_data.TransportProcessData(
            ID="TP1",
            description="Transport Process 1",
            time_model_id="manhattan_time_model_1",
            type="TransportProcesses",
            loading_time_model_id="function_time_model_2",
            unloading_time_model_id="function_time_model_3",
        )
        ```
    """

    type: Literal[ProcessTypeEnum.TransportProcesses]
    loading_time_model_id: Optional[str] = None
    unloading_time_model_id: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ID": "TP1",
                    "description": "Transport Process 1",
                    "time_model_id": "manhattan_time_model_1",
                    "type": "TransportProcesses",
                    "loading_time_model_id": "function_time_model_2",
                    "unloading_time_model_id": "function_time_model_3",
                }
            ]
        }
    )

    def hash(self, adapter: ProductionSystemData) -> str:
        """
        Returns a unique hash for the required capability process data considering the capability and type of the process. Can be used to compare two process data objects for equal functionality.

        Args:
            adapter (ProductionSystemAdapter): Adapter to access the time model data.

        Returns:
            str: hash of the required capability process data.
        """
        base_class_hash = super().hash(adapter)
        loading_time_model_hash = ""
        unloading_time_model_hash = ""

        if self.loading_time_model_id:
            for time_model in adapter.time_model_data:
                if time_model.ID == self.loading_time_model_id:
                    loading_time_model_hash = time_model.hash()
                    break

        if self.unloading_time_model_id:
            for time_model in adapter.time_model_data:
                if time_model.ID == self.unloading_time_model_id:
                    unloading_time_model_hash = time_model.hash()
                    break
        input_data = (
            base_class_hash + loading_time_model_hash + unloading_time_model_hash
        )

        return md5(input_data.encode("utf-8")).hexdigest()


class ReworkProcessData(ProcessData):
    """
    Class that represents rework process data.

    Args:
        ID (str): ID of the process.
        description (str): Description of the process.
        time_model_id (str): ID of the time model of the process.
        type (Literal[ProcessTypeEnum.ProductionProcesses]): Type of the process.
        reworked_process_ids (List[str]): Process IDs of the reworked processes.
        blocking (bool): If the rework process is blocking further processing of the product.

    Examples:
        A rework process with ID "RP1", description "Rework Process 1" and time model ID "function_time_model_1":
        ``` py
        import prodsys
        prodsys.processes_data.ReworkProcessData(
            ID="RP1",
            description="Rework Process 1",
            time_model_id="function_time_model_1",
            type="ProductionProcesses",
            reworked_process_ids=["P1", "P2"],
            blocking=True
        )
        ```
    """

    type: Literal[ProcessTypeEnum.ReworkProcesses]
    reworked_process_ids: List[str]
    blocking: bool

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "summary": "Rework process",
                    "ID": "RP1",
                    "description": "Rework Process 1",
                    "time_model_id": "function_time_model_1",
                    "type": "ProductionProcesses",
                    "reworked_process_ids": ["P1", "P2"],
                    "blocking": True,
                }
            ]
        }
    )


class CompoundProcessData(CoreAsset):
    """
    Class that represents a compound process. A compound process is a container for multiple processes that belong together, e.g. if a hardware module enables all processes of a CompoundProcess or if multiple similar processes can be performed.

    Args:
        ID (str): ID of the process module.
        description (str): Description of the process module.
        process_ids (List[str]): Process IDs of the process module.
    """

    process_ids: List[str]
    type: Literal[ProcessTypeEnum.CompoundProcesses]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ID": "CP1",
                    "description": "Compound Process 1",
                    "process_ids": ["P1", "P2"],
                    "type": "CompoundProcesses",
                }
            ]
        }
    )

    def hash(self, adapter: ProductionSystemData) -> str:
        """
        Returns a unique hash for the compound process data considering the proces ids. Can be used to compare two process data objects for equal functionality.

        Args:
            adapter (ProductionSystemAdapter): Adapter to access the process data.

        Raises:
            ValueError: If a process with the ID of the compound process is not found.

        Returns:
            str: hash of the compound process data.
        """
        process_hashes = []
        for process_id in self.process_ids:
            for process in adapter.process_data:
                if process.ID == process_id:
                    process_hashes.append(process.hash(adapter))
                    break
            else:
                raise ValueError(
                    f"Process with ID {process_id} not found for compound process {self.ID}."
                )
        return md5("".join([*sorted(process_hashes)]).encode("utf-8")).hexdigest()


class RequiredCapabilityProcessData(CoreAsset):
    """
    Class that represents required capability process data. Capability processes are not compared by their IDs but their Capabilities. The required capability process data does not specify a time model ID, as it is not a process that can be performed, but a capability that is required.

    Args:
        ID (str): ID of the process.
        description (str): Description of the process.
        type (Literal[ProcessTypeEnum.CapabilityProcesses]): Type of the process.
        capability (str): Capability of the process.

    Examples:
        A required capability process with ID "P1", description "Process 1", and capability "C1":
        ``` py
        import prodsys
        prodsys.processes_data.CapabilityProcessData(
            ID="P1",
            description="Process 1",
            type="RequiredCapabilityProcesses",
            capability="C1",
        )
        ```
    """

    type: Literal[ProcessTypeEnum.RequiredCapabilityProcesses]
    capability: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ID": "P1",
                    "description": "Process 1",
                    "type": "RequiredCapabilityProcesses",
                    "capability": "C1",
                }
            ]
        }
    )

    def hash(self, adapter: ProductionSystemData) -> str:
        """
        Returns a unique hash for the required capability process data considering the capability and type of the process. Can be used to compare two process data objects for equal functionality.

        Args:
            adapter (ProductionSystemAdapter): Adapter to access the time model data.

        Returns:
            str: hash of the required capability process data.
        """
        return md5(self.capability.encode("utf-8")).hexdigest()


class LinkTransportProcessData(TransportProcessData):
    """
    Class that represents all link transport process data.

    Args:
        ID (str): ID of the process.
        description (str): Description of the process.
        time_model_id (str): ID of the time model of the process.
        type (Literal[ProcessTypeEnum.TransportProcesses]): Type of the process.
        loading_time_model_id (Optional[str], optional): ID of the loading time model of the process. Defaults to None.
        unloading_time_model_id (Optional[str], optional): ID of the loading time model of the process. Defaults to None.
        links (Union[List[List[str]], Dict[str, List[str]]]): Links of the route transport process. This can be a list of links or a dictionary of links with their IDs as keys.
        capability (Optional[str], optional): Capability of the process, which is used for matching if available. Defaults to None.

    Examples:
        A transport process with ID "TP1", description "Transport Process 1",
        type "LinkTransportProcesses", and links [["Resource1", "Node2"], ["Node2", "Resource1"]]:
        ``` py
        import prodsys
        prodsys.processes_data.LinkTransportProcessData(
            ID="TP1",
            description="Transport Process 1",
            time_model_id="manhattan_time_model_1",
            type="LinkTransportProcesses",
            links=[["Resource1", "Node2"], ["Node2", "Resource1"]],
            capability="automated_transport_process",
        )
        ```
    """

    type: Literal[ProcessTypeEnum.LinkTransportProcesses]
    links: List[List[str]]
    capability: Optional[str] = Field(default_factory=str)

    def hash(self, adapter: ProductionSystemData) -> str:
        """
        Returns a unique hash for the required capability process data considering the capability and type of the process. Can be used to compare two process data objects for equal functionality.

        Args:
            adapter (ProductionSystemAdapter): Adapter to access the time model data.

        Returns:
            str: hash of the required capability process data.
        """
        base_class_hash = super().hash(adapter)

        sorted_links = sorted(["-".join(link) for link in self.links])

        input_data = base_class_hash + "".join(sorted_links) + self.capability

        return md5(input_data.encode("utf-8")).hexdigest()

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ID": "TP1",
                    "description": "Transport Process 1",
                    "time_model_id": "manhattan_time_model_1",
                    "type": "LinkTransportProcesses",
                    "links": [["Resource1", "Node2"], ["Node2", "Resource1"]],
                }
            ]
        }
    )


class ProcessModelData(CoreAsset):
    """
    Class that represents process model data. A process model can model sequences of processes as a directed acyclic graph (DAG).

    Args:
        ID (str): ID of the process model.
        description (str): Description of the process model.
        type (Literal[ProcessTypeEnum.ProcessModels]): Type of the process.
        process_ids (List[str]): List of process IDs that are part of this process model.
        adjacency_matrix (Dict[str, List[str]]): Adjacency matrix representing the DAG structure.
        can_contain_other_models (bool): Whether this process model can contain other process models.
    """

    type: Literal[ProcessTypeEnum.ProcessModels]
    adjacency_matrix: Dict[str, List[str]]
    can_contain_other_models: bool = False
    dependency_ids: list[str] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ID": "PM1",
                    "description": "Process Model 1",
                    "type": "ProcessModels",
                    "adjacency_matrix": {"P1": ["P2"], "P2": ["P3"], "P3": []},
                    "can_contain_other_models": False,
                    "dependency_ids": ["P1", "P2"],
                }
            ]
        }
    )

    def hash(self, adapter: ProductionSystemData) -> str:
        """
        Returns a unique hash for the process model data considering the process IDs and adjacency matrix.

        Args:
            adapter (ProductionSystemAdapter): Adapter to access the process data.

        Returns:
            str: hash of the process model data.
        """
        adjacency_hash = "".join([f"{k}:{','.join(sorted(v))}" for k, v in sorted(self.adjacency_matrix.items())])
        return md5((adjacency_hash).encode("utf-8")).hexdigest()

class LoadingProcessData(ProcessData):
    """
    Class that represents loading process data. Loading processes can be chained in sequential processes or be mandatory dependencies.

    Args:
        ID (str): ID of the loading process.
        description (str): Description of the loading process.
        time_model_id (str): ID of the time model of the loading process.
        type (Literal[ProcessTypeEnum.LoadingProcesses]): Type of the process.
        dependency_type (Literal["before", "after", "parallel"]): Type of dependency relationship.
        can_be_chained (bool): Whether this loading process can be chained with others.
    """

    type: Literal[ProcessTypeEnum.LoadingProcesses]
    dependency_type: Literal["before", "after", "parallel"]
    can_be_chained: bool = True

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ID": "LP1",
                    "description": "Loading Process 1",
                    "time_model_id": "function_time_model_1",
                    "type": "LoadingProcesses",
                    "dependency_type": "before",
                    "can_be_chained": True,
                }
            ]
        }
    )

    def hash(self, adapter: ProductionSystemData) -> str:
        """
        Returns a unique hash for the loading process data considering the dependency type and chaining capability.

        Args:
            adapter (ProductionSystemAdapter): Adapter to access the time model data.

        Returns:
            str: hash of the loading process data.
        """
        base_class_hash = super().hash(adapter)
        dependency_info = f"{self.dependency_type}_{self.can_be_chained}"
        return md5((base_class_hash + dependency_info).encode("utf-8")).hexdigest()


PROCESS_DATA_UNION = Union[
    CompoundProcessData,
    RequiredCapabilityProcessData,
    ProductionProcessData,
    TransportProcessData,
    CapabilityProcessData,
    LinkTransportProcessData,
    ReworkProcessData,
    ProcessModelData,
    LoadingProcessData,
]
