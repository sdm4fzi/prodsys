from __future__ import annotations

from hashlib import md5
import datetime
import json
from typing import List, Any, Set, Optional, Tuple, Union, Literal
from pydantic import (
    BaseModel,
    ConfigDict,
    TypeAdapter,
    field_validator,
    model_validator,
    ValidationInfo,
)

import logging

logger = logging.getLogger(__name__)

from prodsys.models import port_data, performance_data
from prodsys.models import (
    dependency_data,
    node_data,
    order_data as order_data_module,
    product_data,
    resource_data,
    sink_data,
    source_data,
    time_model_data as time_model_data_module,
)
from prodsys.models import state_data as state_data_module
from prodsys.models import processes_data as processes_data_module
from prodsys.models import sink_data as sink_data_module
from prodsys.models import source_data as source_data_module
from prodsys.models import resource_data as resource_data_module
from prodsys.models import product_data as product_data_module
from prodsys.models import port_data as queue_data_module
from prodsys.models import node_data as node_data_module
from prodsys.models import scenario_data as scenario_data_module
from prodsys.models import dependency_data as dependency_data_module
from prodsys.models import primitives_data as primitives_data_module
from prodsys.util import util
from prodsys.models.processes_data import LinkTransportProcessData

def get_production_resources(
    adapter: ProductionSystemData,
) -> List[resource_data_module.ResourceData]:
    """
    Returns a list of all machines in the adapter.
    Resources are considered production resources if they have production or capability processes.

    Args:
        adapter (ProductionSystemAdapter): ProductionSystemAdapter object

    Returns:
        List[resource_data_module.ResourceData]: List of all machines in the adapter
    """
    # Get all production process IDs (flatten tuples for compound processes)
    production_process_ids = get_possible_production_processes_IDs(adapter)
    flat_production_ids = set()
    for p_id in production_process_ids:
        if isinstance(p_id, tuple):
            flat_production_ids.update(p_id)
        else:
            flat_production_ids.add(p_id)
    
    # Return resources that have at least one production process
    return [
        resource
        for resource in adapter.resource_data
        if any(proc_id in flat_production_ids for proc_id in resource.process_ids)
    ]


def get_transport_resources(
    adapter: ProductionSystemData,
) -> List[resource_data_module.ResourceData]:
    """
    Returns a list of all transport resources in the adapter.
    Resources are considered transport resources if they have transport processes.

    Args:
        adapter (ProductionSystemAdapter): ProductionSystemAdapter object

    Returns:
        List[resource_data_module.ResourceData]: List of all transport resources in the adapter
    """
    # Get all transport process IDs
    transport_process_ids = set(get_possible_transport_processes_IDs(adapter))
    
    # Return resources that have at least one transport process
    return [
        resource
        for resource in adapter.resource_data
        if any(proc_id in transport_process_ids for proc_id in resource.process_ids)
    ]


def get_set_of_IDs(list_of_objects: List[Any]) -> Set[str]:
    """
    Returns a set of all IDs of the objects in the list, by utilizing the ID attribute of the objects.

    Args:
        list_of_objects (List[Any]): List of objects that have an ID attribute

    Returns:
        Set[str]: Set of all IDs of the objects in the list
    """
    return set([obj.ID for obj in list_of_objects])


def has_only_transport_processes(resource: resource_data_module.ResourceData, available_processes: List[processes_data_module.PROCESS_DATA_UNION]) -> bool:
    process_objects = [process for process in available_processes if process.ID in resource.process_ids]
    return all(process.type in [
        processes_data_module.ProcessTypeEnum.TransportProcesses, 
    processes_data_module.ProcessTypeEnum.LinkTransportProcesses
    ] for process in process_objects)


def get_default_queue_for_resource(
    resource: resource_data_module.ResourceData,
    adapter: ProductionSystemData,
    queue_capacity: Union[float, int] = 0.0,
) -> Optional[queue_data_module.QueueData]:
    """
    Returns default input and output queues for the given resource.

    Args:
        resource (resource_data_module.ResourceData): Resource for which the default queues should be returned
        queue_capacity (Union[float, int], optional): Capacity of the default queues. Defaults to 0.0 (infinite queue).
        adapter (Optional[ProductionSystemData], optional): Production system adapter containing process data. 
                                                           Required for accurate transport resource detection. Defaults to None.

    Returns:
        tuple[queue_data_module.QueueData, queue_data_module.QueueData]: Tuple of (input_queue, output_queue)
    """
    # Determine if this is a transport resource by checking:
    # 1. First priority: check if resource has transport processes (if adapter provided)
    # 2. Fallback: check can_move attribute
    if has_only_transport_processes(resource, adapter.process_data):
        return None
    
    # For production resources, create separate input and output queues
    queue = queue_data_module.QueueData(
            ID=resource.ID + "_default_queue",
            description="Default queue of " + resource.ID,
            capacity=queue_capacity,
            location=resource.location,
            interface_type=port_data.PortInterfaceType.INPUT_OUTPUT,
            port_type=port_data.PortType.QUEUE,
        )
    return queue

def remove_queues_from_resource(machine: resource_data_module.ResourceData):
    machine.ports = []


def remove_queues_from_resources(
    machines: List[resource_data_module.ResourceData],
):
    for machine in machines:
        remove_queues_from_resource(machine)


def remove_queues_from_source(source: source_data_module.SourceData):
    source.ports = []


def remove_queues_from_sink(sink: sink_data_module.SinkData):
    sink.ports = []


def remove_unused_queues_from_adapter(
    adapter: ProductionSystemData,
) -> ProductionSystemData:
    used_queues_ids = set(
        [queue_ID for machine in adapter.resource_data for queue_ID in (machine.ports or [])]
        + [queue_ID for source in adapter.source_data for queue_ID in (source.ports or [])]
        + [queue_ID for sink in adapter.sink_data for queue_ID in (sink.ports or [])]
        + [
            queue_ID
            for primitive in adapter.primitive_data
            for queue_ID in primitive.storages
        ]
    )
    queues_to_remove = []
    for queue in adapter.port_data:
        if queue.ID not in used_queues_ids:
            queues_to_remove.append(queue)
    for queue in queues_to_remove:
        adapter.port_data.remove(queue)
    return adapter

def has_input_port(locatable: resource_data_module.ResourceData, adapter: ProductionSystemData) -> bool:
    if not locatable.ports:
        return False
    ports = [port for port in adapter.port_data if port.ID in locatable.ports]
    return any(port.interface_type in [port_data.PortInterfaceType.INPUT, port_data.PortInterfaceType.INPUT_OUTPUT] for port in ports)

def has_output_port(locatable: resource_data_module.ResourceData, adapter: ProductionSystemData) -> bool:
    if not locatable.ports:
        return False
    ports = [port for port in adapter.port_data if port.ID in locatable.ports]
    return any(port.interface_type in [port_data.PortInterfaceType.OUTPUT, port_data.PortInterfaceType.INPUT_OUTPUT] for port in ports)

def add_default_queues_to_resources(
    adapter: ProductionSystemData, queue_capacity=0.0, reset=True
) -> ProductionSystemData:
    """
    Convenience function to add default queues to all resources in the adapter.
    Creates both input and output queues for production resources, and a single 
    input_output queue for transport resources.

    Args:
        adapter (ProductionSystemAdapter): ProductionSystemAdapter object
        queue_capacity (float, optional): Capacity of the default queues. Defaults to 0.0 (infinite queue).
        reset (bool, optional): If True, removes existing ports and creates new ones. If False, only adds ports if missing. Defaults to True.

    Returns:
        ProductionSystemAdapter: ProductionSystemAdapter object with default queues added to all resources
    """
    for resource in adapter.resource_data:
        transport_process_ids = set(get_possible_transport_processes_IDs(adapter))
        is_transport_resource = any(proc_id in transport_process_ids for proc_id in resource.process_ids)

        if (not reset and has_input_port(resource, adapter) and has_output_port(resource, adapter)) or is_transport_resource:
            continue
        remove_queues_from_resource(resource)
        remove_unused_queues_from_adapter(adapter)
        
        # Get both input and output queues, passing adapter for proper transport resource detection
        default_queue = get_default_queue_for_resource(
            resource, adapter, queue_capacity
        )
        if default_queue is not None:
            # Add queues to adapter
            adapter.port_data.append(default_queue)
            resource.ports = [default_queue.ID]
    return adapter


def get_default_queue_for_source(
    source: source_data_module.SourceData, queue_capacity=0.0
) -> queue_data_module.QueueData:
    """
    Returns a default queue for the given source.

    Args:
        source (source_data_module.SourceData): Source for which the default queue should be returned
        queue_capacity (float, optional): Capacity of the default queue. Defaults to 0.0 (infinite queue).

    Returns:
        queue_data_module.QueueData: Default queue for the given source
    """
    return queue_data_module.QueueData(
        ID=source.ID + "_default_output_queue",
        description="Default output queue of " + source.ID,
        capacity=queue_capacity,
        location=source.location,
        interface_type=port_data.PortInterfaceType.OUTPUT,
        port_type=port_data.PortType.QUEUE,
    )


def add_default_queues_to_sources(
    adapter: ProductionSystemData, queue_capacity=0.0, reset=True
) -> ProductionSystemData:
    """
    Convenience function to add default queues to all sources in the adapter.

    Args:
        adapter (ProductionSystemAdapter): ProductionSystemAdapter object
        queue_capacity (float, optional): Capacity of the default queues. Defaults to 0.0 (infinite queue).

    Returns:
        ProductionSystemAdapter: ProductionSystemAdapter object with default queues added to all sources
    """
    for source in adapter.source_data:
        if not reset and has_output_port(source, adapter):
            continue
        remove_queues_from_source(source)
        remove_unused_queues_from_adapter(adapter)

        output_queues = [get_default_queue_for_source(source, queue_capacity)]
        source.ports = list(get_set_of_IDs(output_queues))
        adapter.port_data += output_queues
    return adapter


def get_default_queue_for_sink(
    sink: sink_data_module.SinkData, queue_capacity=0.0
) -> queue_data_module.QueueData:
    """
    Returns a default queue for the given sink.

    Args:
        sink (sink_data_module.SinkData): Sink for which the default queue should be returned
        queue_capacity (float, optional): Capacity of the default queue. Defaults to 0.0 (infinite queue).

    Returns:
        queue_data_module.QueueData: Default queue for the given sink
    """
    return queue_data_module.QueueData(
        ID=sink.ID + "_default_input_queue",
        description="Default input queue of " + sink.ID,
        capacity=queue_capacity,
        location=sink.location,
        interface_type=port_data.PortInterfaceType.INPUT,
        port_type=port_data.PortType.QUEUE,
    )


def add_default_queues_to_sinks(
    adapter: ProductionSystemData, queue_capacity=0.0, reset=True
) -> ProductionSystemData:
    """
    Convenience function to add default queues to all sinks in the adapter.

    Args:
        adapter (ProductionSystemAdapter): ProductionSystemAdapter object
        queue_capacity (float, optional): Capacity of the default queues. Defaults to 0.0 (infinite queue).

    Returns:
        ProductionSystemAdapter: ProductionSystemAdapter object with default queues added to all sinks
    """
    for sink in adapter.sink_data:
        if not reset and has_input_port(sink, adapter):
            continue
        remove_queues_from_sink(sink)
        remove_unused_queues_from_adapter(adapter)

        input_queues = [get_default_queue_for_sink(sink, queue_capacity)]
        sink.ports = list(get_set_of_IDs(input_queues))
        adapter.port_data += input_queues
    return adapter


def add_default_queues_to_production_system(
    adapter: ProductionSystemData, queue_capacity=0.0, reset=True
) -> ProductionSystemData:
    """
    Convenience function to add default queues to all machines, sources and sinks in the adapter.

    Args:
        adapter (ProductionSystemAdapter): ProductionSystemAdapter object
        queue_capacity (float, optional): Capacity of the default queues. Defaults to 0.0 (infinite queue).

    Returns:
        ProductionSystemAdapter: ProductionSystemAdapter object with default queues added to all machines, sources and sinks
    """
    adapter = add_default_queues_to_resources(adapter, queue_capacity, reset)
    adapter = add_default_queues_to_sources(adapter, queue_capacity, reset)
    adapter = add_default_queues_to_sinks(adapter, queue_capacity, reset)
    return adapter


def load_json(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as json_file:
        data = json.load(json_file)
    return data


class ProductionSystemData(BaseModel):
    """
    A ProductionSystemAdapter serves as a n abstract base class of a data container to represent a production system. It is based on the `prodsys.models` module, but is also compatible with the `prodsys.express` API.
    It is used as the basis for all simulation and optimization algorithms in prodsys and comes with complete data validation.
    Thereby, it is assured that the expected data is used for simulation and optimization. If the data is not valid, an error is raised with information about the reasons for invalidity.
    The adapter targets easy integration of algorithms with each other in different environments.
    Therefore, the adapter can even be used for integration of new algorithms by serving as a defined data interface.

    Args:
        ID (str, optional): ID of the production system. Defaults to "".
        seed (int, optional): Seed for the random number generator used in simulation. Defaults to 0.
        time_model_data (List[time_model_data_module.TIME_MODEL_DATA], optional): List of time models used by the entities in the production system. Defaults to [].
        state_data (List[state_data_module.STATE_DATA_UNION], optional): List of states used by the resources in the production system. Defaults to [].
        process_data (List[processes_data_module.PROCESS_DATA_UNION], optional): List of processes required by products and provided by resources in the production system. Defaults to [].
        port_data (List[queue_data_module.QueueData], optional): List of ports used by the resources, sources and sinks in the production system. Defaults to [].
        node_data (List[resource_data_module.NodeData], optional): List of nodes in the production system. Defaults to [].
        resource_data (List[resource_data_module.RESOURCE_DATA_UNION], optional): List of resources in the production system. Defaults to [].
        product_data (List[product_data_module.ProductData], optional): List of products in the production system. Defaults to []
        sink_data (List[sink_data_module.SinkData], optional): List of sinks in the production system. Defaults to [].
        source_data (List[source_data_module.SourceData], optional): List of sources in the production system. Defaults to [].
        scenario_data (Optional[scenario_data_module.ScenarioData], optional): Scenario data of the production system used for optimization. Defaults to None.
        schedule (Optional[List[performance_data.Event]], optional): List of scheduled Events of the production system. Defaults to None.
        order_data (Optional[List[order_data_module.OrderData]], optional): List of orders in the production system. Defaults to None.
        conwip_number (Optional[int], optional): Number of allowed WIP (Work in Progress - number of released products) in the production system. Defaults to None.
        reference_time (Optional[datetime.datetime], optional): Reference time of the production system. Defaults to None.
        time_unit (Literal["s", "min", "h", "d"], optional): Time unit of the production system. Defaults to "min".
        valid_configuration (bool, optional): Indicates if the configuration is valid. Defaults to True.
        reconfiguration_cost (float, optional): Cost of reconfiguration in a optimization scenario. Defaults to 0.
    """

    # TODO: add check, that throws an error, if items have the same ID!
    ID: str = ""
    seed: int = 0
    time_model_data: List[time_model_data_module.TIME_MODEL_DATA] = []
    state_data: List[state_data_module.STATE_DATA_UNION] = []
    process_data: List[processes_data_module.PROCESS_DATA_UNION] = []
    port_data: List[queue_data_module.QUEUE_DATA_UNION] = []
    node_data: List[node_data_module.NodeData] = []
    resource_data: List[resource_data_module.ResourceData] = []
    product_data: List[product_data_module.ProductData] = []
    sink_data: List[sink_data_module.SinkData] = []
    source_data: List[source_data_module.SourceData] = []
    scenario_data: Optional[scenario_data_module.ScenarioData] = None
    dependency_data: Optional[List[dependency_data_module.DEPENDENCY_TYPES]] = []
    primitive_data: Optional[List[primitives_data_module.StoredPrimitive]] = []
    schedule: Optional[List[performance_data.Event]] = None
    order_data: Optional[List[order_data_module.OrderData]] = None
    conwip_number: Optional[int] = None
    reference_time: Optional[datetime.datetime] = None
    time_unit: Literal["s", "min", "h", "d"] = "min"

    valid_configuration: bool = True
    reconfiguration_cost: float = 0

    model_config = ConfigDict(
        validate_assignment=True,
        revalidate_instances='always',
        json_schema_extra={
            "examples": [
                # TODO: update data here
                {
                    "ID": "Example Adapter",
                    "valid_configuration": True,
                    "reconfiguration_cost": 0,
                    "seed": 24,
                    "time_model_data": [
                        {
                            "ID": "function_time_model_1",
                            "description": "normal distribution time model with 20 minutes",
                            "distribution_function": "normal",
                            "location": 14.3,
                            "scale": 5.0,
                            "batch_size": 100,
                        },
                        {
                            "ID": "function_time_model_2",
                            "description": "constant distribution time model with 10 minutes",
                            "distribution_function": "constant",
                            "location": 15.0,
                            "scale": 0.0,
                            "batch_size": 100,
                        },
                        {
                            "ID": "function_time_model_3",
                            "description": "normal distribution time model with 20 minutes",
                            "distribution_function": "normal",
                            "location": 20.0,
                            "scale": 5.0,
                            "batch_size": 100,
                        },
                        {
                            "ID": "function_time_model_4",
                            "description": "exponential distribution time model with 100 minutes",
                            "distribution_function": "exponential",
                            "location": 52.0,
                            "scale": 0.0,
                            "batch_size": 100,
                        },
                        {
                            "ID": "function_time_model_5",
                            "description": "exponential distribution time model with 150 minutes",
                            "distribution_function": "exponential",
                            "location": 150.0,
                            "scale": 0.0,
                            "batch_size": 100,
                        },
                        {
                            "ID": "sequential_time_model_1",
                            "description": "Sequential time model",
                            "sequence": [25.0, 13.0, 15.0, 16.0, 17.0, 20.0, 21.0],
                        },
                        {
                            "ID": "manhattan_time_model_1",
                            "description": "manhattan time model with speed 180 m/min = 3 m/s",
                            "speed": 30.0,
                            "reaction_time": 0.15,
                        },
                        {
                            "ID": "function_time_model_7",
                            "description": "exponential distribution time model with 300 minutes",
                            "distribution_function": "exponential",
                            "location": 300.0,
                            "scale": 0.0,
                            "batch_size": 100,
                        },
                        {
                            "ID": "function_time_model_8",
                            "description": "normal distribution time model with 15 minutes",
                            "distribution_function": "normal",
                            "location": 15.0,
                            "scale": 3.0,
                            "batch_size": 100,
                        },
                    ],
                    "state_data": [
                        {
                            "ID": "Breakdownstate_1",
                            "description": "Breakdown state machine 1",
                            "time_model_id": "function_time_model_5",
                            "type": "BreakDownState",
                            "repair_time_model_id": "function_time_model_8",
                        },
                        {
                            "ID": "Breakdownstate_2",
                            "description": "Breakdown state machine 2",
                            "time_model_id": "function_time_model_5",
                            "type": "BreakDownState",
                            "repair_time_model_id": "function_time_model_8",
                        },
                        {
                            "ID": "Setup_State_1",
                            "description": "Setup state machine 1",
                            "time_model_id": "function_time_model_2",
                            "type": "SetupState",
                            "origin_setup": "P1",
                            "target_setup": "P2",
                        },
                        {
                            "ID": "Setup_State_2",
                            "description": "Setup state machine 2",
                            "time_model_id": "function_time_model_2",
                            "type": "SetupState",
                            "origin_setup": "P2",
                            "target_setup": "P1",
                        },
                        {
                            "ID": "Setup_State_3",
                            "description": "Setup state machine 3",
                            "time_model_id": "function_time_model_2",
                            "type": "SetupState",
                            "origin_setup": "P1",
                            "target_setup": "P3",
                        },
                        {
                            "ID": "Setup_State_4",
                            "description": "Setup state machine 3",
                            "time_model_id": "function_time_model_3",
                            "type": "SetupState",
                            "origin_setup": "P3",
                            "target_setup": "P1",
                        },
                        {
                            "ID": "ProcessBreakdownState_1",
                            "description": "Breakdown state process 1",
                            "time_model_id": "function_time_model_7",
                            "type": "ProcessBreakDownState",
                            "repair_time_model_id": "function_time_model_8",
                            "process_id": "P1",
                        },
                    ],
                    "process_data": [
                        {
                            "ID": "P1",
                            "description": "Process 1",
                            "time_model_id": "function_time_model_1",
                            "type": "ProductionProcesses",
                        },
                        {
                            "ID": "P2",
                            "description": "Process 2",
                            "time_model_id": "function_time_model_2",
                            "type": "ProductionProcesses",
                        },
                        {
                            "ID": "P3",
                            "description": "Process 3",
                            "time_model_id": "function_time_model_3",
                            "type": "ProductionProcesses",
                        },
                        {
                            "ID": "TP1",
                            "description": "Transport Process 1",
                            "time_model_id": "manhattan_time_model_1",
                            "loading_time_model_id": "function_time_model_2",
                            "unloading_time_model_id": "function_time_model_3",
                            "type": "TransportProcesses",
                        },
                    ],
                    "port_data": [
                        {
                            "ID": "IQ1",
                            "description": "Input-queue 1 for R1",
                            "capacity": 10,
                        },
                        {
                            "ID": "OQ1",
                            "description": "Output-queue 1 for R1",
                            "capacity": 10,
                        },
                        {
                            "ID": "OQ2",
                            "description": "Output-queue 2 for R2",
                            "capacity": 10,
                        },
                        {
                            "ID": "IQ2",
                            "description": "Input-queue 2 for R3",
                            "capacity": 10,
                        },
                        {
                            "ID": "OQ3",
                            "description": "Output-queue 3 for R3",
                            "capacity": 10,
                        },
                        {
                            "ID": "SourceQueue",
                            "description": "Output-Queue for all sources",
                            "capacity": 0,
                        },
                        {
                            "ID": "SinkQueue",
                            "description": "Input-Queue for all sinks",
                            "capacity": 0,
                        },
                        {
                            "ID": "IQ9",
                            "description": "Input-queue 1 for R2",
                            "capacity": 10,
                        },
                    ],
                    "resource_data": [
                        {
                            "ID": "R1",
                            "description": "Resource 1",
                            "capacity": 2,
                            "input_location": [10.0, 10.0],
                            "output_location": [12.0, 10.0],
                            "controller": "PipelineController",
                            "control_policy": "FIFO",
                            "process_ids": ["P1", "P2"],
                            "process_capacities": [2, 1],
                            "state_ids": [
                                "Breakdownstate_1",
                                "Setup_State_1",
                                "Setup_State_2",
                                "ProcessBreakdownState_1",
                            ],
                            "input_queues": ["IQ1"],
                            "output_queues": ["OQ1"],
                        },
                        {
                            "ID": "R2",
                            "description": "Resource 2",
                            "capacity": 1,
                            "input_location": [20.0, 10.0],
                            "output_location": [22.0, 10.0],
                            "controller": "PipelineController",
                            "control_policy": "FIFO",
                            "process_ids": ["P2", "P3"],
                            "process_capacities": None,
                            "state_ids": ["Breakdownstate_2"],
                            "input_queues": ["IQ9"],
                            "output_queues": ["OQ2"],
                        },
                        {
                            "ID": "R3",
                            "description": "Resource 3",
                            "capacity": 2,
                            "input_location": [20.0, 20.0],
                            "output_location": [22.0, 22.0],
                            "controller": "PipelineController",
                            "control_policy": "FIFO",
                            "process_ids": ["P1", "P3"],
                            "process_capacities": [1, 2],
                            "state_ids": [
                                "Breakdownstate_1",
                                "Breakdownstate_2",
                                "Setup_State_3",
                                "Setup_State_4",
                            ],
                            "input_queues": ["IQ2"],
                            "output_queues": ["OQ3"],
                        },
                        {
                            "ID": "R4",
                            "description": "Resource 3",
                            "capacity": 2,
                            "input_location": [10.0, 20.0],
                            "output_location": [12.0, 20.0],
                            "controller": "PipelineController",
                            "control_policy": "FIFO",
                            "process_ids": ["P1", "P3"],
                            "process_capacities": [2, 2],
                            "state_ids": [
                                "Breakdownstate_1",
                                "Setup_State_3",
                                "Setup_State_4",
                            ],
                            "input_queues": ["IQ2"],
                            "output_queues": ["OQ3"],
                        },
                        {
                            "ID": "TR1",
                            "description": "Transport Resource 1",
                            "capacity": 1,
                            "location": [15.0, 15.0],
                            "controller": "TransportController",
                            "control_policy": "FIFO",
                            "process_ids": ["TP1"],
                            "process_capacities": None,
                            "state_ids": ["Breakdownstate_1"],
                        },
                        {
                            "ID": "TR2",
                            "description": "Transport Resource 2",
                            "capacity": 1,
                            "location": [15.0, 20.0],
                            "controller": "TransportController",
                            "control_policy": "SPT_transport",
                            "process_ids": ["TP1"],
                            "process_capacities": None,
                            "state_ids": ["Breakdownstate_1"],
                        },
                    ],
                    "product_data": [
                        {
                            "ID": "Product_1",
                            "description": "Product 1",
                            "product_type": "Product_1",
                            "processes": ["P1", "P2", "P3"],
                            "transport_process": "TP1",
                        },
                        {
                            "ID": "Product_2",
                            "description": "Product 2",
                            "product_type": "Product_2",
                            "processes": ["P1", "P2", "P3", "P1"],
                            "transport_process": "TP1",
                        },
                        {
                            "ID": "Product_3",
                            "description": "Product 3",
                            "product_type": "Product_3",
                            "processes": {"P1": ["P2", "P3"], "P2": [], "P3": []},
                            "transport_process": "TP1",
                        },
                    ],
                    "sink_data": [
                        {
                            "ID": "SK1",
                            "description": "Sink 1",
                            "input_location": [50.0, 50.0],
                            "product_type": "Product_1",
                            "input_queues": ["SinkQueue"],
                        },
                        {
                            "ID": "SK2",
                            "description": "Sink 2",
                            "input_location": [55.0, 50.0],
                            "product_type": "Product_2",
                            "input_queues": ["SinkQueue"],
                        },
                        {
                            "ID": "SK3",
                            "description": "Sink 3",
                            "input_location": [45.0, 50.0],
                            "product_type": "Product_3",
                            "input_queues": ["SinkQueue"],
                        },
                    ],
                    "source_data": [
                        {
                            "ID": "S1",
                            "description": "Source 1",
                            "output_location": [0.0, 0.0],
                            "product_type": "Product_1",
                            "time_model_id": "function_time_model_4",
                            "router": "SimpleRouter",
                            "routing_heuristic": "shortest_queue",
                            "output_queues": ["SourceQueue"],
                        },
                        {
                            "ID": "S2",
                            "description": "Source 2",
                            "output_location": [30.0, 30.0],
                            "product_type": "Product_2",
                            "time_model_id": "function_time_model_4",
                            "router": "SimpleRouter",
                            "routing_heuristic": "shortest_queue",
                            "output_queues": ["SourceQueue"],
                        },
                        {
                            "ID": "S3",
                            "description": "Source 3",
                            "output_location": [40.0, 30.0],
                            "product_type": "Product_3",
                            "time_model_id": "function_time_model_4",
                            "router": "SimpleRouter",
                            "routing_heuristic": "shortest_queue",
                            "output_queues": ["SourceQueue"],
                        },
                    ],
                    "scenario_data": None,
                }
            ]
        },
    )

    @classmethod
    def read(cls, filepath: str) -> ProductionSystemData:
        """
        Reads a JSON file and returns a ProductionSystemData object.

        Args:
            filepath (str): Path to the JSON file

        Returns:
            ProductionSystemData: ProductionSystemData object
        """
        data = load_json(filepath)
        return cls.model_validate(data)

    def write(self, filepath: str):
        """
        Writes the ProductionSystemData object to a JSON file.

        Args:
            filepath (str): Path to the JSON file
        """
        with open(filepath, "w", encoding="utf-8") as json_file:
            json_file.write(self.model_dump_json(indent=4))

    def revalidate(self) -> 'ProductionSystemData':
        """
        Explicitly revalidates the entire ProductionSystemData model.
        
        This is useful after making in-place modifications to lists (e.g., appending items)
        to ensure all validators run, including the duplicate ID check.
        
        Example:
            ```python
            system = ProductionSystemData(...)
            system.node_data.append(new_node)  # In-place modification
            system.revalidate()  # Trigger validation
            ```
        
        Returns:
            ProductionSystemData: Self, after validation
            
        Raises:
            ValueError: If validation fails (e.g., duplicate IDs detected)
        """
        # Trigger validation by re-parsing the model
        validated = self.model_validate(self.model_dump())
        # Update self with validated data
        for key, value in validated.__dict__.items():
            setattr(self, key, value)
        return self

    def hash(self) -> str:
        """
        Generates a hash of the adapter based on the hash of all contained entities. Only information describing the physical structure and functionality of the production system is considered. Can be used to compare two production systems of adapters for functional equality.

        Returns:
            str: Hash of the adapter
        """
        return md5(
            (
                "".join(
                    [
                        *sorted(
                            [time_model.hash() for time_model in self.time_model_data]
                        ),
                        *sorted([state.hash(self) for state in self.state_data]),
                        *sorted([process.hash(self) for process in self.process_data]),
                        *sorted([res.hash(self) for res in self.resource_data]),
                        *sorted([queue.hash() for queue in self.port_data]),
                        *sorted([node.hash() for node in self.node_data]),
                        *sorted([product.hash(self) for product in self.product_data]),
                        *sorted([sink.hash(self) for sink in self.sink_data]),
                        *sorted([source.hash(self) for source in self.source_data]),
                        *sorted(
                            [
                                dependency.hash(self)
                                for dependency in self.dependency_data
                            ]
                        ),
                        *sorted(
                            [primitive.hash(self) for primitive in self.primitive_data]
                        ),
                    ]
                )
            ).encode("utf-8")
        ).hexdigest()

    @model_validator(mode='after')
    def check_no_duplicate_ids(self) -> 'ProductionSystemData':
        """
        Validates that no duplicate IDs exist across all data types in the production system.
        This is critical for proper object resolution, especially for link transport processes.
        
        This validator runs automatically:
        - On initialization of a new ProductionSystemData instance
        - When entire fields are reassigned (e.g., `system.node_data = new_list`)
        
        For in-place mutations (e.g., `system.node_data.append(item)`), call `revalidate()` 
        or `model_validate()` explicitly to trigger validation.
        
        Raises:
            ValueError: If duplicate IDs are found with details about which IDs and where.
        """
        id_registry = {}  # Maps ID to list of (field_name, object_type) tuples
        
        # Define all fields to check
        fields_to_check = [
            ('time_model_data', self.time_model_data, 'TimeModel'),
            ('state_data', self.state_data, 'State'),
            ('process_data', self.process_data, 'Process'),
            ('port_data', self.port_data, 'Port/Queue'),
            ('node_data', self.node_data, 'Node'),
            ('resource_data', self.resource_data, 'Resource'),
            ('product_data', self.product_data, 'Product'),
            ('sink_data', self.sink_data, 'Sink'),
            ('source_data', self.source_data, 'Source'),
            ('depdendency_data', self.dependency_data or [], 'Dependency'),
            ('primitive_data', self.primitive_data or [], 'Primitive'),
        ]
        
        # Collect all IDs and their locations
        for field_name, data_list, object_type in fields_to_check:
            for item in data_list:
                if hasattr(item, 'ID'):
                    item_id = item.ID
                    if item_id not in id_registry:
                        id_registry[item_id] = []
                    id_registry[item_id].append((field_name, object_type))
        
        # Find duplicates
        duplicates = {id_: locations for id_, locations in id_registry.items() if len(locations) > 1}
        
        if duplicates:
            error_messages = []
            for duplicate_id, locations in duplicates.items():
                location_strs = [f"{obj_type} (in {field})" for field, obj_type in locations]
                error_messages.append(
                    f"  - ID '{duplicate_id}' is used in: {', '.join(location_strs)}"
                )
            
            raise ValueError(
                "\n\nDuplicate IDs detected in ProductionSystemData!\n"
                "Each ID must be unique across ALL data types (nodes, sources, sinks, resources, ports, etc.).\n"
                "This is required for proper object resolution, especially for link transport processes.\n\n"
                "Duplicate IDs found:\n" + "\n".join(error_messages) + "\n\n"
                "Resolution: Please rename the conflicting objects to have unique IDs.\n"
                "Example: If both a Node and Source have ID 'S1', rename them to 'Node_S1' and 'Source_S1'.\n"
            )
        
        return self

    @field_validator("state_data")
    def check_states(
        cls, states: List[state_data_module.STATE_DATA_UNION], info: ValidationInfo
    ):
        values = info.data
        for state in states:
            time_models = get_set_of_IDs(values["time_model_data"])
            if state.time_model_id not in time_models:
                raise ValueError(
                    f"The time model {state.time_model_id} of state {state.ID} is not a valid time model of {time_models}."
                )
        return states

    @field_validator("process_data")
    def check_processes(
        cls,
        processes: List[processes_data_module.PROCESS_DATA_UNION],
        info: ValidationInfo,
    ):
        values = info.data
        for process in processes:
            if isinstance(
                process, processes_data_module.CompoundProcessData
            ) or isinstance(
                process, processes_data_module.RequiredCapabilityProcessData
            ) or isinstance(
                process, processes_data_module.ProcessModelData
            ):
                continue
            time_models = get_set_of_IDs(values["time_model_data"])
            if process.time_model_id not in time_models:
                raise ValueError(
                    f"The time model {process.time_model_id} of process {process.ID} is not a valid time model of {time_models}."
                )
        return processes

    @field_validator("resource_data")
    def check_resources(
        cls,
        resources: List[resource_data_module.ResourceData],
        info: ValidationInfo,
    ):
        values = info.data
        for resource in resources:
            processes = get_set_of_IDs(values["process_data"])
            for process in resource.process_ids:
                if process not in processes:
                    raise ValueError(
                        f"The process {process} of resource {resource.ID} is not a valid process of {processes}."
                    )
            states = get_set_of_IDs(values["state_data"])
            for state in resource.state_ids:
                if state not in states:
                    raise ValueError(
                        f"The state {state} of resource {resource.ID} is not a valid state of {states}."
                    )
            
            # Check if resource only has transport processes
            # If it does, no queues are required

            available_processes = values["process_data"]
            available_processes = TypeAdapter(List[processes_data_module.PROCESS_DATA_UNION]).validate_python(available_processes)

            only_transport_processes = has_only_transport_processes(resource, available_processes)

            
            # If resource has no ports and doesn't only have transport processes, add default queues
            if not resource.ports and not only_transport_processes:
                queue = queue_data_module.QueueData(
                    ID=resource.ID + "_default_queue",
                    description="Default queue of " + resource.ID,
                    capacity=0.0,
                    location=resource.location,
                    interface_type=port_data.PortInterfaceType.INPUT_OUTPUT,
                    port_type=port_data.PortType.QUEUE,
                )
                if "port_data" not in values:
                    values["port_data"] = []
                values["port_data"].append(queue)
                resource.ports = [queue.ID]
                
            port_data_ids = get_set_of_IDs(values["port_data"])
            
            # Validate ports if they exist (skip validation for transport-only resources without ports)
            if resource.ports:
                for port in resource.ports:
                    if port not in port_data_ids:
                        raise ValueError(
                            f"The port {port} of resource {resource.ID} is not a valid port of {port_data_ids}."
                        )
                resource_ports: list[port_data.QueueData] = [port for port in values["port_data"] if port.ID in resource.ports]
                if not any(
                    port.interface_type
                    in [
                        queue_data_module.PortInterfaceType.OUTPUT,
                        queue_data_module.PortInterfaceType.INPUT_OUTPUT,
                    ]
                    for port in resource_ports
                ):
                    raise ValueError(
                        f"The resource {resource.ID} has no output port. Resources must have at least one output port."
                    )
                if not any(port.interface_type in [queue_data_module.PortInterfaceType.INPUT, queue_data_module.PortInterfaceType.INPUT_OUTPUT] for port in resource_ports):
                    raise ValueError(
                        f"The resource {resource.ID} has no input port. Resources must have at least one input port."
                    )
        return resources

    @field_validator("product_data")
    def check_products(
        cls, products: List[product_data_module.ProductData], info: ValidationInfo
    ):
        values = info.data
        for product in products:
            all_processes = get_set_of_IDs(values["process_data"])
            if product.transport_process not in all_processes:
                raise ValueError(
                    f"The transport process {product.transport_process} of product {product.ID} is not a valid process of {all_processes}."
                )
            required_processes = set()
            if isinstance(product.processes, list) and isinstance(
                product.processes[0], str
            ):
                required_processes = set(product.processes)
            elif isinstance(product.processes, list) and isinstance(
                product.processes[0], list
            ):
                required_processes = set(util.flatten(product.processes))
            elif isinstance(product.processes, dict):
                required_processes = set(product.processes.keys())
            if required_processes - all_processes != set():
                raise ValueError(
                    f"The processes {required_processes - all_processes} of product {product.ID} are not a valid processes of {all_processes}."
                )

        return products

    @field_validator("sink_data")
    def check_sinks(cls, sinks: List[sink_data_module.SinkData], info: ValidationInfo):
        values = info.data
        for sink in sinks:
            try:
                product_types = set([product.type for product in values["product_data"]])
            except KeyError:
                raise ValueError("Product data is missing or faulty.")
            if sink.product_type not in product_types:
                raise ValueError(
                    f"The product type {sink.product_type} of sink {sink.ID} is not a valid product type of {product_types}."
                )
            if not sink.ports:
                input_queue = get_default_queue_for_sink(sink)
                sink.ports = list(get_set_of_IDs([input_queue]))
                values["port_data"] += [input_queue]
                continue
            ports = get_set_of_IDs(values["port_data"])
            for p in sink.ports:
                if p not in ports:
                    raise ValueError(
                        f"The port {p} of sink {sink.ID} is not a valid port of {ports}."
                    )
                for port in values["port_data"]:
                    if port.ID == p:
                        if port.capacity != 0:
                            logger.warning(
                                f"The capacity of the port {port.ID} of sink {sink.ID} is limited. This might lead to unexpected behavior so it was changed to infinity."
                            )
                            port.capacity = 0
            sink_ports : list[queue_data_module.QueueData] = [port for port in values["port_data"] if port.ID in sink.ports]
            if not any(port.interface_type in [queue_data_module.PortInterfaceType.INPUT, queue_data_module.PortInterfaceType.INPUT_OUTPUT] for port in sink_ports):
                raise ValueError(
                    f"The sink {sink.ID} has no input port. Sinks must have at least one input port."
                )
        return sinks

    @field_validator("source_data")
    def check_sources(
        cls, sources: List[source_data_module.SourceData], info: ValidationInfo
    ):
        values = info.data
        for source in sources:
            time_models = get_set_of_IDs(values["time_model_data"])
            if source.time_model_id not in time_models:
                raise ValueError(
                    f"The time model {source.time_model_id} of source {source.ID} is not a valid time model of {time_models}."
                )
            try:
                product_types = set([product.type for product in values["product_data"]])
            except KeyError:
                raise ValueError("Product data is missing or faulty.")
            if source.product_type not in product_types:
                raise ValueError(
                    f"The product type {source.product_type} of source {source.ID} is not a valid product type of {product_types}."
                )
            if not source.ports:
                output_queue = get_default_queue_for_source(source)
                source.ports = list(get_set_of_IDs([output_queue]))
                values["port_data"] += [output_queue]
                continue
            queues = get_set_of_IDs(values["port_data"])
            for q in source.ports:
                if q not in queues:
                    raise ValueError(
                        f"The queue {q} of source {source.ID} is not a valid queue of {queues}."
                    )
            source_ports: list[queue_data_module.QueueData] = [port for port in values["port_data"] if port.ID in source.ports]
            if not any(
                port.interface_type
                in [
                    queue_data_module.PortInterfaceType.OUTPUT,
                    queue_data_module.PortInterfaceType.INPUT_OUTPUT,
                ]
                for port in source_ports
            ):
                raise ValueError(
                    f"The source {source.ID} has no output port. Sources must have at least one output port."
                )
        return sources

    @field_validator("schedule")
    def check_schedule(
        cls, schedule: Optional[List[performance_data.Event]], info: ValidationInfo
    ):
        if schedule is None:
            return schedule
        event_resources_ids = set()
        event_process_ids = set()
        event_product_ids = set()
        schedule_to_consider = []
        for event in schedule:
            if not isinstance(event, performance_data.Event):
                raise ValueError(
                    f"The event {event} is not a valid event of {schedule}."
                )
            event_resources_ids.add(event.resource)
            product_id = "_".join(event.product.split("_")[:-1])
            event_product_ids.add(product_id)
            if event.process:
                event_process_ids.add(event.process)
            if not event.activity == "start state":
                continue
            schedule_to_consider.append(event)

        values = info.data
        resources_ids = get_set_of_IDs(values["resource_data"])
        processes_ids = get_set_of_IDs(values["process_data"])
        products_ids = get_set_of_IDs(values["product_data"])

        if event_resources_ids - resources_ids != set():
            raise ValueError(
                f"The resources {event_resources_ids - resources_ids} of the schedule are not valid resources of {resources_ids}."
            )
        if event_process_ids - processes_ids != set():
            raise ValueError(
                f"The processes {event_process_ids - processes_ids} of the schedule are not valid processes of {processes_ids}."
            )
        
        if event_product_ids - products_ids != set():
            raise ValueError(
                f"The products {event_product_ids - products_ids} of the schedule are not valid products of {products_ids}."
            )

        return schedule_to_consider

    def read_scenario(self, scenario_file_path: str):
        scenario_data = json.load(open(scenario_file_path))
        self.scenario_data = scenario_data_module.ScenarioData.model_validate_json(scenario_data)

    def validate_proceses_available(self):
        required_processes = set(
            util.flatten([product.processes for product in self.product_data])
        )
        available_processes = set()
        for resource in self.resource_data:
            for process in resource.process_ids:
                available_processes.add(process)
        if required_processes > available_processes:
            raise ValueError(
                f"The processes {required_processes - available_processes} are not available."
            )

    def validate_configuration(self):
        """
        Checks if the configuration is physically valid, i.e. if all resources are positioned at different locations and if all required processes are available.

        Raises:
            ValueError: If multiple objects are positioned at the same location.
            ValueError: If not all required process are available.
            ValueError: If not all links are available for LinkTransportProcesses.
            ValueError: If ports are missing locations (needed for transport routing).
        """
        assert_no_redundant_locations(self)
        assert_required_processes_in_resources_available(self)
        assert_all_links_available(self)
        assert_ports_have_locations(self)


def remove_duplicate_locations(input_list: List[List[float]]) -> List[List[float]]:
    return [list(x) for x in set(tuple(x) for x in input_list)]


def get_location_of_locatable(
    adapter: ProductionSystemData,
    locatable: Union[
        resource_data_module.ResourceData,
        source_data_module.SourceData,
        sink_data_module.SinkData,
        port_data.StoreData,
    ],
) -> List[List[float]]:
    locations = [locatable.location]
    if hasattr(locatable, "ports") and locatable.ports:
        for port_ID in locatable.ports:
            port = next((portx for portx in adapter.port_data if portx.ID == port_ID), None)
            if port.location != locatable.location:
                result = get_location_of_locatable(adapter, port)
                if isinstance(result, list):
                    locations.extend(result)
                else:
                    locations.append(result)
    return locations


def assert_no_redundant_locations(adapter: ProductionSystemData):
    """
    Asserts that no multiple objects are positioned at the same location.

    Args:
        adapter (ProductionSystemAdapter): Production system configuration

    Raises:
        ValueError: If multiple objects are positioned at the same location.
    """
    machine_locations = []
    for production_resource in get_production_resources(adapter):
        machine_locations.append(production_resource.location)
    source_locations = []
    for source in adapter.source_data:
        source_locations += get_location_of_locatable(adapter, source)
    source_locations = remove_duplicate_locations(source_locations)
    sink_locations = []
    for sink in adapter.sink_data:
        sink_locations += get_location_of_locatable(adapter, sink)
    sink_locations = remove_duplicate_locations(
        [sink.location for sink in adapter.sink_data]
    )
    store_locations = []
    for store in adapter.port_data:
        if not isinstance(store, port_data.StoreData):
            continue
        store_locations += get_location_of_locatable(adapter, store)

    positions = machine_locations + store_locations # + source_locations + sink_locations
    for location in positions:
        if positions.count(location) > 1:
            raise ValueError(
                f"Multiple objects are positioned at the same location: {location}"
            )


def assert_all_links_available(adapter: ProductionSystemData):
    """
    Asserts that all links are valid, so that the start and target of the link are valid locations.

    Args:
        adapter (ProductionSystemAdapter): Production system configuration

    Raises:
        ValueError: If the start or target of a link is not a valid location.
    """
    link_transport_processes = [
        process
        for process in adapter.process_data
        if isinstance(process, processes_data_module.LinkTransportProcessData)
    ]
    if not link_transport_processes:
        return
    nodes = get_set_of_IDs(adapter.node_data)
    resources = get_set_of_IDs(adapter.resource_data)
    sources = get_set_of_IDs(adapter.source_data)
    sinks = get_set_of_IDs(adapter.sink_data)
    ports = get_set_of_IDs(adapter.port_data)
    all_location_ids = nodes | resources | sources | sinks | ports
    for link_transport_process in link_transport_processes:
        link_pairs: List[List[str]] = []
        if isinstance(link_transport_process.links, dict):
            for start, targets in link_transport_process.links.items():
                for target in targets:
                    link_pairs.append([start, target])
        else:
            link_pairs = link_transport_process.links
        for start, target in link_pairs:
            if start not in all_location_ids:
                raise ValueError(
                    f"The link from {start} to {target} of process {link_transport_process.ID} is not a valid location because {start} is no valid location id."
                )
            if target not in all_location_ids:
                raise ValueError(
                    f"The link from {start} to {target} of process {link_transport_process.ID} is not a valid location because {target} is no valid location id."
                )


def assert_ports_have_locations(adapter: ProductionSystemData):
    """
    Checks if ports associated with resources have locations.
    Ports without locations cannot be used for transport routing.
    
    Note: Source and sink ports (SourceQueue, SinkQueue) are excluded from this check
    as they are logical grouping points that may be shared across multiple sources/sinks.

    Args:
        adapter (ProductionSystemAdapter): Adapter containing the production system to validate.

    Raises:
        ValueError: If resource ports are missing locations.
    """
    # Only check ports that are referenced by RESOURCES (not sources/sinks)
    # Sources and sinks use shared SourceQueue/SinkQueue which don't need individual locations
    resource_port_ids = set()
    for resource in adapter.resource_data:
        if resource.ports:
            resource_port_ids.update(resource.ports)
    
    # Check that all resource ports have locations
    ports_without_locations = []
    for port in adapter.port_data:
        if port.ID in resource_port_ids and port.location is None:
            # Skip common shared queues
            if port.ID in ['SourceQueue', 'SinkQueue']:
                continue
            ports_without_locations.append(port.ID)
    
    if ports_without_locations:
        raise ValueError(
            f"The following resource ports are missing locations (required for transport routing): {ports_without_locations}. "
            f"Ports must have locations to enable transport compatibility precomputation. "
            f"Use add_default_queues_to_resources() to automatically set port locations from resource locations."
        )


def check_for_clean_compound_processes(
    adapter_object: ProductionSystemData,
) -> bool:
    """
    Checks that the compound processes are clean, i.e. that they do not contain compund processes and normal processes at the same time.

    Args:
        adapter_object (ProductionSystemAdapter): Production system configuration

    Returns:
        bool: True if the compound processes are clean, False otherwise
    """
    possible_production_processes_ids = get_possible_production_processes_IDs(
        adapter_object
    )
    if any(
        isinstance(process_id, tuple)
        for process_id in possible_production_processes_ids
    ) and any(
        isinstance(process_id, str) for process_id in possible_production_processes_ids
    ):
        return False
    return True


def get_possible_production_processes_IDs(
    adapter_object: ProductionSystemData,
) -> Union[List[str], List[Tuple[str, ...]]]:
    """
    Returns all possible production processes IDs that can be used in the production system.
    Compund processes are grouped as touples, whereas individual processes are represented as strings.

    Args:
        adapter_object (ProductionSystemAdapter): Production system configuration

    Returns:
        Union[List[str], List[Tuple[str, ...]]]: List of production process IDs
    """
    possible_processes = [
        process
        for process in adapter_object.process_data
        if not isinstance(process, processes_data_module.TransportProcessData)
        and not isinstance(process, processes_data_module.RequiredCapabilityProcessData)
    ]
    compund_processes = [
        process
        for process in adapter_object.process_data
        if isinstance(process, processes_data_module.CompoundProcessData)
    ]
    compound_process_id_tuples = [
        tuple(compound_process.process_ids) for compound_process in compund_processes
    ]

    compound_processes_ids = set(
        [compound_process.ID for compound_process in compund_processes]
    )
    compound_processes_contained_process_ids = set(
        util.flatten(compound_process_id_tuples)
    )
    individual_processes_ids = [
        process.ID
        for process in possible_processes
        if process.ID not in compound_processes_contained_process_ids
        and process.ID not in compound_processes_ids
    ]

    return individual_processes_ids + compound_process_id_tuples


def get_possible_transport_processes_IDs(
    adapter_object: ProductionSystemData,
) -> List[str]:
    possible_processes = adapter_object.process_data
    return [
        process.ID
        for process in possible_processes
        if isinstance(process, processes_data_module.TransportProcessData)
    ]


def get_production_processes_from_ids(
    adapter_object: ProductionSystemData, process_ids: List[str]
) -> List[processes_data_module.PROCESS_DATA_UNION]:
    processes = []
    for process_id in process_ids:
        for process in adapter_object.process_data:
            if process.ID == process_id and (
                isinstance(process, processes_data_module.ProductionProcessData)
                or isinstance(process, processes_data_module.ReworkProcessData)
            ):
                processes.append(process)
                break
    return processes


def get_transport_processes_from_ids(
    adapter_object: ProductionSystemData, process_ids: List[str]
) -> List[processes_data_module.PROCESS_DATA_UNION]:
    processes = []
    for process_id in process_ids:
        for process in adapter_object.process_data:
            if (
                process.ID == process_id
                and isinstance(process, processes_data_module.TransportProcessData)
                and not (
                    hasattr(process, "capability") and getattr(process, "capability")
                )
            ):
                processes.append(process)
                break
    return processes


def get_capability_processes_from_ids(
    adapter_object: ProductionSystemData, process_ids: List[str]
) -> List[processes_data_module.PROCESS_DATA_UNION]:
    processes = []
    for process_id in process_ids:
        for process in adapter_object.process_data:
            if process.ID == process_id and (
                isinstance(process, processes_data_module.CapabilityProcessData)
                or (hasattr(process, "capability") and getattr(process, "capability"))
            ):
                processes.append(process)
                break
    return processes


def get_compound_processes_from_ids(
    adapter_object: ProductionSystemData, process_ids: List[str]
) -> List[processes_data_module.PROCESS_DATA_UNION]:
    processes = []
    for process_id in process_ids:
        for process in adapter_object.process_data:
            if process.ID == process_id and isinstance(
                process, processes_data_module.CompoundProcessData
            ):
                processes.append(process)
    return processes


def get_required_capability_processes_from_ids(
    adapter_object: ProductionSystemData, process_ids: List[str]
) -> List[processes_data_module.PROCESS_DATA_UNION]:
    processes = []
    for process_id in process_ids:
        for process in adapter_object.process_data:
            if process.ID == process_id and isinstance(
                process, processes_data_module.RequiredCapabilityProcessData
            ):
                processes.append(process)
    return processes


def get_contained_production_processes_from_compound_processes(
    adapter_object: ProductionSystemData,
    compound_processes: List[processes_data_module.CompoundProcessData],
) -> List[processes_data_module.PROCESS_DATA_UNION]:
    processes = []
    for compound_process in compound_processes:
        for process_id in compound_process.process_ids:
            processes = get_production_processes_from_ids(adapter_object, [process_id])
            if len(processes) > 1:
                raise ValueError(f"Multiple processes with ID {process_id} found.")
            if processes:
                process = processes[0]
                processes.append(process)
    return processes


def get_contained_capability_processes_from_compound_processes(
    adapter_object: ProductionSystemData,
    compound_processes: List[processes_data_module.CompoundProcessData],
) -> List[processes_data_module.PROCESS_DATA_UNION]:
    processes = []
    for compound_process in compound_processes:
        for process_id in compound_process.process_ids:
            processes = get_capability_processes_from_ids(adapter_object, [process_id])
            if len(processes) > 1:
                raise ValueError(f"Multiple processes with ID {process_id} found.")
            if processes:
                process = processes[0]
                processes.append(process)
    return processes


def get_contained_transport_processes_from_compound_processes(
    adapter_object: ProductionSystemData,
    compound_processes: List[processes_data_module.CompoundProcessData],
) -> List[processes_data_module.PROCESS_DATA_UNION]:
    processes = []
    for compound_process in compound_processes:
        for process_id in compound_process.process_ids:
            processes = get_transport_processes_from_ids(adapter_object, [process_id])
            if len(processes) > 1:
                raise ValueError(f"Multiple processes with ID {process_id} found.")
            if processes:
                process = processes[0]
                processes.append(process)
    return processes


def get_contained_required_capability_processes_from_compound_processes(
    adapter_object: ProductionSystemData,
    compound_processes: List[processes_data_module.CompoundProcessData],
) -> List[processes_data_module.PROCESS_DATA_UNION]:
    processes = []
    for compound_process in compound_processes:
        for process_id in compound_process.process_ids:
            processes = get_required_capability_processes_from_ids(
                adapter_object, [process_id]
            )
            if len(processes) > 1:
                raise ValueError(f"Multiple processes with ID {process_id} found.")
            process = processes[0]
            processes.append(process)
    return processes


def get_required_process_ids(
    configuration: ProductionSystemData,
) -> List[str]:
    """
    Returns all required process IDs that are used in the production system.

    Args:
        configuration (ProductionSystemData): Production system configuration

    Returns:
        List[str]: List of required process IDs
    """
    required: List[str] = []
    required_dict_keys: List[str] = []
    required_dict_values: List[str] = []

    for product in configuration.product_data:
        processes = product.processes
        if processes is None:
            continue
        if isinstance(processes, dict):
            required_dict_keys.extend(processes.keys())
            dict_values = util.flatten(list(processes.values()))
            if dict_values:
                required_dict_values.extend(dict_values)
        else:
            flattened = util.flatten(processes)
            if flattened:
                required.extend(flattened)

    required_transport_processes = [
        product.transport_process
        for product in configuration.product_data
        if product.transport_process
    ]

    primitive_transport_processes = [
        primitive.transport_process
        for primitive in configuration.primitive_data
        if getattr(primitive, "transport_process", None)
    ]

    dependency_entries = getattr(configuration, "dependency_data", None)
    if dependency_entries is None:
        dependency_entries = getattr(configuration, "depdendency_data", []) or []
    dependency_processes = [
        dependency.required_process
        for dependency in dependency_entries
        if hasattr(dependency, "required_process") and dependency.required_process
    ]

    return list(
        set(
            required
            + required_dict_keys
            + required_dict_values
            + required_transport_processes
            + primitive_transport_processes
            + dependency_processes
        )
    )


def get_available_process_ids(
    configuration: ProductionSystemData,
) -> List[str]:
    """
    Returns all available process IDs that are used in the production system.

    Args:
        configuration (ProductionSystemData): Production system configuration

    Returns:
        List[str]: List of available process IDs
    """
    return list(
        set(
            util.flatten(
                [resource.process_ids for resource in configuration.resource_data]
            )
        )
    )


def get_required_production_processes(
    configuration: ProductionSystemData,
) -> List[processes_data_module.PROCESS_DATA_UNION]:
    """
    Returns all required production processes in the production system.

    Args:
        configuration (ProductionSystemData): Production system configuration

    Returns:
        List: List of required production processes
    """
    required = get_required_process_ids(configuration)
    required_production_processes = get_production_processes_from_ids(
        configuration, required
    )
    all_process_ids = set([process.ID for process in configuration.process_data])
    compound_processes = get_compound_processes_from_ids(configuration, all_process_ids)
    for compound_process in compound_processes:
        if not all(
            process_id in all_process_ids for process_id in compound_process.process_ids
        ):
            raise ValueError(
                f"Compound process {compound_process.ID} contains processes that are not available in the data."
            )
    required_compound_processes = get_compound_processes_from_ids(
        configuration, required
    )
    required_production_processes += (
        get_contained_production_processes_from_compound_processes(
            configuration, required_compound_processes
        )
    )
    return required_production_processes


def get_required_transport_processes(
    configuration: ProductionSystemData,
) -> List[processes_data_module.PROCESS_DATA_UNION]:
    """
    Returns all required transport processes in the production system.

    Args:
        configuration (ProductionSystemData): Production system configuration

    Returns:
        List: List of required transport processes
    """
    required = get_required_process_ids(configuration)
    required_transport_processes = get_transport_processes_from_ids(
        configuration, required
    )
    all_process_ids = set([process.ID for process in configuration.process_data])
    compound_processes = get_compound_processes_from_ids(configuration, all_process_ids)
    required_compound_processes = get_compound_processes_from_ids(
        configuration, required
    )
    required_transport_processes += (
        get_contained_transport_processes_from_compound_processes(
            configuration, required_compound_processes
        )
    )
    return required_transport_processes

def get_conveyor_processes(
    configuration: ProductionSystemData,
) -> List[processes_data_module.PROCESS_DATA_UNION]:
    """
    Returns all required transport processes in the production system.

    Args:
        configuration (ProductionSystemData): Production system configuration

    Returns:
        List: List of required transport processes
    """
    required_transport_processes=[]
    for process in configuration.process_data:
        if isinstance(process, LinkTransportProcessData):
            if not process.can_move:
                required_transport_processes.append(process)

    return required_transport_processes 

def get_required_capability_processes(
    configuration: ProductionSystemData,
) -> List[processes_data_module.PROCESS_DATA_UNION]:
    """
    Returns all required capability processes in the production system.

    Args:
        configuration (ProductionSystemData): Production system configuration

    Returns:
        List: List of required capability processes
    """
    required = get_required_process_ids(configuration)
    required_capability_processes = get_capability_processes_from_ids(
        configuration, required
    )
    required_capability_processes += get_required_capability_processes_from_ids(
        configuration, required
    )
    all_process_ids = set([process.ID for process in configuration.process_data])
    compound_processes = get_compound_processes_from_ids(configuration, all_process_ids)
    required_compound_processes = get_compound_processes_from_ids(
        configuration, required
    )
    required_capability_processes += (
        get_contained_capability_processes_from_compound_processes(
            configuration, required_compound_processes
        )
    )
    required_capability_processes += (
        get_contained_required_capability_processes_from_compound_processes(
            configuration, required_compound_processes
        )
    )
    return required_capability_processes


def get_available_production_processes(
    configuration: ProductionSystemData,
) -> List[processes_data_module.PROCESS_DATA_UNION]:
    """
    Returns all available production processes in the production system.

    Args:
        configuration (ProductionSystemData): Production system configuration

    Returns:
        List: List of available production processes
    """
    available = get_available_process_ids(configuration)
    available_production_processes = get_production_processes_from_ids(
        configuration, available
    )
    all_process_ids = set([process.ID for process in configuration.process_data])
    compound_processes = get_compound_processes_from_ids(configuration, all_process_ids)
    available_compound_processes = get_compound_processes_from_ids(
        configuration, available
    )
    available_production_processes += (
        get_contained_production_processes_from_compound_processes(
            configuration, available_compound_processes
        )
    )
    return available_production_processes


def get_available_transport_processes(
    configuration: ProductionSystemData,
) -> List[processes_data_module.PROCESS_DATA_UNION]:
    """
    Returns all available transport processes in the production system.

    Args:
        configuration (ProductionSystemData): Production system configuration

    Returns:
        List: List of available transport processes
    """
    available = get_available_process_ids(configuration)
    available_transport_processes = get_transport_processes_from_ids(
        configuration, available
    )
    all_process_ids = set([process.ID for process in configuration.process_data])
    compound_processes = get_compound_processes_from_ids(configuration, all_process_ids)
    available_compound_processes = get_compound_processes_from_ids(
        configuration, available
    )
    available_transport_processes += (
        get_contained_transport_processes_from_compound_processes(
            configuration, available_compound_processes
        )
    )
    return available_transport_processes


def get_available_capability_processes(
    configuration: ProductionSystemData,
) -> List[processes_data_module.PROCESS_DATA_UNION]:
    """
    Returns all available capability processes in the production system.

    Args:
        configuration (ProductionSystemData): Production system configuration

    Returns:
        List: List of available capability processes
    """
    available = get_available_process_ids(configuration)
    available_capability_processes = get_capability_processes_from_ids(
        configuration, available
    )
    all_process_ids = set([process.ID for process in configuration.process_data])
    compound_processes = get_compound_processes_from_ids(configuration, all_process_ids)
    available_compound_processes = get_compound_processes_from_ids(
        configuration, available
    )
    available_capability_processes += (
        get_contained_capability_processes_from_compound_processes(
            configuration, available_compound_processes
        )
    )
    return available_capability_processes


def get_missing_production_processes(
    available: List[
        Union[
            processes_data_module.ProductionProcessData,
            processes_data_module.ReworkProcessData,
        ]
    ],
    required: List[
        Union[
            processes_data_module.ProductionProcessData,
            processes_data_module.ReworkProcessData,
        ]
    ],
) -> List[Union[processes_data_module.ProductionProcessData, processes_data_module.ReworkProcessData]]:
    """
    Returns list of missing production processes.

    Args:
        available (List[processes_data_module.ProductionProcessData]): production processes that are available in the production system resources
        required (List[processes_data_module.ProductionProcessData]): production processes that are required from the products
    
    Returns:
        List: List of missing production processes
    """
    available_ids = set([process.ID for process in available])
    required_ids = set([process.ID for process in required])
    missing = required_ids - available_ids
    missing_processes = [p for p in required if p.ID in missing]
    return missing_processes


def assert_production_processes_available(
    available: List[
        Union[
            processes_data_module.ProductionProcessData,
            processes_data_module.ReworkProcessData,
        ]
    ],
    required: List[
        Union[
            processes_data_module.ProductionProcessData,
            processes_data_module.ReworkProcessData,
        ]
    ],
):
    """
    Checks if all required production processes are available.

    Args:
        available (List[processes_data_module.ProductionProcessData]): production processes that are available in the production system resources
        required (List[processes_data_module.ProductionProcessData]): production processes that are required from the products
    Raises:
        ValueError: If required production processes are not available
    """
    available = set([process.ID for process in available])
    required = set([process.ID for process in required])
    if required - available != set():
        raise ValueError(
            f"Required production processes {required - available} are not available."
        )


def get_missing_transport_processes(
    available: List[processes_data_module.TransportProcessData],
    required: List[processes_data_module.TransportProcessData],
) -> List[processes_data_module.TransportProcessData]:
    """
    Returns list of missing transport processes.

    Args:
        available (List[processes_data_module.TransportProcessData]): transport processes that are available in the production system resources
        required (List[processes_data_module.TransportProcessData]): transport processes that are required from the products

    Returns:
        List: List of missing transport processes
    """
    available_ids = set([process.ID for process in available])
    required_ids = set([process.ID for process in required])
    missing = required_ids - available_ids
    missing_processes = [p for p in required if p.ID in missing]
    return missing_processes


def assert_transport_processes_available(
    available: List[processes_data_module.TransportProcessData],
    required: List[processes_data_module.TransportProcessData],
):
    """
    Checks if all required transport processes are available.

    Args:
        available (List[processes_data_module.TransportProcessData]): transport processes that are available in the production system resources
        required (List[processes_data_module.TransportProcessData]): transport processes that are required from the products

    Raises:
        ValueError: If required transport processes are not available
    """
    available = set([process.ID for process in available])
    required = set([process.ID for process in required])
    if required - available != set():
        raise ValueError(
            f"Required transport processes {required - available} are not available."
        )


def get_missing_capability_processes(
    available: List[processes_data_module.CapabilityProcessData],
    required: List[processes_data_module.CapabilityProcessData],
) -> List[processes_data_module.CapabilityProcessData]:
    """
    Returns list of missing capability processes.

    Args:
        available (List[processes_data_module.CapabilityProcessData]): capability processes that are available in the production system resources
        required (List[processes_data_module.CapabilityProcessData]): capability processes that are required from the products

    Returns:
        List: List of missing capability processes
    """
    available_ids = set([process.capability for process in available])
    required_ids = set([process.capability for process in required])
    missing_capabilities = required_ids - available_ids
    missing_processes = [
        p
        for p in required
        if p.capability in missing_capabilities
    ]
    return missing_processes


def assert_capability_processes_available(
    available: List[processes_data_module.CapabilityProcessData],
    required: List[processes_data_module.CapabilityProcessData],
):
    """
    Checks if all required capability processes are available.

    Args:
        available (List[processes_data_module.CapabilityProcessData]): capability processes that are available in the production system resources
        required (List[processes_data_module.CapabilityProcessData]): capability processes that are required from the products

    Raises:
        ValueError: If required capability processes are not available
    """
    available = set([process.capability for process in available])
    required = set([process.capability for process in required])
    if required - available != set():
        raise ValueError(
            f"Required capability processes {required - available} are not available."
        )


def assert_required_processes_in_resources_available(
    configuration: ProductionSystemData,
):
    """
    Asserts that all required processes are available in the resources that are requested by the products in the configuration.

    Args:
        configuration (ProductionSystemAdapter): Production system configuration

    Raises:
        ValueError: If specified processes contain some logical errors.
    """
    process_map = {process.ID: process for process in configuration.process_data}

    available = set(
        util.flatten(
            [resource.process_ids for resource in configuration.resource_data]
        )
    )

    required_ids = set(get_required_process_ids(configuration))

    state_related_process_ids: Set[str] = set()
    for state in configuration.state_data:
        if hasattr(state, "origin_setup") and state.origin_setup:
            state_related_process_ids.add(state.origin_setup)
        if hasattr(state, "target_setup") and state.target_setup:
            state_related_process_ids.add(state.target_setup)
        if hasattr(state, "process_id") and state.process_id:
            state_related_process_ids.add(state.process_id)
    required_ids.update(state_related_process_ids)

    required_list = list(required_ids)
    available_list = list(available)

    required_production_processes = get_production_processes_from_ids(
        configuration, required_list
    )
    required_transport_processes = get_transport_processes_from_ids(
        configuration, required_list
    )
    required_capability_processes = get_capability_processes_from_ids(
        configuration, required_list
    )
    required_capability_processes += get_required_capability_processes_from_ids(
        configuration, required_list
    )
    available_production_processes = get_production_processes_from_ids(
        configuration, available_list
    )
    available_transport_processes = get_transport_processes_from_ids(
        configuration, available_list
    )
    available_capability_processes = get_capability_processes_from_ids(
        configuration, available_list
    )
    available_required_capability_processes = (
        get_required_capability_processes_from_ids(configuration, available_list)
    )
    if available_required_capability_processes:
        raise ValueError(
            f"Required capability processes {available_required_capability_processes} should not be used for resources since no time model is given."
        )

    all_process_ids = set([process.ID for process in configuration.process_data])
    compound_processes = get_compound_processes_from_ids(configuration, all_process_ids)
    for compound_process in compound_processes:
        if not all(
            process_id in all_process_ids for process_id in compound_process.process_ids
        ):
            raise ValueError(
                f"Compound process {compound_process.ID} contains processes that are not available in the data."
            )
    required_compound_processes = get_compound_processes_from_ids(
        configuration, required_list
    )
    available_compound_processes = get_compound_processes_from_ids(
        configuration, available_list
    )

    required_production_processes += (
        get_contained_production_processes_from_compound_processes(
            configuration, required_compound_processes
        )
    )
    required_transport_processes += (
        get_contained_transport_processes_from_compound_processes(
            configuration, required_compound_processes
        )
    )
    required_capability_processes += (
        get_contained_capability_processes_from_compound_processes(
            configuration, required_compound_processes
        )
    )
    required_capability_processes += (
        get_contained_required_capability_processes_from_compound_processes(
            configuration, required_compound_processes
        )
    )
    available_production_processes += (
        get_contained_production_processes_from_compound_processes(
            configuration, available_compound_processes
        )
    )
    available_transport_processes += (
        get_contained_transport_processes_from_compound_processes(
            configuration, available_compound_processes
        )
    )
    available_capability_processes += (
        get_contained_capability_processes_from_compound_processes(
            configuration, available_compound_processes
        )
    )

    required_capabilities: Set[str] = {
        process.capability
        for process in required_capability_processes
        if getattr(process, "capability", None)
    }

    for resource in configuration.resource_data:
        for process_id in resource.process_ids:
            process_data = process_map.get(process_id)
            if process_data is None:
                raise ValueError(
                    f"The process {process_id} assigned to resource {resource.ID} is not defined in process data."
                )
            capability = getattr(process_data, "capability", None)
            if isinstance(
                process_data, processes_data_module.CapabilityProcessData
            ):
                if not capability or capability not in required_capabilities:
                    raise ValueError(
                        f"The capability process {process_id} of resource {resource.ID} provides capability "
                        f"{capability}, which is not required by any product."
                    )
                continue
            if isinstance(
                process_data, processes_data_module.RequiredCapabilityProcessData
            ):
                raise ValueError(
                    f"Resource {resource.ID} contains required capability process {process_id}. "
                    "Required capability processes are only allowed on products."
                )
            if capability:
                if capability not in required_capabilities:
                    raise ValueError(
                        f"The process {process_id} of resource {resource.ID} provides capability "
                        f"{capability}, which is not required by any product."
                    )
                continue
            if process_id not in required_ids:
                continue

    assert_production_processes_available(
        available_production_processes, required_production_processes
    )
    assert_transport_processes_available(
        available_transport_processes, required_transport_processes
    )
    assert_capability_processes_available(
        available_capability_processes, required_capability_processes
    )
