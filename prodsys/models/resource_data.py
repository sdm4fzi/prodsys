"""
In `prodsys` exist two different types of resources: production resources and transport resources. Production resources are resources that can perform processes on products. Transport resources are resources that can transport products from one location to another. Both types of resources are represented by the `ResourceData` class. The `ResourceData` class is an abstract base class and cannot be instantiated. Instead, the `ResourceData` and `ResourceData` classes can be used to represent production resources and transport resources, respectively.

The following resources are available:

- `ResourceData`: Class that represents a production resource.
- `ResourceData`: Class that represents a transport resource.
"""

from __future__ import annotations
from hashlib import md5
from typing import Any, Literal, Union, List, Optional, TYPE_CHECKING, Dict
from enum import Enum

from pydantic import (
    ConfigDict,
    ValidationInfo,
    field_validator,
    model_validator,
    conlist,
)
from prodsys.models.core_asset import CoreAsset, Locatable

if TYPE_CHECKING:
    from prodsys.models.production_system_data import ProductionSystemData


class ControllerEnum(str, Enum):
    """
    Enum that represents the controller of a resource.

    - PipelineController: Pipeline controller.
    """

    PipelineController = "PipelineController"


class ResourceControlPolicy(str, Enum):
    """
    Enum that represents the control policy of a resource.

    - FIFO: First in first out.
    - LIFO: Last in first out.
    - SPT: Shortest processing time first.
    """

    FIFO = "FIFO"
    LIFO = "LIFO"
    SPT = "SPT"


class TransportControlPolicy(str, Enum):
    """
    Enum that represents the control policy of a transport resource.

    - FIFO: First in first out.
    - SPT_transport: Shortest raw transport time first. Does not consider distance to start of the transport.
    - NEAREST_ORIGIN_AND_LONGEST_TARGET_QUEUES_TRANSPORT: Nearest_Origin but also sorts by the length of the target queue to make sure, something can be picked up at the target.
    - NEAREST_ORIGIN_AND_SHORTEST_TARGET_INPUT_QUEUES_TRANSPORT: Nearest_Origin but also sorts by the length of the target input queue to prefer target machines, that have lower number of products waiting to be processed.
    """

    FIFO = "FIFO"
    SPT_transport = "SPT_transport"
    NEAREST_ORIGIN_AND_LONGEST_TARGET_QUEUES_TRANSPORT = (
        "Nearest_origin_and_longest_target_queues_transport"
    )
    NEAREST_ORIGIN_AND_SHORTEST_TARGET_INPUT_QUEUES_TRANSPORT = (
        "Nearest_origin_and_shortest_target_input_queues_transport"
    )


class ResourceType(str, Enum):
    """
    Enum that represents the type of resource.

    - SYSTEM: System resource.
    - RESOURCE: Resource.
    """

    SYSTEM = "system"
    RESOURCE = "resource"


class ResourceData(CoreAsset, Locatable):
    """
    Class that represents resource data. Base class for ResourceData and ResourceData.

    Args:
        ID (str): ID of the resource.
        description (str): Description of the resource.
        capacity (int): Capacity of the resource.
        location (List[float]): Location of the resource. Has to be a list of length 2.
        controller (ControllerEnum): Controller of the resource.
        control_policy (Union[ResourceControlPolicy, TransportControlPolicy]): Control policy of the resource.
        process_ids (List[str]): Process IDs of the resource.
        process_capacities (Optional[List[int]], optional): Process capacities of the resource (in sequence of the capacity of the resource). Must have the same length as process_ids. Defaults to None.
        state_ids (Optional[List[str]], optional): State IDs of the resource. Defaults to [].
        ports (Optional[List[str]], optional): List of port IDs that are used by the resource for input and output of products and primitives. Ports can be Queues, Stores or other Port Interfaces. If not specfied, default Queues with infinite capacity are created at simulation start.
        can_move (Optional[bool], optional): Whether the resource can move. Defaults to None (if None, the can_move attribute is inferred from the processes).
        dependency_ids (List[str]): List of dependency IDs that are required by the resource.
    """
    resource_type: ResourceType = ResourceType.RESOURCE
    process_ids: List[str]

    control_policy: Union[ResourceControlPolicy, TransportControlPolicy]
    capacity: int = 1
    process_capacities: Optional[List[int]] = None
    state_ids: Optional[List[str]] = []
    controller: ControllerEnum = ControllerEnum.PipelineController
    ports: Optional[List[str]] = None
    buffers: Optional[List[str]] = None
    can_move: Optional[bool] = None

    dependency_ids: List[str] = []

    @model_validator(mode="before")
    def check_process_capacity(cls, values):
        if not isinstance(values, dict):
            return values
        if "process_capacities" not in values or values["process_capacities"] is None:
            values["process_capacities"] = [
                values["capacity"] for _ in values["process_ids"]
            ]
        if len(values["process_capacities"]) != len(values["process_ids"]):
            raise ValueError(
                f"process_capacities {values['process_capacities']} must have the same length as processes {values['process_ids']}"
            )
        if (
            values["process_capacities"]
            and max(values["process_capacities"]) > values["capacity"]
        ):
            raise ValueError(
                f"process_capacities {values['process_capacities']} values must be smaller than capacity of resource {values['capacity']}."
            )
        return values

    def hash(self, production_system: ProductionSystemData) -> str:
        """
        Returns a unique hash of the resource considering the capacity, location (input/output for production resources or location for transport resources),
        controller, processes, process capacities, and states. Can be used to compare resources for equal functionality.

        Args:
            production_system (ProductionSystemData): Adapter that contains the process and state data.

        Raises:
            ValueError: If a state or process is not found in the adapter.

        Returns:
            str: Hash of the resource.
        """
        state_hashes = []
        process_hashes = []
        port_hashes = []

        base_class_hash = Locatable.hash(self)

        for state_id in self.state_ids:
            for state in production_system.state_data:
                if state.ID == state_id:
                    state_hashes.append(state.hash(production_system))
                    break
            else:
                raise ValueError(
                    f"State with ID {state_id} not found for resource {self.ID}."
                )

        for process_id in self.process_ids:
            for process in production_system.process_data:
                if process.ID == process_id:
                    process_hashes.append(process.hash(production_system))
                    break
            else:
                raise ValueError(
                    f"Process with ID {process_id} not found for resource {self.ID}."
                )

        # For production resources, include queues in the hash
        if self.ports:
            for port_id in self.ports:
                for port in production_system.port_data:
                    if port.ID == port_id:
                        port_hashes.append(port.hash())
                        break
                else:
                    raise ValueError(
                        f"Port with ID {port_id} not found for resource {self.ID}."
                    )

        components = [
            base_class_hash,
            str(self.capacity),
            self.controller.value,
            *sorted(process_hashes),
            *map(str, self.process_capacities or []),
            *sorted(state_hashes),
        ]

        if self.ports:
            components.extend(sorted(port_hashes))
        if self.can_move is not None:
            components.append(str(self.can_move))

        return md5(("".join(components)).encode("utf-8")).hexdigest()

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                # Production resource example
                {
                    "ID": "R1",
                    "description": "Production Resource",
                    "capacity": 2,
                    "location": [10.0, 10.0],
                    "controller": "PipelineController",
                    "control_policy": "FIFO",
                    "process_ids": ["P1", "P2"],
                    "process_capacities": [2, 1],
                    "state_ids": ["Breakdownstate_1"],
                    "ports": ["IQ1", "OQ1"],
                    "buffers": ["SQ1"],
                    "can_move": False,
                },
                # Transport resource example
                {
                    "ID": "TR1",
                    "description": "Transport Resource",
                    "capacity": 1,
                    "location": [15.0, 15.0],
                    "controller": "TransportController",
                    "control_policy": "FIFO",
                    "process_ids": ["TP1"],
                    "state_ids": ["Breakdownstate_1"],
                    "can_move": True,
                },
            ]
        }
    )


class SystemResourceData(ResourceData):
    """
    Class that represents system resource data. A system resource is a resource with subresources that can be used interchangeably.

    Args:
        ID (str): ID of the system resource.
        description (str): Description of the system resource.
        capacity (int): Capacity of the system resource.
        location (List[float]): Location of the system resource.
        controller (ControllerEnum): Controller of the system resource.
        control_policy (Union[ResourceControlPolicy, TransportControlPolicy]): Control policy of the system resource.
        process_ids (List[str]): Process IDs of the system resource.
        subresource_ids (List[str]): List of subresource IDs that are part of this system.
        system_ports (Optional[List[str]], optional): List of system port IDs for external communication. Defaults to None.
        internal_routing_matrix (Optional[Dict[str, List[str]]], optional): Internal routing matrix for routing within the system. Defaults to None.
        process_capacities (Optional[List[int]], optional): Process capacities of the system resource. Defaults to None.
        state_ids (Optional[List[str]], optional): State IDs of the system resource. Defaults to [].
        ports (Optional[List[str]], optional): List of port IDs that are used by the system resource. Defaults to None.
        can_move (Optional[bool], optional): Whether the system resource can move. Defaults to None.
        dependency_ids (List[str]): List of dependency IDs that are required by the system resource.
    """
    resource_type: ResourceType = ResourceType.SYSTEM
    subresource_ids: List[str]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ID": "SR1",
                    "description": "System Resource 1",
                    "capacity": 1,
                    "location": [20.0, 20.0],
                    "controller": "PipelineController",
                    "control_policy": "FIFO",
                    "process_ids": ["P1", "P2"],
                    "subresource_ids": ["R1", "R2", "R3"],
                    "process_capacities": [1, 1],
                    "state_ids": [],
                    "ports": ["IQ1", "OQ1"],
                    "buffers": [], 
                    "can_move": False,
                }
            ]
        }
    )

    def hash(self, production_system: ProductionSystemData) -> str:
        """
        Returns a unique hash of the system resource considering the subresources and internal routing.

        Args:
            production_system (ProductionSystemData): Adapter that contains the resource data.

        Returns:
            str: Hash of the system resource.
        """
        base_hash = super().hash(production_system)
        
        # Add subresource hashes
        subresource_hashes = []
        for subresource_id in self.subresource_ids:
            for resource in production_system.resource_data:
                if resource.ID == subresource_id:
                    subresource_hashes.append(resource.hash(production_system))
                    break
            else:
                raise ValueError(
                    f"Subresource with ID {subresource_id} not found for system resource {self.ID}."
                )
        
        # Add system port hashes
        system_port_hashes = []
        if self.system_ports:
            for port_id in self.system_ports:
                for port in production_system.port_data:
                    if port.ID == port_id:
                        system_port_hashes.append(port.hash())
                        break
                else:
                    raise ValueError(
                        f"System port with ID {port_id} not found for system resource {self.ID}."
                    )
        
        # Add internal routing matrix hash
        routing_hash = ""
        if self.internal_routing_matrix:
            routing_hash = "".join([f"{k}:{','.join(sorted(v))}" for k, v in sorted(self.internal_routing_matrix.items())])
        
        components = [
            base_hash,
            *sorted(subresource_hashes),
            *sorted(system_port_hashes),
            routing_hash,
        ]
        
        return md5("".join(components).encode("utf-8")).hexdigest()
