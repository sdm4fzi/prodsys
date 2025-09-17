"""
`process` module contains the `prodsys.express` classes to represent the processes that can
be performed on products by resources.

The following processes are possible:
- `ProductionProcess`: A process that can be performed on a product by a production resource.
- `CapabilityProcess`: A process that can be performed on a product by a resource, based on the capability of the resource.
- `TransportProcess`: A process that can be performed on a product by a transport resource.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Union, Literal
from uuid import uuid1

from abc import ABC

from pydantic import Field, field_validator, model_validator
from pydantic.dataclasses import dataclass
from pydantic_core import ArgsKwargs

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


@dataclass
class ProcessModel(core.ExpressObject):
    """
    Class that represents a process model. A process model can model sequences of processes as a directed acyclic graph (DAG).

    Args:
        process_ids (List[str]): List of process IDs that are part of this process model.
        adjacency_matrix (Dict[str, List[str]]): Adjacency matrix representing the DAG structure.
        can_contain_other_models (bool): Whether this process model can contain other process models.
        ID (str): ID of the process model.

    Examples:
        Process model with a simple sequence:
        ```py
        import prodsys.express as psx
        psx.ProcessModel(
            process_ids=["P1", "P2", "P3"],
            adjacency_matrix={"P1": ["P2"], "P2": ["P3"], "P3": []}
        )
        ```
    """
    adjacency_matrix: Dict[str, List[str]]
    can_contain_other_models: bool = False
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))
    type: processes_data.ProcessTypeEnum = Field(
        init=False, default=processes_data.ProcessTypeEnum.ProcessModels
    )
    dependencies: Optional[List[Dependency]] = Field(default_factory=list)

    def to_model(self) -> processes_data.ProcessModelData:
        """
        Converts the ProcessModel object to its corresponding data model.

        Returns:
            processes_data.ProcessModelData: The converted data model object.
        """
        return processes_data.ProcessModelData(
            ID=self.ID,
            description="",
            type="ProcessModels",
            adjacency_matrix=self.adjacency_matrix,
            can_contain_other_models=self.can_contain_other_models,
            dependency_ids=[dependency.ID for dependency in self.dependencies],
        )


@dataclass
class SequentialProcess(ProcessModel):
    """
    Class that represents a sequential process. A sequential process is a container for a sequence of processes.

    Args:
        process_ids (List[str]): List of process IDs that are executed sequentially.
        ID (str): ID of the sequential process.

    Examples:
        Sequential process with three processes:
        ```py
        import prodsys.express as psx
        psx.SequentialProcess(
            process_ids=["P1", "P2", "P3"]
        )
        ```
    """

    adjacency_matrix: Optional[Dict[str, List[str]]] = None
    process_ids: Optional[List[str]] = None
    type: processes_data.ProcessTypeEnum = Field(
        init=False, default=processes_data.ProcessTypeEnum.SequentialProcesses
    )

    def __post_init__(self):
        """Generate adjacency matrix for sequential execution after initialization."""
        if self.adjacency_matrix is None:
            adjacency_matrix = {}
            for i, process_id in enumerate(self.process_ids):
                if i < len(self.process_ids) - 1:
                    adjacency_matrix[process_id] = [self.process_ids[i + 1]]
                else:
                    adjacency_matrix[process_id] = []
            self.adjacency_matrix = adjacency_matrix

    @model_validator(mode='before')
    @classmethod
    def validate_adjacency_matrix(cls, v):
        if v is None:
            return {}
        if ArgsKwargs and isinstance(v, ArgsKwargs):
            v = dict(v.kwargs or {})  # ignore positional args for this model
        # check that its purely sequential
        count_nodes_without_successors = 0
        start_node_count = {}
        end_node_count = {}
        if isinstance(v, dict) and "process_ids" in v and "adjacency_matrix" not in v:
            # adjacency_matrix = {process_id: [process_id + 1] for counter,process_id in enumerate(v["process_ids"]) if counter < len(v["process_ids"]) - 1}
            adjacency_matrix = {}
            for i, process_id in enumerate(v["process_ids"]):
                if i < len(v["process_ids"]) - 1:
                    adjacency_matrix[process_id] = [v["process_ids"][i + 1]]
                else:
                    adjacency_matrix[process_id] = []
            v["adjacency_matrix"] = adjacency_matrix
        else:
            adjacency_matrix = v["adjacency_matrix"]
        print(adjacency_matrix)
        for process_id, successors in adjacency_matrix.items():
            if len(successors) > 1:
                raise ValueError(f"Process {process_id} has multiple successors: {successors}")
            
            if len(successors) == 0:
                count_nodes_without_successors += 1
                continue
            if process_id == successors[0]:
                raise ValueError(f"Process {process_id} has itself as successor")
            if process_id not in start_node_count:
                start_node_count[process_id] = 0
            start_node_count[process_id] += 1
            if successors[0] not in end_node_count:
                end_node_count[successors[0]] = 0
            end_node_count[successors[0]] += 1
        if count_nodes_without_successors > 1:
            raise ValueError(f"There are {count_nodes_without_successors} nodes without successors")
        if any(x > 1 for x in start_node_count.values()):
            raise ValueError(f"There are {sum(start_node_count.values())} nodes with multiple successors, probably due to a directed cycle")
        if any(x > 1 for x in end_node_count.values()):
            raise ValueError(f"There are {sum(end_node_count.values())} nodes with multiple predecessors")
        return v


@dataclass
class LoadingProcess(Process, core.ExpressObject):
    """
    Class that represents a loading process. Loading processes can be chained in sequential processes or be mandatory dependencies.

    Args:
        time_model (time_model.TIME_MODEL_UNION): Time model of the loading process.
        dependency_type (Literal["before", "after", "parallel"]): Type of dependency relationship.
        can_be_chained (bool): Whether this loading process can be chained with others.
        ID (str): ID of the loading process.

    Examples:
        Loading process with "before" dependency:
        ```py
        import prodsys.express as psx
        time_model = psx.FunctionTimeModel("normal", 2.0, 0.5)
        psx.LoadingProcess(
            time_model=time_model,
            dependency_type="before",
            can_be_chained=True
        )
        ```
    """

    dependency_type: Literal["before", "after", "parallel"]
    can_be_chained: bool = True
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))
    type: processes_data.ProcessTypeEnum = Field(
        init=False, default=processes_data.ProcessTypeEnum.LoadingProcesses
    )
    dependencies: Optional[List[Dependency]] = Field(default_factory=list)

    def to_model(self) -> processes_data.LoadingProcessData:
        """
        Converts the LoadingProcess object to its corresponding data model.

        Returns:
            processes_data.LoadingProcessData: The converted data model object.
        """
        return processes_data.LoadingProcessData(
            time_model_id=self.time_model.ID,
            ID=self.ID,
            description="",
            type=self.type,
            dependency_type=self.dependency_type,
            can_be_chained=self.can_be_chained,
            dependency_ids=[dependency.ID for dependency in self.dependencies],
        )


PROCESS_UNION = Union[
    ProductionProcess,
    CapabilityProcess,
    TransportProcess,
    RequiredCapabilityProcess,
    LinkTransportProcess,
    ReworkProcess,
    ProcessModel,
    SequentialProcess,
    LoadingProcess,
]

# Import at the end to avoid circular imports
from prodsys.express import resources, sink, source, node
from prodsys.express.dependency import Dependency
