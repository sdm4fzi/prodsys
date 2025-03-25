"""
In `prodsys` exist two different types of resources: production resources and transport resources. Production resources are resources that can perform processes on products. Transport resources are resources that can transport products from one location to another. Both types of resources are represented by the `Resource` class. The `Resource` class is an abstract base class and cannot be instantiated. Instead, the `ProductionResource` and `TransportResource` classes can be used to represent production resources and transport resources, respectively.

The following resources are available:

- `ProductionResource`: Class that represents a production resource.
- `TransportResource`: Class that represents a transport resource.
"""

from __future__ import annotations

from typing import List, Optional, Union
from uuid import uuid1

from abc import ABC

from pydantic import Field, conlist
from pydantic.dataclasses import dataclass

from prodsys.express import core

from prodsys.models import resource_data, queue_data
import prodsys


@dataclass
class Resource(core.ExpressObject):
    """
    Abstract base class to represents a resource.

    Args:
        processes (List[process.PROCESS_UNION]): Processes of the resource.
        location (conlist(float, min_length=2, max_length=2)): Location of the resource.
        capacity (int): Capacity of the resource. Defaults to 1.
        states (Optional[List[state.STATE_UNION]], optional): States of the resource. Defaults to None.
        controller (resource_data.ControllerEnum, optional): Controller of the resource. Defaults to resource_data.ControllerEnum.PipelineController.
        control_policy (resource_data.ResourceControlPolicy, optional): Control policy of the resource. Defaults to resource_data.ResourceControlPolicy.FIFO.
        ID (str): ID of the resource.
    """

    processes: List[process.PROCESS_UNION]
    location: list[float] = Field(..., min_length=2, max_length=2)
    capacity: int = 1
    states: Optional[List[state.STATE_UNION]] = Field(default_factory=list)
    controller: resource_data.ControllerEnum = (
        resource_data.ControllerEnum.PipelineController
    )
    control_policy: Union[
        resource_data.ResourceControlPolicy, resource_data.TransportControlPolicy
    ] = resource_data.ResourceControlPolicy.FIFO
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    input_location: Optional[list[float]] = Field(None, min_length=2, max_length=2)
    output_location: Optional[list[float]] = Field(None, min_length=2, max_length=2)

    batch_size: Optional[int] = None
    input_stores: Optional[list[queue.Store]] = Field(default_factory=list)
    output_stores: Optional[list[queue.Store]] = Field(default_factory=list)
    internal_queue_size: Optional[int] = 0
    _input_queues: List[queue_data.QueueData] = Field(default_factory=list, init=False)
    _output_queues: List[queue_data.QueueData] = Field(default_factory=list, init=False)

    def to_model(self) -> resource_data.ResourceData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            resource_data.ProductionResourceData: Data object of the express object.
        """
        resource = resource_data.ResourceData(
            ID=self.ID,
            description="",
            process_ids=[process.ID for process in self.processes],
            location=self.location,
            input_location=self.input_location,
            output_location=self.output_location,
            capacity=self.capacity,
            batch_size=self.batch_size,
            state_ids=[state.ID for state in self.states],
            controller=self.controller,
            control_policy=self.control_policy,
        )
        (
            self._input_queues,
            self._output_queues,
        ) = prodsys.adapters.get_default_queues_for_resource(
            resource, self.internal_queue_size
        )
        resource.input_queues = [q.ID for q in self._input_queues + self.input_stores]
        resource.output_queues = [
            q.ID for q in self._output_queues + self.output_stores
        ]
        return resource


from prodsys.express import state, process, queue
