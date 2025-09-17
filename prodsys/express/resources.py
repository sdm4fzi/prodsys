"""
In `prodsys` exist two different types of resources: production resources and transport resources. Production resources are resources that can perform processes on products. Transport resources are resources that can transport products from one location to another. Both types of resources are represented by the `Resource` class. The `Resource` class is an abstract base class and cannot be instantiated. Instead, the `Resource` and `Resource` classes can be used to represent production resources and transport resources, respectively.

The following resources are available:

- `Resource`: Class that represents a production resource.
- `Resource`: Class that represents a transport resource.
"""

from __future__ import annotations

from typing import List, Optional, Union, Dict
from uuid import uuid1

from abc import ABC

from pydantic import Field, conlist
from pydantic.dataclasses import dataclass

from prodsys.express import core, port

from prodsys.models import port_data, resource_data
import prodsys
import prodsys.models
from prodsys.models.core_asset import Location2D
import prodsys.models.production_system_data


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
    location: Location2D
    capacity: int = 1
    states: Optional[List[state.STATE_UNION]] = Field(default_factory=list)
    controller: resource_data.ControllerEnum = (
        resource_data.ControllerEnum.PipelineController
    )
    control_policy: Union[
        resource_data.ResourceControlPolicy, resource_data.TransportControlPolicy
    ] = resource_data.ResourceControlPolicy.FIFO
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    batch_size: Optional[int] = None
    internal_queue_size: Optional[int] = 0
    ports: List[port_data.QueueData] = Field(default_factory=list, init=False)

    dependencies: Optional[List[dependency.Dependency]] = Field(default_factory=list)

    def to_model(self) -> resource_data.ResourceData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            resource_data.ResourceData: Data object of the express object.
        """
        resource = resource_data.ResourceData(
            ID=self.ID,
            description="",
            process_ids=[process.ID for process in self.processes],
            location=self.location,
            capacity=self.capacity,
            batch_size=self.batch_size,
            state_ids=[state.ID for state in self.states],
            controller=self.controller,
            control_policy=self.control_policy,
            dependency_ids=[dep.ID for dep in self.dependencies],
        )
        if not self.ports:
            self.ports = [
                prodsys.models.production_system_data.get_default_queue_for_resource(
                    resource, self.internal_queue_size
                )
            ]
        resource.ports = [port.ID for port in self.ports]
        return resource


@dataclass
class SystemResource(Resource):
    """
    Class that represents a system resource. A system resource is a resource with subresources that can be used interchangeably.

    Args:
        processes (List[process.PROCESS_UNION]): Processes of the system resource.
        location (conlist(float, min_length=2, max_length=2)): Location of the system resource.
        subresource_ids (List[str]): List of subresource IDs that are part of this system.
        system_ports (Optional[List[str]], optional): List of system port IDs for external communication. Defaults to None.
        internal_routing_matrix (Optional[Dict[str, List[str]]], optional): Internal routing matrix for routing within the system. Defaults to None.
        capacity (int): Capacity of the system resource. Defaults to 1.
        states (Optional[List[state.STATE_UNION]], optional): States of the system resource. Defaults to None.
        controller (resource_data.ControllerEnum, optional): Controller of the system resource. Defaults to resource_data.ControllerEnum.PipelineController.
        control_policy (resource_data.ResourceControlPolicy, optional): Control policy of the system resource. Defaults to resource_data.ResourceControlPolicy.FIFO.
        ID (str): ID of the system resource.

    Examples:
        System resource with subresources:
        ```py
        import prodsys.express as psx
        psx.SystemResource(
            processes=[process1, process2],
            location=[10.0, 10.0],
            subresource_ids=["R1", "R2", "R3"],
            system_ports=["SP1", "SP2"],
            internal_routing_matrix={"SP1": ["R1"], "R1": ["R2"], "R2": ["R3"], "R3": ["SP2"]}
        )
        ```
    """

    subresource_ids: "List[str]" = Field(default_factory=list)
    system_ports: "Optional[List[str]]" = None
    internal_routing_matrix: "Optional[Dict[str, List[str]]]" = None

    def to_model(self) -> resource_data.SystemResourceData:
        """
        Converts the SystemResource object to its corresponding data model.

        Returns:
            resource_data.SystemResourceData: The converted data model object.
        """
        resource = resource_data.SystemResourceData(
            ID=self.ID,
            description="",
            process_ids=[process.ID for process in self.processes],
            location=self.location,
            capacity=self.capacity,
            batch_size=self.batch_size,
            state_ids=[state.ID for state in self.states],
            controller=self.controller,
            control_policy=self.control_policy,
            dependency_ids=[dep.ID for dep in self.dependencies],
            subresource_ids=self.subresource_ids,
            system_ports=self.system_ports,
            internal_routing_matrix=self.internal_routing_matrix,
        )
        if not self.ports:
            self.ports = [
                prodsys.models.production_system_data.get_default_queue_for_resource(
                    resource, self.internal_queue_size
                )
            ]
        resource.ports = [port.ID for port in self.ports]
        return resource


from prodsys.express import state, process, dependency
