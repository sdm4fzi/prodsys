from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Any, Set, Optional, Tuple, Union
from pydantic import BaseModel, validator

from prodsim.data_structures import (
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


def get_machines(adapter: Adapter) -> List[resource_data.ProductionResourceData]:
    return [
        resource
        for resource in adapter.resource_data
        if isinstance(resource, resource_data.ProductionResourceData)
    ]


def get_transport_resources(
    adapter: Adapter,
) -> List[resource_data.TransportResourceData]:
    return [
        resource
        for resource in adapter.resource_data
        if isinstance(resource, resource_data.TransportResourceData)
    ]


def get_set_of_IDs(list_of_objects: List[Any]) -> Set[str]:
    return set([obj.ID for obj in list_of_objects])


def get_default_queues_for_resource(
    resource: resource_data.ProductionResourceData,
    queue_capacity: Union[float, int] = 0.0,
) -> Tuple[List[queue_data.QueueData], List[queue_data.QueueData]]:
    input_queues = [
        queue_data.QueueData(
            ID=resource.ID + "default_input_queue",
            description="Default input queue of " + resource.ID,
            capacity=queue_capacity,
        )
    ]
    output_queues = [
        queue_data.QueueData(
            ID=resource.ID + "default_output_queue",
            description="Default output queue of " + resource.ID,
            capacity=queue_capacity,
        )
    ]
    return input_queues, output_queues


class Adapter(ABC, BaseModel):
    ID: str = ""
    valid_configuration: bool = True
    reconfiguration_cost: float = 0

    seed: int = 21
    time_model_data: List[time_model_data.TIME_MODEL_DATA] = []
    state_data: List[state_data.STATE_DATA_UNION] = []
    process_data: List[processes_data.PROCESS_DATA_UNION] = []
    queue_data: List[queue_data.QueueData] = []
    resource_data: List[resource_data.RESOURCE_DATA_UNION] = []
    material_data: List[material_data.MaterialData] = []
    sink_data: List[sink_data.SinkData] = []
    source_data: List[source_data.SourceData] = []
    scenario_data: Optional[scenario_data.ScenarioData] = None

    class Config:
        validate_assignment = True
        schema_extra = {
            "example": {
                "seed": 24,
                "time_models": {
                    "0": {
                        "ID": "function_time_model_1",
                        "description": "normal distribution time model with 20 minutes",
                        "type": "FunctionTimeModel",
                        "distribution_function": "normal",
                        "parameters": [14.3, 5.0],
                        "batch_size": 100,
                    },
                    "1": {
                        "ID": "function_time_model_2",
                        "description": "constant distribution time model with 10 minutes",
                        "type": "FunctionTimeModel",
                        "distribution_function": "constant",
                        "parameters": [15.0],
                        "batch_size": 100,
                    },
                    "2": {
                        "ID": "function_time_model_3",
                        "description": "normal distribution time model with 20 minutes",
                        "type": "FunctionTimeModel",
                        "distribution_function": "normal",
                        "parameters": [20.0, 5.0],
                        "batch_size": 100,
                    },
                    "3": {
                        "ID": "function_time_model_4",
                        "description": "exponential distribution time model with 100 minutes",
                        "type": "FunctionTimeModel",
                        "distribution_function": "exponential",
                        "parameters": [52.0],
                        "batch_size": 100,
                    },
                    "4": {
                        "ID": "function_time_model_5",
                        "description": "exponential distribution time model with 150 minutes",
                        "type": "FunctionTimeModel",
                        "distribution_function": "exponential",
                        "parameters": [150.0],
                        "batch_size": 100,
                    },
                    "5": {
                        "ID": "history_time_model_1",
                        "description": "history time model",
                        "type": "HistoryTimeModel",
                        "history": [25.0, 13.0, 15.0, 16.0, 17.0, 20.0, 21.0],
                    },
                    "6": {
                        "ID": "manhattan_time_model_1",
                        "description": "manhattan time model with speed 180 m/min = 3 m/s",
                        "type": "ManhattanDistanceTimeModel",
                        "speed": 30.0,
                        "reaction_time": 0.15,
                    },
                },
                "states": {
                    "0": {
                        "ID": "Breakdownstate_1",
                        "description": "Breakdown state machine 1",
                        "time_model_id": "function_time_model_5",
                        "type": "BreakDownState",
                    },
                    "1": {
                        "ID": "Breakdownstate_2",
                        "description": "Breakdown state machine 2",
                        "time_model_id": "function_time_model_5",
                        "type": "BreakDownState",
                    },
                    "2": {
                        "ID": "Setup_State_1",
                        "description": "Setup state machine 1",
                        "time_model_id": "function_time_model_2",
                        "type": "SetupState",
                        "origin_setup": "P1",
                        "target_setup": "P2",
                    },
                    "3": {
                        "ID": "Setup_State_2",
                        "description": "Setup state machine 2",
                        "time_model_id": "function_time_model_2",
                        "type": "SetupState",
                        "origin_setup": "P2",
                        "target_setup": "P1",
                    },
                    "4": {
                        "ID": "Setup_State_3",
                        "description": "Setup state machine 3",
                        "time_model_id": "function_time_model_2",
                        "type": "SetupState",
                        "origin_setup": "P1",
                        "target_setup": "P3",
                    },
                    "5": {
                        "ID": "Setup_State_4",
                        "description": "Setup state machine 3",
                        "time_model_id": "function_time_model_3",
                        "type": "SetupState",
                        "origin_setup": "P3",
                        "target_setup": "P1",
                    },
                    "6": {
                        "ID": "ProcessBreakdownState_1",
                        "description": "Breakdown state process 1",
                        "time_model_id": "function_time_model_5",
                        "type": "ProcessBreakDownState",
                        "process_id": "P1",
                    },
                },
                "processes": {
                    "0": {
                        "ID": "P1",
                        "description": "Process 1",
                        "time_model_id": "function_time_model_1",
                        "type": "ProductionProcesses",
                    },
                    "1": {
                        "ID": "P2",
                        "description": "Process 2",
                        "time_model_id": "function_time_model_2",
                        "type": "ProductionProcesses",
                    },
                    "2": {
                        "ID": "P3",
                        "description": "Process 3",
                        "time_model_id": "function_time_model_3",
                        "type": "ProductionProcesses",
                    },
                    "3": {
                        "ID": "TP1",
                        "description": "Transport Process 1",
                        "time_model_id": "manhattan_time_model_1",
                        "type": "TransportProcesses",
                    },
                },
                "queues": {
                    "0": {
                        "ID": "IQ1",
                        "description": "Input-queue 1 for R1 and R2",
                        "capacity": 10,
                    },
                    "1": {
                        "ID": "OQ1",
                        "description": "Output-queue 1 for R1",
                        "capacity": 10,
                    },
                    "2": {
                        "ID": "OQ2",
                        "description": "Output-queue 2 for R2",
                        "capacity": 10,
                    },
                    "3": {
                        "ID": "IQ2",
                        "description": "Input-queue 2 for R3",
                        "capacity": 10,
                    },
                    "4": {
                        "ID": "OQ3",
                        "description": "Output-queue 3 for R3",
                        "capacity": 10,
                    },
                    "5": {
                        "ID": "SourceQueue",
                        "description": "Output-Queue for all sources",
                        "capacity": 0,
                    },
                    "6": {
                        "ID": "SinkQueue",
                        "description": "Input-Queue for all sinks",
                        "capacity": 0,
                    },
                },
                "resources": {
                    "0": {
                        "ID": "R1",
                        "description": "Resource 1",
                        "capacity": 2,
                        "location": [10.0, 10.0],
                        "controller": "SimpleController",
                        "control_policy": "FIFO",
                        "processes": ["P1", "P2"],
                        "process_capacity": [2, 1],
                        "states": [
                            "Breakdownstate_1",
                            "Setup_State_1",
                            "Setup_State_2",
                            "ProcessBreakdownState_1",
                        ],
                        "input_queues": ["IQ1"],
                        "output_queues": ["OQ1"],
                    },
                    "1": {
                        "ID": "R2",
                        "description": "Resource 2",
                        "capacity": 1,
                        "location": [20.0, 10.0],
                        "controller": "SimpleController",
                        "control_policy": "FIFO",
                        "processes": ["P2", "P3"],
                        "process_capacity": None,
                        "states": ["Breakdownstate_2"],
                        "input_queues": ["IQ1"],
                        "output_queues": ["OQ2"],
                    },
                    "2": {
                        "ID": "R3",
                        "description": "Resource 3",
                        "capacity": 2,
                        "location": [20.0, 20.0],
                        "controller": "SimpleController",
                        "control_policy": "FIFO",
                        "processes": ["P1", "P3"],
                        "process_capacity": [1, 2],
                        "states": [
                            "Breakdownstate_1",
                            "Breakdownstate_2",
                            "Setup_State_3",
                            "Setup_State_4",
                        ],
                        "input_queues": ["IQ2"],
                        "output_queues": ["OQ3"],
                    },
                    "3": {
                        "ID": "R4",
                        "description": "Resource 3",
                        "capacity": 2,
                        "location": [10.0, 20.0],
                        "controller": "SimpleController",
                        "control_policy": "FIFO",
                        "processes": ["P1", "P3"],
                        "process_capacity": [2, 2],
                        "states": [
                            "Breakdownstate_1",
                            "Setup_State_3",
                            "Setup_State_4",
                        ],
                        "input_queues": ["IQ2"],
                        "output_queues": ["OQ3"],
                    },
                    "4": {
                        "ID": "TR1",
                        "description": "Transport Resource 1",
                        "capacity": 1,
                        "location": [15.0, 15.0],
                        "controller": "TransportController",
                        "control_policy": "FIFO",
                        "processes": ["TP1"],
                        "process_capacity": None,
                        "states": ["Breakdownstate_1"],
                    },
                    "5": {
                        "ID": "TR2",
                        "description": "Transport Resource 2",
                        "capacity": 1,
                        "location": [15.0, 20.0],
                        "controller": "TransportController",
                        "control_policy": "SPT_transport",
                        "processes": ["TP1"],
                        "process_capacity": None,
                        "states": ["Breakdownstate_1"],
                    },
                },
                "materials": {
                    "0": {
                        "ID": "Material_1",
                        "description": "Material 1",
                        "material_type": "Material_1",
                        "processes": ["P1", "P2", "P3"],
                        "transport_process": "TP1",
                    },
                    "1": {
                        "ID": "Material_2",
                        "description": "Material 2",
                        "material_type": "Material_2",
                        "processes": ["P1", "P2", "P3", "P1"],
                        "transport_process": "TP1",
                    },
                    "2": {
                        "ID": "Material_3",
                        "description": "Material 3",
                        "material_type": "Material_3",
                        "processes": "data/example_material_petri_net.pnml",
                        "transport_process": "TP1",
                    },
                },
                "sinks": {
                    "0": {
                        "ID": "SK1",
                        "description": "Sink 1",
                        "location": [50.0, 50.0],
                        "material_type": "Material_1",
                        "input_queues": ["SinkQueue"],
                    },
                    "1": {
                        "ID": "SK2",
                        "description": "Sink 2",
                        "location": [55.0, 50.0],
                        "material_type": "Material_2",
                        "input_queues": ["SinkQueue"],
                    },
                    "2": {
                        "ID": "SK3",
                        "description": "Sink 3",
                        "location": [45.0, 50.0],
                        "material_type": "Material_3",
                        "input_queues": ["SinkQueue"],
                    },
                },
                "sources": {
                    "0": {
                        "ID": "S1",
                        "description": "Source 1",
                        "location": [0.0, 0.0],
                        "material_type": "Material_1",
                        "time_model_id": "function_time_model_4",
                        "router": "SimpleRouter",
                        "routing_heuristic": "shortest_queue",
                        "output_queues": ["SourceQueue"],
                    },
                    "1": {
                        "ID": "S2",
                        "description": "Source 2",
                        "location": [30.0, 30.0],
                        "material_type": "Material_2",
                        "time_model_id": "function_time_model_4",
                        "router": "SimpleRouter",
                        "routing_heuristic": "shortest_queue",
                        "output_queues": ["SourceQueue"],
                    },
                    "2": {
                        "ID": "S3",
                        "description": "Source 3",
                        "location": [40.0, 30.0],
                        "material_type": "Material_3",
                        "time_model_id": "function_time_model_4",
                        "router": "SimpleRouter",
                        "routing_heuristic": "shortest_queue",
                        "output_queues": ["SourceQueue"],
                    },
                },
            }
        }

    @validator("state_data", each_item=True)
    def check_states(cls, state, values):
        time_models = get_set_of_IDs(values["time_model_data"])
        if state.time_model_id not in time_models:
            raise ValueError(
                f"The time model {state.time_model_id} of state {state.ID} is not a valid time model of {time_models}."
            )
        return state

    @validator("process_data", each_item=True)
    def check_processes(cls, process, values):
        time_models = get_set_of_IDs(values["time_model_data"])
        if process.time_model_id not in time_models:
            raise ValueError(
                f"The time model {process.time_model_id} of process {process.ID} is not a valid time model of {time_models}."
            )
        return process

    @validator("resource_data", each_item=True)
    def check_resources(cls, resource, values):
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
    def check_materials(cls, material, values):
        processes = get_set_of_IDs(values["process_data"])
        if not material.transport_process in processes:
            raise ValueError(
                f"The transport process {material.transport_process} of material {material.ID} is not a valid process of {processes}."
            )
        if isinstance(material.processes, list):
            for process in material.processes:
                if process not in processes:
                    raise ValueError(
                        f"The process {process} of material {material.ID} is not a valid process of {processes}."
                    )
        return material

    @validator("sink_data", each_item=True)
    def check_sinks(cls, sink, values):
        materials = get_set_of_IDs(values["material_data"])
        if sink.material_type not in materials:
            raise ValueError(
                f"The material type {sink.material_type} of sink {sink.ID} is not a valid material of {materials}."
            )
        queues = get_set_of_IDs(values["queue_data"])
        for q in sink.input_queues:
            if q not in queues:
                raise ValueError(
                    f"The queue {q} of sink {sink.ID} is not a valid queue of {queues}."
                )
        return sink

    @validator("source_data", each_item=True)
    def check_sources(cls, source, values):
        time_models = get_set_of_IDs(values["time_model_data"])
        if source.time_model_id not in time_models:
            raise ValueError(
                f"The time model {source.time_model_id} of source {source.ID} is not a valid time model of {time_models}."
            )
        materials = get_set_of_IDs(values["material_data"])
        if source.material_type not in materials:
            raise ValueError(
                f"The material type {source.material_type} of source {source.ID} is not a valid material of {materials}."
            )
        queues = get_set_of_IDs(values["queue_data"])
        for q in source.output_queues:
            if q not in queues:
                raise ValueError(
                    f"The queue {q} of source {source.ID} is not a valid queue of {queues}."
                )
        return source

    @abstractmethod
    def read_data(self, file_path: str, scenario_file_path: Optional[str] = None):
        pass

    @abstractmethod
    def write_data(self, file_path: str):
        pass

    def read_scenario(self, scenario_file_path: str):
        self.scenario_data = scenario_data.ScenarioData.parse_file(scenario_file_path)
