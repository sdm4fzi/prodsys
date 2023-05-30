"""
`process` module contains the `prodsys.express` classes to represent the processes that can 
be performed on products by resources.

The following processes are possible:
- `ProductionProcess`: A process that can be performed on a product by a production resource.
- `CapabilityProcess`: A process that can be performed on a product by a resource, based on the capability of the resource.
- `TransportProcess`: A process that can be performed on a product by a transport resource.
"""

from __future__ import annotations

from typing import List, Optional, Union
from uuid import uuid1

from abc import ABC

from pydantic import Field
from pydantic.dataclasses import dataclass

from prodsys.models import processes_data, time_model_data

from prodsys.express import time_model, core

@dataclass
class Process(ABC):
    """
    Abstract base class to represents a process.

    Args:
        time_model (time_model.TIME_MODEL_UNION): Time model of the process.

    Attributes:
        type (processes_data.ProcessTypeEnum): Type of the process.
    """

    time_model: time_model.TIME_MODEL_UNION

@dataclass
class DefaultProcess(Process):
    """
    Abstract base class to represents a process, with no additional attributes than type and ID.

    Args:
        time_model (time_model.TIME_MODEL_UNION): Time model of the process.
        ID (str): ID of the process.
    
    Attributes:
        type (processes_data.ProcessTypeEnum): Type of the process.
    """
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))
    type: processes_data.ProcessTypeEnum = Field(init=False)




@dataclass
class ProductionProcess(DefaultProcess, core.ExpressObject):
    """
    Class that represents a production process.

    Args:
        time_model (time_model.TIME_MODEL_UNION): Time model of the process.
        ID (str): ID of the process.

    Attributes:
        type (processes_data.ProcessTypeEnum): Type of the process. Equals to processes_data.ProcessTypeEnum.ProductionProcesses.

    Examples:
        Production process with a function time model:
        ``` py
        import prodsys.express as psx
        welding_time_model = psx.time_model_data.FunctionTimeModel(
            distribution_function="normal",
            location=20.0,
            scale=5.0,
        )
        psx.ProductionProcess(
            time_model=welding_time_model,
        )
        ```
    """
    type: processes_data.ProcessTypeEnum = Field(
        init=False, default=processes_data.ProcessTypeEnum.ProductionProcesses
    )

    def to_model(self) -> processes_data.ProductionProcessData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            processes_data.ProductionProcessData: Data object of the express object.
        """
        return processes_data.ProductionProcessData(
            time_model_id=self.time_model.ID,
            ID=self.ID,
            description="",
            type=self.type
        )


@dataclass
class CapabilityProcess(Process, core.ExpressObject):
    """
    Class that represents a capability process. For capability processes, matching of 
    required processes of product and provided processes by resources is done based on 
    the capability instead of the porcess itself.

    Args:
        time_model (time_model.TIME_MODEL_UNION): Time model of the process.
        capability (str): Capability of the process.
        ID (str): ID of the process.

    Attributes:
        type (processes_data.ProcessTypeEnum): Type of the process. Equals to processes_data.ProcessTypeEnum.CapabilityProcesses.

    Examples:
        Capability process with a function time model:
        ``` py
        import prodsys.express as psx
        welding_time_model = psx.FunctionTimeModel(
            distribution_function="normal",
            location=20.0,
            scale=5.0,
        )
        psx.CapabilityProcess(
            time_model=welding_time_model,
            capability="welding"
        )
        ```
    """
    capability: str
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))
    type: processes_data.ProcessTypeEnum = Field(
        init=False, default=processes_data.ProcessTypeEnum.CapabilityProcesses
    )

    def to_model(self) -> processes_data.CapabilityProcessData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            processes_data.CapabilityProcessData: Data object of the express object.
        """
        return processes_data.CapabilityProcessData(
            time_model_id=self.time_model.ID,
            capability=self.capability,
            ID=self.ID,
            description="",
            type=self.type
        )


@dataclass
class TransportProcess(DefaultProcess, core.ExpressObject):
    """
    Class that represents a transport process. Transport processes are required to transport product from one location to another. 

    Args:
        time_model (time_model.TIME_MODEL_UNION): Time model of the process.
        ID (str): ID of the process.

    Attributes:
        type (processes_data.ProcessTypeEnum): Type of the process. Equals to processes_data.ProcessTypeEnum.TransportProcesses.

    Examples:
        Transport process with a manhattan distance time model:
        ```py
        import prodsys.express as psx
        manhattan_time_model = psx.ManhattenDistanceTimeModel(
            speed=30.0,
            reaction_time=0.15,
        )
        psx.TransportProcess(
            time_model=manhattan_time_model
        )
        ```
    """ 
    type: processes_data.ProcessTypeEnum = Field(
        init=False, default=processes_data.ProcessTypeEnum.TransportProcesses
    )

    def to_model(self) -> processes_data.TransportProcessData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            processes_data.TransportProcessData: Data object of the express object.
        """
        return processes_data.TransportProcessData(
            time_model_id=self.time_model.ID,
            ID=self.ID,
            description="",
            type=self.type
        )
    

PROCESS_UNION = Union[
    ProductionProcess,
    CapabilityProcess,
    TransportProcess,
]

