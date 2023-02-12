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
    scenario_data
)

def get_machines(adapter: Adapter) -> List[resource_data.ProductionResourceData]:
    return [resource for resource in adapter.resource_data if isinstance(resource, resource_data.ProductionResourceData)]

def get_transport_resources(adapter: Adapter) -> List[resource_data.TransportResourceData]:
    return [resource for resource in adapter.resource_data if isinstance(resource, resource_data.TransportResourceData)]

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
        for process in resource.processes:
            if process not in processes:
                raise ValueError(
                    f"The process {process} of resource {resource.ID} is not a valid process of {processes}."
                )
        states = get_set_of_IDs(values["state_data"])
        for state in resource.states:
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
