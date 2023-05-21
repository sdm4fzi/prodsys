from __future__ import annotations

from abc import ABC, abstractmethod
import warnings
from typing import List, Any, Set, Optional, Tuple, Union
from pydantic import BaseModel, validator, ValidationError
from prodsys import adapters

from prodsys.data_structures import (
    queue_data,
    resource_data,
    time_model_data,
    state_data,
    processes_data,
    material_data,
    sink_data,
    source_data,
    scenario_data,
)
from prodsys.util import util


def get_machines(adapter: ProductionSystemAdapter) -> List[resource_data.ProductionResourceData]:
    """
    Returns a list of all machines in the adapter.

    Args:
        adapter (ProductionSystemAdapter): ProductionSystemAdapter object

    Returns:
        List[resource_data.ProductionResourceData]: List of all machines in the adapter
    """
    return [
        resource
        for resource in adapter.resource_data
        if isinstance(resource, resource_data.ProductionResourceData)
    ]


def get_transport_resources(
    adapter: ProductionSystemAdapter,
) -> List[resource_data.TransportResourceData]:
    """
    Returns a list of all transport resources in the adapter.

    Args:
        adapter (ProductionSystemAdapter): ProductionSystemAdapter object

    Returns:
        List[resource_data.TransportResourceData]: List of all transport resources in the adapter
    """
    return [
        resource
        for resource in adapter.resource_data
        if isinstance(resource, resource_data.TransportResourceData)
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


def get_default_queues_for_resource(
    resource: resource_data.ProductionResourceData,
    queue_capacity: Union[float, int] = 0.0,
) -> Tuple[List[queue_data.QueueData], List[queue_data.QueueData]]:
    """
    Returns a tuple of two lists of default queues for the given resource. The first list contains the default input queues and the second list contains the default output queues.

    Args:
        resource (resource_data.ProductionResourceData): Resource for which the default queues should be returned
        queue_capacity (Union[float, int], optional): Capacity of the default queues. Defaults to 0.0 (infinite queue).

    Returns:
        Tuple[List[queue_data.QueueData], List[queue_data.QueueData]]: Tuple of two lists of default queues for the given resource
    """
    input_queues = [
        queue_data.QueueData(
            ID=resource.ID + "_default_input_queue",
            description="Default input queue of " + resource.ID,
            capacity=queue_capacity,
        )
    ]
    output_queues = [
        queue_data.QueueData(
            ID=resource.ID + "_default_output_queue",
            description="Default output queue of " + resource.ID,
            capacity=queue_capacity,
        )
    ]
    return input_queues, output_queues


def remove_queues_from_resource(
    machine: resource_data.ProductionResourceData, adapter: adapters.ProductionSystemAdapter
) -> adapters.ProductionSystemAdapter:
    if machine.input_queues or machine.output_queues:
        for queue_ID in machine.input_queues + machine.output_queues:
            for queue in adapter.queue_data:
                if queue.ID == queue_ID:
                    adapter.queue_data.remove(queue)
                    break
        for machine in adapters.get_machines(adapter):
            machine.input_queues = []
            machine.output_queues = []
        return adapter


def remove_unused_queues_from_adapter(adapter: adapters.ProductionSystemAdapter) -> adapters.ProductionSystemAdapter:
    for queue in adapter.queue_data:
        if not any(
            [
                queue.ID in machine.input_queues + machine.output_queues
                for machine in adapters.get_machines(adapter)
                if machine.input_queues or machine.output_queues
            ]
            + [queue.ID in source.output_queues for source in adapter.source_data]
            + [queue.ID in sink.input_queues for sink in adapter.sink_data]
        ):
            adapter.queue_data.remove(queue)
    return adapter


def add_default_queues_to_resources(
    adapter: adapters.ProductionSystemAdapter, queue_capacity=0.0
) -> adapters.ProductionSystemAdapter:
    """
    Convenience function to add default queues to all machines in the adapter.

    Args:
        adapter (adapters.ProductionSystemAdapter): ProductionSystemAdapter object
        queue_capacity (float, optional): Capacity of the default queues. Defaults to 0.0 (infinite queue).

    Returns:
        adapters.ProductionSystemAdapter: ProductionSystemAdapter object with default queues added to all machines
    """
    for machine in adapters.get_machines(adapter):
        remove_queues_from_resource(machine, adapter)
        remove_unused_queues_from_adapter(adapter)
        input_queues, output_queues = adapters.get_default_queues_for_resource(
            machine, queue_capacity
        )
        machine.input_queues = list(adapters.get_set_of_IDs(input_queues))
        machine.output_queues = list(adapters.get_set_of_IDs(output_queues))
        adapter.queue_data += input_queues + output_queues
    return adapter


def get_default_queue_for_source(
    source: source_data.SourceData, queue_capacity=0.0
) -> queue_data.QueueData:
    """
    Returns a default queue for the given source.

    Args:
        source (source_data.SourceData): Source for which the default queue should be returned
        queue_capacity (float, optional): Capacity of the default queue. Defaults to 0.0 (infinite queue).

    Returns:
        queue_data.QueueData: Default queue for the given source
    """
    return queue_data.QueueData(
        ID=source.ID + "_default_output_queue",
        description="Default output queue of " + source.ID,
        capacity=queue_capacity,
    )


def add_default_queues_to_sources(
    adapter: adapters.ProductionSystemAdapter, queue_capacity=0.0
) -> adapters.ProductionSystemAdapter:
    """
    Convenience function to add default queues to all sources in the adapter.

    Args:
        adapter (adapters.ProductionSystemAdapter): ProductionSystemAdapter object
        queue_capacity (float, optional): Capacity of the default queues. Defaults to 0.0 (infinite queue).

    Returns:
        adapters.ProductionSystemAdapter: ProductionSystemAdapter object with default queues added to all sources
    """
    for source in adapter.source_data:
        if not source.output_queues:
            output_queues = [get_default_queue_for_source(source, queue_capacity)]
            source.output_queues = list(adapters.get_set_of_IDs(output_queues))
            adapter.queue_data += output_queues
    return adapter


def get_default_queue_for_sink(
    sink: sink_data.SinkData, queue_capacity=0.0
) -> queue_data.QueueData:
    """
    Returns a default queue for the given sink.

    Args:
        sink (sink_data.SinkData): Sink for which the default queue should be returned
        queue_capacity (float, optional): Capacity of the default queue. Defaults to 0.0 (infinite queue).

    Returns:
        queue_data.QueueData: Default queue for the given sink
    """
    return queue_data.QueueData(
        ID=sink.ID + "_default_input_queue",
        description="Default input queue of " + sink.ID,
        capacity=queue_capacity,
    )


def add_default_queues_to_sinks(
    adapter: adapters.ProductionSystemAdapter, queue_capacity=0.0
) -> adapters.ProductionSystemAdapter:
    """
    Convenience function to add default queues to all sinks in the adapter.

    Args:
        adapter (adapters.ProductionSystemAdapter): ProductionSystemAdapter object
        queue_capacity (float, optional): Capacity of the default queues. Defaults to 0.0 (infinite queue).

    Returns:
        adapters.ProductionSystemAdapter: ProductionSystemAdapter object with default queues added to all sinks
    """
    for sink in adapter.sink_data:
        if not sink.input_queues:
            input_queues = [get_default_queue_for_sink(sink, queue_capacity)]
            sink.input_queues = list(adapters.get_set_of_IDs(input_queues))
            adapter.queue_data += input_queues
    return adapter


def add_default_queues_to_adapter(
    adapter: adapters.ProductionSystemAdapter, queue_capacity=0.0
) -> adapters.ProductionSystemAdapter:
    """
    Convenience function to add default queues to all machines, sources and sinks in the adapter.

    Args:
        adapter (adapters.ProductionSystemAdapter): ProductionSystemAdapter object
        queue_capacity (float, optional): Capacity of the default queues. Defaults to 0.0 (infinite queue).

    Returns:
        adapters.ProductionSystemAdapter: ProductionSystemAdapter object with default queues added to all machines, sources and sinks
    """
    adapter = add_default_queues_to_resources(adapter, queue_capacity)
    adapter = add_default_queues_to_sources(adapter, queue_capacity)
    adapter = add_default_queues_to_sinks(adapter, queue_capacity)
    return adapter


class ProductionSystemAdapter(ABC, BaseModel):
    """
    A ProductionSystemAdapter serves as a n abstract base class of a data container to represent a production system. It is based on the `prodsys.data_structures` module, but is also compatible with the `prodsys.express` API.
    It is used as the basis for all simulation and optimization algorithms in prodsys and comes with complete data validation. 
    Thereby, it is assured that the expected data is used for simulation and optimization. If the data is not valid, an error is raised with information about the reasons for invalidity.
    The adapter targets easy integration of algorithms with each other in different environments. 
    Therefore, the adapter can even be used for integration of new algorithms by serving as a defined data interface. 

    Args:
        ID (str, optional): ID of the production system. Defaults to "".
        seed (int, optional): Seed for the random number generator used in simulation. Defaults to 0.
        time_model_data (List[time_model_data.TIME_MODEL_DATA], optional): List of time models used by the entities in the production system. Defaults to [].
        state_data (List[state_data.STATE_DATA_UNION], optional): List of states used by the resources in the production system. Defaults to [].
        process_data (List[processes_data.PROCESS_DATA_UNION], optional): List of processes required by materials and provided by resources in the production system. Defaults to [].
        queue_data (List[queue_data.QueueData], optional): List of queues used by the resources, sources and sinks in the production system. Defaults to [].
        resource_data (List[resource_data.RESOURCE_DATA_UNION], optional): List of resources in the production system. Defaults to [].
        material_data (List[material_data.MaterialData], optional): List of materials in the production system. Defaults to [].
        sink_data (List[sink_data.SinkData], optional): List of sinks in the production system. Defaults to [].
        source_data (List[source_data.SourceData], optional): List of sources in the production system. Defaults to [].
        scenario_data (Optional[scenario_data.ScenarioData], optional): Scenario data of the production system used for optimization. Defaults to None.
        valid_configuration (bool, optional): Indicates if the configuration is valid. Defaults to True.
        reconfiguration_cost (float, optional): Cost of reconfiguration in a optimization scenario. Defaults to 0.
    """
    ID: str = ""
    seed: int = 0
    time_model_data: List[time_model_data.TIME_MODEL_DATA] = []
    state_data: List[state_data.STATE_DATA_UNION] = []
    process_data: List[processes_data.PROCESS_DATA_UNION] = []
    queue_data: List[queue_data.QueueData] = []
    resource_data: List[resource_data.RESOURCE_DATA_UNION] = []
    material_data: List[material_data.MaterialData] = []
    sink_data: List[sink_data.SinkData] = []
    source_data: List[source_data.SourceData] = []
    scenario_data: Optional[scenario_data.ScenarioData] = None

    
    valid_configuration: bool = True
    reconfiguration_cost: float = 0

    class Config:
        validate = True
        validate_assignment = True
        schema_extra = {
            "example": {
                "ID": "",
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
                        "type": "TransportProcesses",
                    },
                ],
                "queue_data": [
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
                        "location": [10.0, 10.0],
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
                        "location": [20.0, 10.0],
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
                        "location": [20.0, 20.0],
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
                        "location": [10.0, 20.0],
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
                "material_data": [
                    {
                        "ID": "Material_1",
                        "description": "Material 1",
                        "material_type": "Material_1",
                        "processes": ["P1", "P2", "P3"],
                        "transport_process": "TP1",
                    },
                    {
                        "ID": "Material_2",
                        "description": "Material 2",
                        "material_type": "Material_2",
                        "processes": ["P1", "P2", "P3", "P1"],
                        "transport_process": "TP1",
                    },
                    {
                        "ID": "Material_3",
                        "description": "Material 3",
                        "material_type": "Material_3",
                        "processes": {"P1": ["P2", "P3"], "P2": [], "P3": []},
                        "transport_process": "TP1",
                    },
                ],
                "sink_data": [
                    {
                        "ID": "SK1",
                        "description": "Sink 1",
                        "location": [50.0, 50.0],
                        "material_type": "Material_1",
                        "input_queues": ["SinkQueue"],
                    },
                    {
                        "ID": "SK2",
                        "description": "Sink 2",
                        "location": [55.0, 50.0],
                        "material_type": "Material_2",
                        "input_queues": ["SinkQueue"],
                    },
                    {
                        "ID": "SK3",
                        "description": "Sink 3",
                        "location": [45.0, 50.0],
                        "material_type": "Material_3",
                        "input_queues": ["SinkQueue"],
                    },
                ],
                "source_data": [
                    {
                        "ID": "S1",
                        "description": "Source 1",
                        "location": [0.0, 0.0],
                        "material_type": "Material_1",
                        "time_model_id": "function_time_model_4",
                        "router": "SimpleRouter",
                        "routing_heuristic": "shortest_queue",
                        "output_queues": ["SourceQueue"],
                    },
                    {
                        "ID": "S2",
                        "description": "Source 2",
                        "location": [30.0, 30.0],
                        "material_type": "Material_2",
                        "time_model_id": "function_time_model_4",
                        "router": "SimpleRouter",
                        "routing_heuristic": "shortest_queue",
                        "output_queues": ["SourceQueue"],
                    },
                    {
                        "ID": "S3",
                        "description": "Source 3",
                        "location": [40.0, 30.0],
                        "material_type": "Material_3",
                        "time_model_id": "function_time_model_4",
                        "router": "SimpleRouter",
                        "routing_heuristic": "shortest_queue",
                        "output_queues": ["SourceQueue"],
                    },
                ],
                "scenario_data": None,
            }
        }

    @validator("state_data", each_item=True)
    def check_states(cls, state: state_data.STATE_DATA_UNION, values):
        time_models = get_set_of_IDs(values["time_model_data"])
        if state.time_model_id not in time_models:
            raise ValueError(
                f"The time model {state.time_model_id} of state {state.ID} is not a valid time model of {time_models}."
            )
        return state

    @validator("process_data", each_item=True)
    def check_processes(cls, process: processes_data.PROCESS_DATA_UNION, values):
        time_models = get_set_of_IDs(values["time_model_data"])
        if process.time_model_id not in time_models:
            raise ValueError(
                f"The time model {process.time_model_id} of process {process.ID} is not a valid time model of {time_models}."
            )
        return process

    @validator("resource_data", each_item=True)
    def check_resources(cls, resource: resource_data.RESOURCE_DATA_UNION, values):
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
        if isinstance(resource, resource_data.ProductionResourceData):
            queues = get_set_of_IDs(values["queue_data"])
            if resource.input_queues and resource.output_queues:
                for queue in resource.input_queues + resource.output_queues:
                    if queue not in queues:
                        raise ValueError(
                            f"The queue {queue} of resource {resource.ID} is not a valid queue of {queues}."
                        )
            else:
                input_queues, output_queues = get_default_queues_for_resource(resource)
                resource.input_queues = list(get_set_of_IDs(input_queues))
                resource.output_queues = list(get_set_of_IDs(output_queues))
                values["queue_data"] += input_queues + output_queues

        return resource

    @validator("material_data", each_item=True)
    def check_materials(cls, material: material_data.MaterialData, values):
        all_processes = get_set_of_IDs(values["process_data"])
        if material.transport_process not in all_processes:
            raise ValidationError(
                f"The transport process {material.transport_process} of material {material.ID} is not a valid process of {all_processes}."
            )
        required_processes = set()
        if isinstance(material.processes, list) and isinstance(
            material.processes[0], str
        ):
            required_processes = set(material.processes)
        elif isinstance(material.processes, list) and isinstance(
            material.processes[0], list
        ):
            required_processes = set(util.flatten(material.processes))
        elif isinstance(material.processes, dict):
            required_processes = set(material.processes.keys())
        if required_processes - all_processes != set():
            raise ValueError(
                f"The processes {required_processes - all_processes} of material {material.ID} are not a valid processes of {all_processes}."
            )

        return material

    @validator("sink_data", each_item=True)
    def check_sinks(cls, sink: sink_data.SinkData, values):
        try:
            materials = get_set_of_IDs(values["material_data"])
        except KeyError:
            raise ValueError("Material data is missing or faulty.")
        if sink.material_type not in materials:
            raise ValueError(
                f"The material type {sink.material_type} of sink {sink.ID} is not a valid material of {materials}."
            )
        if not sink.input_queues:
            input_queue = get_default_queue_for_sink(sink)
            sink.input_queues = list(get_set_of_IDs([input_queue]))
            values["queue_data"] += [input_queue]
            return sink
        queues = get_set_of_IDs(values["queue_data"])
        for q in sink.input_queues:
            if q not in queues:
                raise ValueError(
                    f"The queue {q} of sink {sink.ID} is not a valid queue of {queues}."
                )
        return sink

    @validator("source_data", each_item=True)
    def check_sources(cls, source: source_data.SourceData, values):
        time_models = get_set_of_IDs(values["time_model_data"])
        if source.time_model_id not in time_models:
            raise ValueError(
                f"The time model {source.time_model_id} of source {source.ID} is not a valid time model of {time_models}."
            )
        try:
            materials = get_set_of_IDs(values["material_data"])
        except KeyError:
            raise ValueError("Material data is missing or faulty.")
        if source.material_type not in materials:
            raise ValueError(
                f"The material type {source.material_type} of source {source.ID} is not a valid material of {materials}."
            )
        if not source.output_queues:
            output_queue = get_default_queue_for_source(source)
            source.output_queues = list(get_set_of_IDs([output_queue]))
            values["queue_data"] += [output_queue]
            return source
        queues = get_set_of_IDs(values["queue_data"])
        for q in source.output_queues:
            if q not in queues:
                raise ValueError(
                    f"The queue {q} of source {source.ID} is not a valid queue of {queues}."
                )
        return source

    @abstractmethod
    def read_data(self, file_path: str, scenario_file_path: Optional[str] = None):
        """
        Reads the data from the given file path and scenario file path.

        Args:
            file_path (str): File path for the production system configuration
            scenario_file_path (Optional[str], optional): File path for the scenario data. Defaults to None.
        """
        pass

    @abstractmethod
    def write_data(self, file_path: str):
        """
        Writes the data to the given file path.

        Args:
            file_path (str): File path for the production system configuration
        """
        pass

    def read_scenario(self, scenario_file_path: str):
        self.scenario_data = scenario_data.ScenarioData.parse_file(scenario_file_path)

    def validate_proceses_available(self):
        required_processes = set(
            util.flatten([material.processes for material in self.material_data])
        )
        available_processes = set()
        for resource in self.resource_data:
            for process in resource.process_ids:
                available_processes.add(process)
        if required_processes > available_processes:
            raise ValueError(
                f"The processes {required_processes - available_processes} are not available."
            )

    def physical_validation(self):
        """
        Checks if the configuration is physically valid, i.e. if all resources are positioned at different locations and if all required processes are available.

        Raises:
            ValueError: If multiple objects are positioned at the same location.
            ValueError: If not all required process are available.
        """
        if not check_redudant_locations(self):
            raise ValueError(f"Multiple objects are positioned at the same location.")
        if not check_required_processes_available(self):
            raise ValueError(f"Not all required process are available.")


def remove_duplicate_locations(input_list: List[List[float]]) -> List[List[float]]:
    return [list(x) for x in set(tuple(x) for x in input_list)]


def check_redudant_locations(adapter: adapters.ProductionSystemAdapter) -> bool:
    machine_locations = [machine.location for machine in adapters.get_machines(adapter)]
    source_locations = remove_duplicate_locations(
        [source.location for source in adapter.source_data]
    )
    sink_locations = remove_duplicate_locations(
        [sink.location for sink in adapter.sink_data]
    )
    positions = machine_locations + source_locations + sink_locations
    if any(positions.count(location) > 1 for location in positions):
        return False
    return True


def get_possible_production_processes_IDs(
    adapter_object: adapters.ProductionSystemAdapter,
) -> Union[List[str], List[Tuple[str, ...]]]:
    possible_processes = adapter_object.process_data
    if not any(
        process.type == processes_data.ProcessTypeEnum.CapabilityProcesses
        for process in possible_processes
    ):
        return [
            process.ID
            for process in possible_processes
            if isinstance(process, processes_data.ProductionProcessData)
        ]
    capability_processes = [
        process
        for process in possible_processes
        if isinstance(process, processes_data.CapabilityProcessData)
        and process.time_model_id is not None
    ]
    process_dict = {}
    for process in capability_processes:
        if not process.capability in process_dict.keys():
            process_dict[process.capability] = []
        process_dict[process.capability].append(process.ID)
    return [tuple(value) for value in process_dict.values()]


def check_required_processes_available(configuration: adapters.ProductionSystemAdapter) -> bool:
    available = set(
        util.flatten(
            [resource.process_ids for resource in adapters.get_machines(configuration)]
        )
    )
    required = set(
        util.flatten([material.processes for material in configuration.material_data])
    )
    if required - available != set():
        return False
    return True
