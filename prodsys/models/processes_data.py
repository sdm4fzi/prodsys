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
from typing import Literal, Union, List, TYPE_CHECKING

from prodsys.models.core_asset import CoreAsset

if TYPE_CHECKING:
    from prodsys.adapters.adapter import ProductionSystemAdapter


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


class ProcessData(CoreAsset):
    """
    Class that represents process data. Acts as a base class for all process data classes.

    Args:
        ID (str): ID of the process.
        description (str): Description of the process.
        time_model_id (str): ID of the time model of the process.
    """

    time_model_id: str
    # TODO: add optional attribute for failure rate (defaults to 0), also update hasing

    class Config:
        schema_extra = {
            "example": {
                "ID": "P1",
                "description": "Process 1",
                "time_model_id": "function_time_model_1",
            }
        }
    
    def hash(self, adapter: ProductionSystemAdapter) -> str:
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
            raise ValueError(f"Time model with ID {self.time_model_id} not found for process {self.ID}.")
        return md5((time_model_hash).encode("utf-8")).hexdigest()


class ProductionProcessData(ProcessData):
    """
    Class that represents production process data.

    Args:
        ID (str): ID of the process.
        description (str): Description of the process.
        time_model_id (str): ID of the time model of the process.
        type (Literal[ProcessTypeEnum.ProductionProcesses]): Type of the process.

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

    class Config:
        schema_extra = {
            "example": {
                "summary": "Production process",
                "value": {
                    "ID": "P1",
                    "description": "Process 1",
                    "time_model_id": "function_time_model_1",
                    "type": "ProductionProcesses",
                },
            }
        }


class CapabilityProcessData(ProcessData):
    """
    Class that represents capability process data. Capability processes are not compared by their IDs but their Capabilities.

    Args:
        ID (str): ID of the process.
        description (str): Description of the process.
        time_model_id (str): ID of the time model of the process.
        type (Literal[ProcessTypeEnum.CapabilityProcesses]): Type of the process.
        capability (str): Capability of the process.

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

    class Config:
        schema_extra = {
            "example": {
                "summary": "Capability process",
                "value": {
                    "ID": "P1",
                    "description": "Process 1",
                    "time_model_id": "function_time_model_1",
                    "type": "CapabilityProcesses",
                    "capability": "C1",
                },
            }
        }

    def hash(self, adapter: ProductionSystemAdapter) -> str:
        """
        Returns a unique hash for the capability process data considering the capability, time model and type of the process. Can be used to compare two process data objects for equal functionality.

        Args:
            adapter (ProductionSystemAdapter): Adapter to access the time model data.

        Returns:
            str: hash of the capability process data.
        """
        base_class_hash = super().hash(adapter)
        return md5((base_class_hash + self.capability).encode("utf-8")).hexdigest()

class TransportProcessData(ProcessData):
    """
    Class that represents transport process data.

    Args:
        ID (str): ID of the process.
        description (str): Description of the process.
        time_model_id (str): ID of the time model of the process
        type (Literal[ProcessTypeEnum.TransportProcesses]): Type of the process.

    Examples:
        A transport process with ID "TP1", description "Transport Process 1" and time model ID "manhattan_time_model_1":
        ``` py
        import prodsys
        prodsys.processes_data.TransportProcessData(
            ID="TP1",
            description="Transport Process 1",
            time_model_id="manhattan_time_model_1",
            type="TransportProcesses",
        )
        ```
    """

    type: Literal[ProcessTypeEnum.TransportProcesses]
    # TODO: add time model for loading (and maybe unloading)

    class Config:
        schema_extra = {
            "example": {
                "summary": "Transport process",
                "value": {
                    "ID": "TP1",
                    "description": "Transport Process 1",
                    "time_model_id": "manhattan_time_model_1",
                    "type": "TransportProcesses",
                },
            }
        }


# TODO: add ReworkProcess

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

    class Config:
        schema_extra = {
            "example": {
                "summary": "Compound Process",
                "value": {
                    "ID": "CP1",
                    "description": "Compound Process 1",
                    "process_ids": ["P1", "P2"],
                    "type": "CompoundProcesses",
                },
            }
        }

    def hash(self, adapter: ProductionSystemAdapter) -> str:
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
                raise ValueError(f"Process with ID {process_id} not found for compound process {self.ID}.")
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

    class Config:
        schema_extra = {
            "example": {
                "summary": "Required Capability process",
                "value": {
                    "ID": "P1",
                    "description": "Process 1",
                    "type": "RequiredCapabilityProcesses",
                    "capability": "C1",
                },
            }
        }

    def hash(self, adapter: ProductionSystemAdapter) -> str:
        """
        Returns a unique hash for the required capability process data considering the capability and type of the process. Can be used to compare two process data objects for equal functionality.

        Args:
            adapter (ProductionSystemAdapter): Adapter to access the time model data.

        Returns:
            str: hash of the required capability process data.
        """
        return md5(self.capability.encode("utf-8")).hexdigest()


PROCESS_DATA_UNION = Union[
    CompoundProcessData, RequiredCapabilityProcessData,
    ProductionProcessData, TransportProcessData, CapabilityProcessData
]