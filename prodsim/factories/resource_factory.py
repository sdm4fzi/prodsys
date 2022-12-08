from __future__ import annotations

import copy
from typing import Dict, List, Optional, Union, Tuple, TYPE_CHECKING

from pydantic import BaseModel, parse_obj_as

from .. import env
from ..util_temp import get_class_from_str


from ..data_structures.resource_data import RESOURCE_DATA_UNION, ProductionResourceData
from ..data_structures import state_data
from ..factories import process_factory, state_factory, queue_factory

from .. import resources, control, process

if TYPE_CHECKING:
    from .. import adapter
    from .. import process, state, store





CONTROLLER_DICT: Dict = {
    'SimpleController': control.SimpleController,
    'TransportController': control.TransportController,
}

CONTROL_POLICY_DICT: Dict = {
    'FIFO': control.FIFO_control_policy,
    'LIFO': control.LIFO_control_policy,
    'SPT': control.SPT_control_policy,
    'SPT_transport': control.SPT_transport_control_policy,
}

def register_states(resource: resources.Resourcex, states: List[state.State], _env: env.Environment):
    for actual_state in states:
        copy_state = copy.deepcopy(actual_state)
        copy_state.env = _env
        resource.add_state(copy_state)


def register_production_states(resource: resources.Resourcex, states: List[state.State], _env: env.Environment):
    for actual_state in states:
        copy_state = copy.deepcopy(actual_state)
        copy_state.env = _env
        resource.add_production_state(copy_state)


def register_production_states_for_processes(resource: resources.Resourcex, state_factory: state_factory.StateFactory,
                                             _env: env.Environment):
    states: List[state.State] = []
    for process_instance in resource.processes:
        values = {"new_state": {'ID': process_instance.process_data.ID, 'description': process_instance.process_data.description, 
            'time_model_id': process_instance.process_data.time_model_id}}
        if isinstance(process_instance, process.ProductionProcess):
            # values["new_state"].update({"type": state_data.StateTypeEnum.ProductionState})
            state_factory.create_states_from_configuration_data({"ProductionState": values})
        elif isinstance(process_instance, process.TransportProcess):
            # values["new_state"].update({'type': state_data.StateTypeEnum.TransportState})
            state_factory.create_states_from_configuration_data({"TransportState": values})
        _state = state_factory.get_states(IDs=[process_instance.process_data.ID]).pop()
        states.append(_state)
    register_production_states(resource, states, _env)




class ResourceFactory(BaseModel):
    envir: env.Environment
    process_factory: process_factory.ProcessFactory
    state_factory: state_factory.StateFactory
    queue_factory: queue_factory.QueueFactory

    resource_data: List[RESOURCE_DATA_UNION] = []
    resources: List[resources.RESOURCE_UNION] = []
    controllers: List[Union[control.SimpleController, control.TransportController]] = []

    class Config:
        arbitrary_types_allowed = True

    def create_resources_from_configuration_data(self, configuration_data: dict):
        for values in configuration_data.values():
            self.resource_data.append(parse_obj_as(RESOURCE_DATA_UNION, values))
            self.add_resource(self.resource_data[-1])

    def create_resources_from_adapter(self, adapter: adapter.Adapter):
        for resource_data in adapter.resource_data:
            self.add_resource(resource_data)


    def adjust_process_capacities(self, resource_data: RESOURCE_DATA_UNION):
        for process, capacity in zip(resource_data.processes, resource_data.process_capacity):
            resource_data.processes += [process]*(capacity - 1)

    def get_queues_for_resource(self, resource_data: ProductionResourceData) -> Tuple[List[store.Queue], List[store.Queue]]:
        input_queues = []
        output_queues = []
        if resource_data.input_queues:
            input_queues = self.queue_factory.get_queues(resource_data.input_queues)
        else:
            raise ValueError("No input queues for resource" + resource_data.ID)
        if resource_data.output_queues:
            output_queues = self.queue_factory.get_queues(resource_data.output_queues)
        else:
            raise ValueError("No output queues for resource" + resource_data.ID)

        return input_queues, output_queues


    def add_resource(self, resource_data: RESOURCE_DATA_UNION):
        values = {"env": self.envir, "resource_data": resource_data}
        processes = self.process_factory.get_processes_in_order(resource_data.processes)
        values.update({"processes": processes})

        if resource_data.process_capacity:
            self.adjust_process_capacities(resource_data)

        # controllers = Union[control.TransportController, control.SimpleController]

        # controller = parse_obj_as(controllers, {"control_policy": resource_data.control_policy,})

        controller_class = get_class_from_str(name=resource_data.controller, cls_dict=CONTROLLER_DICT)
        control_policy = get_class_from_str(name=resource_data.control_policy, cls_dict=CONTROL_POLICY_DICT)
        print(controller_class, control_policy)
        controller: Union[control.SimpleController, control.TransportController] = controller_class(
                control_policy=control_policy, envir=self.envir)
        self.controllers.append(controller)
        values.update({"controller": controller})

        if isinstance(resource_data, ProductionResourceData):
            input_queues, output_queues = self.get_queues_for_resource(resource_data)
            values.update({"input_queues": input_queues, "output_queues": output_queues})

        print(values.keys())
        print(values["resource_data"])
        resource_object = parse_obj_as(resources.RESOURCE_UNION, values)
        controller.set_resource(resource_object)

        states = self.state_factory.get_states(resource_data.states)
        register_states(resource_object, states, self.envir)
        register_production_states_for_processes(resource_object, self.state_factory, self.envir)
        self.resources.append(resource_object)

    def start_resources(self):
        for _resource in self.resources:
            _resource.start_states()
            
        for controller in self.controllers:
            self.envir.process(controller.control_loop())

    def get_resource(self, ID):
        return [r for r in self.resources if r.resource_data.ID == ID].pop()

    def get_controller_of_resource(self, _resource: resources.Resourcex) -> Optional[Union[control.SimpleController, control.TransportController]]:
        for controller in self.controllers:
            if controller.resource == _resource:
                return controller

    def get_resources(self, IDs: List[str]) -> List[resources.Resourcex]:
        return [r for r in self.resources if r.resource_data.ID in IDs]

    def get_resources_with_process(self, __process: process.Process) -> List[resources.Resourcex]:
        return [r for r in self.resources if __process in r.processes]
