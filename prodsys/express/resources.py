"""
In `prodsys` exist two different types of resources: production resources and transport resources. Production resources are resources that can perform processes on products. Transport resources are resources that can transport products from one location to another. Both types of resources are represented by the `Resource` class. The `Resource` class is an abstract base class and cannot be instantiated. Instead, the `ProductionResource` and `TransportResource` classes can be used to represent production resources and transport resources, respectively.

The following resources are available:

- `ProductionResource`: Class that represents a production resource.
- `TransportResource`: Class that represents a transport resource.
"""
from typing import List, Optional, Union
from uuid import uuid1

from abc import ABC

from pydantic import Field, conlist
from pydantic.dataclasses import dataclass

from prodsys.models import core_asset, resource_data, queue_data
import prodsys

from prodsys.express import process, state, core

@dataclass
class Resource(ABC):
    """
    Abstract base class to represents a resource.

    Args:
        processes (List[process.PROCESS_UNION]): Processes of the resource.
        location (conlist(float, min_items=2, max_items=2)): Location of the resource.
        capacity (int): Capacity of the resource. Defaults to 1.
        states (Optional[List[state.STATE_UNION]], optional): States of the resource. Defaults to None.
        controller (resource_data.ControllerEnum, optional): Controller of the resource. Defaults to resource_data.ControllerEnum.PipelineController.
        control_policy (resource_data.ResourceControlPolicy, optional): Control policy of the resource. Defaults to resource_data.ResourceControlPolicy.FIFO.
        ID (str): ID of the resource.
    """
    processes: List[process.PROCESS_UNION]
    location: conlist(float, min_items=2, max_items=2)
    capacity: int = 1
    states: Optional[List[state.STATE_UNION]] = Field(default_factory=list)
    controller: resource_data.ControllerEnum = resource_data.ControllerEnum.PipelineController
    control_policy: Union[resource_data.ResourceControlPolicy, resource_data.TransportControlPolicy] = resource_data.ResourceControlPolicy.FIFO
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))


@dataclass
class ProductionResource(Resource, core.ExpressObject):
    """
    Class that represents a production resource.

    Args:
        processes (List[process.ProductionProcess]): Processes of the resource.
        location (conlist(float, min_items=2, max_items=2)): Location of the resource.
        capacity (int): Capacity of the resource. Defaults to 1.
        states (Optional[List[state.STATE_UNION]], optional): States of the resource. Defaults to None.
        controller (resource_data.ControllerEnum, optional): Controller of the resource. Defaults to resource_data.ControllerEnum.PipelineController.
        control_policy (resource_data.ResourceControlPolicy, optional): Control policy of the resource. Defaults to resource_data.ResourceControlPolicy.FIFO.
        queue_size (Optional[int], optional): Queue size of the resource. Defaults to 0 (infinte queue).
        ID (str): ID of the resource.

    Examples:
        Production resource with a capacity of 2 and 2 production processes:
        ``` py
        import prodsys.express as psx
        welding_time_model = psx.time_model_data.FunctionTimeModel(
            distribution_function="normal",
            location=20.0,
            scale=5.0,
        )
        screwing_time_model = psx.time_model_data.FunctionTimeModel(
            distribution_function="normal",
            location=10.0,
            scale=2.0,
        )
        welding_process = psx.process.ProductionProcess(
            time_model=welding_time_model
        )
        screwing_process = psx.process.ProductionProcess(
            time_model=screwing_time_model
        )
        psx.ProductionResource(
            processes=[welding_process, screwing_process],
            location=[10.0, 10.0]
            capacity=2
        )
        ```
    """
    processes: List[Union[process.ProductionProcess, process.CapabilityProcess]]
    control_policy: resource_data.ResourceControlPolicy = resource_data.ResourceControlPolicy.FIFO
    queue_size: Optional[int] = 0
    _input_queues: List[queue_data.QueueData] = Field(default_factory=list, init=False)
    _output_queues: List[queue_data.QueueData] = Field(default_factory=list, init=False)

    def to_data_object(self) -> resource_data.ProductionResourceData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            resource_data.ProductionResourceData: Data object of the express object.
        """
        resource =  resource_data.ProductionResourceData(
            ID=self.ID,
            description="",
            process_ids=[process.ID for process in self.processes],
            location=self.location,
            capacity=self.capacity,
            state_ids=[state.ID for state in self.states],
            controller=self.controller,
            control_policy=self.control_policy,
        )
        self._input_queues, self._output_queues = prodsys.adapters.get_default_queues_for_resource(resource, self.queue_size)
        resource.input_queues = [q.ID for q in self._input_queues]
        resource.output_queues = [q.ID for q in self._output_queues]
        return resource   


@dataclass
class TransportResource(Resource, core.ExpressObject):
    """
    Class that represents a transport resource.

    Args:
        processes (List[process.TransportProcess]): Processes of the resource.
        location (conlist(float, min_items=2, max_items=2)): Location of the resource.
        capacity (int): Capacity of the resource. Defaults to 1.
        states (Optional[List[state.STATE_UNION]], optional): States of the resource. Defaults to None.
        controller (resource_data.ControllerEnum, optional): Controller of the resource. Defaults to resource_data.ControllerEnum.TransportController.
        control_policy (resource_data.TransportControlPolicy, optional): Control policy of the resource. Defaults to resource_data.TransportControlPolicy.FIFO.
        ID (str): ID of the resource.

    Examples:
        Transport resource with a capacity of 1:
        ``` py
        import prodsys.express as psx
        time_model = psx.time_model_data.ManhattanDistanceTimeModel(
            speed=1.0,
            reaction_time=1.0,
        )
        transport_process = psx.process.TransportProcess(
            time_model=time_model
        )
        psx.TransportResource(
            processes=[transport_process],
            location=[10.0, 10.0]
        )
        ```
    """
    processes: List[process.TransportProcess]
    location: conlist(float, min_items=2, max_items=2) = Field(default_factory=list)
    # capacity: int = 1
    # states: Optional[List[state.STATE_UNION]] = Field(default_factory=list)
    controller: resource_data.ControllerEnum = resource_data.ControllerEnum.TransportController
    control_policy: resource_data.TransportControlPolicy = resource_data.TransportControlPolicy.FIFO
    # ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def __post_init_post_parse__(self):
        self.location = [0.0, 0.0]

    def to_data_object(self) -> resource_data.TransportResourceData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            resource_data.TransportResourceData: Data object of the express object.
        """
        return resource_data.TransportResourceData(
            ID=self.ID,
            description="",
            process_ids=[process.ID for process in self.processes],
            location=self.location,
            capacity=self.capacity,
            state_ids=[state.ID for state in self.states],
            controller=self.controller,
            control_policy=self.control_policy,
        )