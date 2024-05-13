from __future__ import annotations

from typing import List, TYPE_CHECKING

from pydantic import BaseModel



if TYPE_CHECKING:
    from prodsys.simulation import resources, state
    from prodsys.factories import resource_factory


class ProcessObservation(BaseModel):
    process: str
    product: str
    activity: state.StateEnum
    state: state.StateTypeEnum

class QueueObservation(BaseModel):
    product: str
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
                product=production_state.state_info._product_ID,
                activity=production_state.state_info._activity,
                state=production_state.state_info._state_type
            )
            process_observations.append(observation)
    return process_observations

def observe_input_queue(resource: resources.Resource, product_factory: product_factory.ProductFactory) -> List[QueueObservation]:
    queue_observation = []
    for queue in resource.input_queues:
        for product_data in queue.items:
            product = product_factory.get_product(product_data.ID)

            production_process_info = QueueObservation(
                product=product_data.ID,
                activity="waiting",
                process=product.next_prodution_process.process_data.ID,
                next_resource=product.current_locatable.data.ID,
                waiting_since=product.product_info.event_time
            )
            queue_observation.append(production_process_info)

    return queue_observation

def observe_output_queue(resource: resources.Resource, product_factory: product_factory.ProductFactory) -> List[QueueObservation]:
    queue_observation = []
    for queue in resource.output_queues:
        for product_data in queue.items:
            product = product_factory.get_product(product_data.ID)

            production_process_info = QueueObservation(
                product=product_data.ID,
                activity="waiting",
                process=product.next_prodution_process,
                next_resource=product.current_locatable,
                waiting_since=product.product_info.event_time
            )
            queue_observation.append(production_process_info)

    return queue_observation

class ResourceAvailableObservation(BaseModel):
    available: bool

def observe_resource_available(resource: resources.Resource) -> ResourceAvailableObservation:
    return ResourceAvailableObservation(available=resource.active.triggered)
    

class ResourceObserver(BaseModel):
    resource_factory: resource_factory.ResourceFactory
    product_factory: product_factory.ProductFactory
    resource: resources.Resource

    def observe_processes(self) -> List[ProcessObservation]:
        return observe_processes(self.resource)
    
    def observe_input_queue(self) -> List[QueueObservation]:
        return observe_input_queue(self.resource, self.product_factory)
    
    def observe_output_queue(self) -> List[QueueObservation]:
        return observe_output_queue(self.resource, self.product_factory)
    
    def observe_resource_available(self) -> ResourceAvailableObservation:
        return observe_resource_available(self.resource)
    
from prodsys.factories import resource_factory, product_factory
from prodsys.simulation import resources, state
ResourceObserver.update_forward_refs()