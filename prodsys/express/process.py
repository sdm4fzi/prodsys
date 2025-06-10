"""
`process` module contains the `prodsys.express` classes to represent the processes that can
be performed on products by resources.

The following processes are possible:
- `ProductionProcess`: A process that can be performed on a product by a production resource.
- `CapabilityProcess`: A process that can be performed on a product by a resource, based on the capability of the resource.
- `TransportProcess`: A process that can be performed on a product by a transport resource.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Union
from uuid import uuid1

from abc import ABC

from pydantic import Field
from pydantic.dataclasses import dataclass

from prodsys.express import core, time_model
from prodsys.models import processes_data


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
    dependencies: Optional[List[Dependency]] = Field(default_factory=list)


@dataclass
class ProductionProcess(DefaultProcess, core.ExpressObject):
    """
    Class that represents a production process.

    Args:
        time_model (time_model.TIME_MODEL_UNION): Time model of the process.
        failure_rate (Optional[float]): Failure rate of the process.
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

    failure_rate: Optional[float] = None
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))
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
            type=self.type,
            failure_rate=self.failure_rate,
            dependency_ids=[dependency.ID for dependency in self.dependencies],
        )


@dataclass
class CapabilityProcess(Process, core.ExpressObject):
    """
    Class that represents a capability process. For capability processes, matching of
    required processes of product and provided processes by resources is done based on
    the capability instead of the porcess itself.

    Args:
        time_model (time_model.TIME_MODEL_UNION): Time model of the process.
        failure_rate (Optional[float]): Failure rate of the process.
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
    failure_rate: Optional[float] = None
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))
    type: processes_data.ProcessTypeEnum = Field(
        init=False, default=processes_data.ProcessTypeEnum.CapabilityProcesses
    )
    dependencies: Optional[List[Dependency]] = Field(default_factory=list)

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
            type=self.type,
            failure_rate=self.failure_rate,
            dependency_ids=[dependency.ID for dependency in self.dependencies],
        )


@dataclass
class ReworkProcess(Process, core.ExpressObject):
    """
    Class that represents a rework process. Rework processes are required to rework a product.

    Args:
        time_model (time_model.TIME_MODEL_UNION): Time model of the process.
        reworked_process (Optional[Union[ProductionProcess, CapabilityProcess]]): Process that is reworked.
        blocking (Optional[bool]): If the rework process is blocking.
        ID (str): ID of the process.
    """

    reworked_processes: list[Union[ProductionProcess, CapabilityProcess]]
    blocking: Optional[bool] = False
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))
    type: processes_data.ProcessTypeEnum = Field(
        init=False, default=processes_data.ProcessTypeEnum.ReworkProcesses
    )
    dependencies: Optional[List[Dependency]] = Field(default_factory=list)

    def to_model(self):
        return processes_data.ReworkProcessData(
            ID=self.ID,
            description="",
            type=self.type,
            time_model_id=self.time_model.ID,
            reworked_process_ids=[
                reworked_process.ID for reworked_process in self.reworked_processes
            ],
            blocking=self.blocking,
            dependency_ids=[dependency.ID for dependency in self.dependencies],
        )


@dataclass
class TransportProcess(DefaultProcess, core.ExpressObject):
    """
    Class that represents a transport process. Transport processes are required to transport product from one location to another.

    Args:
        time_model (time_model.TIME_MODEL_UNION): Time model of the process.
        ID (str): ID of the process.
        loading_time_model (Optional[time_model.TIME_MODEL_UNION]): Time model of the loading process.
        unloading_time_model (Optional[time_model.TIME_MODEL_UNION]): Time model of the unloading process.
        type (processes_data.ProcessTypeEnum): Type of the process.

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

    loading_time_model: Optional[time_model.TIME_MODEL_UNION] = None
    unloading_time_model: Optional[time_model.TIME_MODEL_UNION] = None
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
            type=self.type,
            loading_time_model_id=(
                self.loading_time_model.ID if self.loading_time_model else None
            ),
            unloading_time_model_id=(
                self.unloading_time_model.ID if self.unloading_time_model else None
            ),
            dependency_ids=[dependency.ID for dependency in self.dependencies],
        )


@dataclass
class LinkTransportProcess(TransportProcess):
    """
    Represents a link transport process. They include a list or dict of links.

    Attributes:
        type (processes_data.ProcessTypeEnum): The type of the process.
        ID (Optional[str]): The ID of the process.
        links (Union[List[List[Union[resources.Resource, resources.NodeData, source.Source, sink.Sink]]],
                      Dict[Union[resources.Resource, resources.NodeData, source.Source, sink.Sink],
                           List[Union[resources.Resource, resources.NodeData, source.Source, sink.Sink]]]]):
            The links associated with the process. Each link is a list of different objects, which can be a
            Resource, NodeData, Source, or Sink. If the links attribute is a list, it represents a list of
            links, where each link is a list of these objects. If the links attribute is a dictionary, it represents a
            mapping from a key (which can be a Resource, NodeData, Source, or Sink) to a list of these objects.
        capability (Optional[str]): The capability of the process.
    """

    type: processes_data.ProcessTypeEnum = Field(
        init=False, default=processes_data.ProcessTypeEnum.LinkTransportProcesses
    )
    links: Union[
        List[List[Union[resources.Resource, sink.Sink, source.Source, node.Node]]],
        Dict[
            Union[resources.Resource, sink.Sink, source.Source, node.Node],
            List[Union[resources.Resource, sink.Sink, source.Source, node.Node]],
        ],
    ] = Field(default_factory=list)
    capability: Optional[str] = Field(default_factory=str)

    def add_link(
        self, link: List[Union[resources.Resource, sink.Sink, source.Source, node.Node]]
    ) -> None:
        """
        Adds a link to the LinkTransportProcess object.

        Args:
            link (Union[Resource, Node, Source, Sink]): The link to add.
            link_list (List[Union[Resource, Node, Source, Sink]]): The list of links to add the link to.
        """
        if isinstance(self.links, list):
            self.links.append(link)
        else:
            if not link in self.links:
                self.links[link] = []
            self.links[link[0]] = link[1]

    def set_links(
        self,
        links: List[
            List[Union[resources.Resource, node.Node, source.Source, sink.Sink]]
        ],
    ) -> None:
        """
        Sets the links of the LinkTransportProcess object.

        Args:
            links (List[List[Union[Resource, Node, Source, Sink]]]): The links to set.
        """
        self.links = links

    def to_model(self) -> processes_data.LinkTransportProcessData:
        """
        Converts the LinkTransportProcess object to its corresponding data model.

        Returns:
            processes_data.LinkTransportProcessData: The converted data model object.
        """
        if isinstance(self.links, list):
            return_links = [[link.ID for link in link_list] for link_list in self.links]
        else:
            return_links = []
            for start, targets in self.links.items():
                for target in targets:
                    return_links.append([start.ID, target.ID])

        return processes_data.LinkTransportProcessData(
            time_model_id=self.time_model.ID,
            ID=self.ID,
            description="",
            type=self.type,
            links=return_links,
            capability=self.capability,
            loading_time_model_id=(
                self.loading_time_model.ID if self.loading_time_model else None
            ),
            unloading_time_model_id=(
                self.unloading_time_model.ID if self.unloading_time_model else None
            ),
            dependency_ids=[dependency.ID for dependency in self.dependencies],
        )


@dataclass
class RequiredCapabilityProcess(core.ExpressObject):
    """
    Represents a required capability process. A capability which can be matched with the capability of another process with a capability.

    Attributes:
        ID (Optional[str]): The ID of the process.
        type (processes_data.ProcessTypeEnum): The type of the process.
        capability (Optional[str]): The capability required by the process.
    """

    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))
    type: processes_data.ProcessTypeEnum = Field(
        init=False, default=processes_data.ProcessTypeEnum.RequiredCapabilityProcesses
    )
    capability: Optional[str] = Field(default_factory=str)

    def to_model(self) -> processes_data.RequiredCapabilityProcessData:
        """
        Converts the RequiredCapabilityProcess object to its corresponding data model.

        Returns:
            processes_data.RequiredCapabilityProcessData: The data model representation of the process.
        """
        return processes_data.RequiredCapabilityProcessData(
            ID=self.ID,
            description="",
            type=self.type,
            capability=self.capability,
        )


PROCESS_UNION = Union[
    ProductionProcess,
    CapabilityProcess,
    TransportProcess,
    RequiredCapabilityProcess,
    LinkTransportProcess,
    ReworkProcess,
]
from prodsys.express import resources, sink, source, node
from prodsys.express.dependency import Dependency
