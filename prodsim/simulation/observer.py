from __future__ import annotations

from enum import Enum
from abc import ABC, abstractmethod
from typing import List, Union, TYPE_CHECKING, Dict, Type, Callable

import numpy as np
from pydantic import BaseModel



if TYPE_CHECKING:
    from prodsim.simulation import material, resources, control, state
    from prodsim.factories import resource_factory, material_factory


class ProcessObservation(BaseModel):
    process: str
    material: str
    activity: state.StateEnum
    state: state.StateTypeEnum

class QueueObservation(BaseModel):
    material: str
    activity: str
    process: str
    next_resource: str
    waiting_since: float

def observe_processes(resource: resources.Resource) -> List[ProcessObservation]:
    process_observations = []
    for production_state in resource.production_states:
        if production_state.process:
            observation = ProcessObservation(
                process=production_state.state_info.ID,
                material=production_state.state_info._material_ID,
                activity=production_state.state_info._activity,
                state=production_state.state_info._state_type
            )
            process_observations.append(observation)
    return process_observations

def observe_input_queue(resource: resources.Resource, material_factory: material_factory.MaterialFactory) -> List[QueueObservation]:
    queue_observation = []
    for queue in resource.input_queues:
        for material_data in queue.items:
            material = material_factory.get_material(material_data.ID)

            production_process_info = QueueObservation(
                material=material_data.ID,
                activity="waiting",
                process=material.next_process.process_data.ID,
                next_resource=material.next_resource.data.ID,
                waiting_since=material.material_info.event_time
            )
            queue_observation.append(production_process_info)

    return queue_observation

def observe_output_queue(resource: resources.Resource, material_factory: material_factory.MaterialFactory) -> List[QueueObservation]:
    queue_observation = []
    for queue in resource.output_queues:
        for material_data in queue.items:
            material = material_factory.get_material(material_data.ID)

            production_process_info = QueueObservation(
                material=material_data.ID,
                activity="waiting",
                process=material.next_process,
                next_resource=material.next_resource,
                waiting_since=material.material_info.event_time
            )
            queue_observation.append(production_process_info)

    return queue_observation

class ResourceAvailableObservation(BaseModel):
    available: bool

def observe_resource_available(resource: resources.Resource) -> ResourceAvailableObservation:
    return ResourceAvailableObservation(available=resource.active.triggered)
    

class ResourceObserver(BaseModel):
    resource_factory: resource_factory.ResourceFactory
    material_factory: material_factory.MaterialFactory
    resource: resources.Resource

    def observe_processes(self) -> List[ProcessObservation]:
        return observe_processes(self.resource)
    
    def observe_input_queue(self) -> List[QueueObservation]:
        return observe_input_queue(self.resource, self.material_factory)
    
    def observe_output_queue(self) -> List[QueueObservation]:
        return observe_output_queue(self.resource, self.material_factory)
    
    def observe_resource_available(self) -> ResourceAvailableObservation:
        return observe_resource_available(self.resource)
    
from prodsim.factories import resource_factory, material_factory
from prodsim.simulation import material, resources, control, state
ResourceObserver.update_forward_refs()