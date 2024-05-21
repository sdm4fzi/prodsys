from __future__ import annotations

import copy
from typing import Dict, List, Optional, Union, Tuple, TYPE_CHECKING

from pydantic import BaseModel, parse_obj_as

from prodsys.simulation import sim
from prodsys.simulation import process, state
from prodsys.util.util import get_class_from_str


from prodsys.models.resource_data import (
    RESOURCE_DATA_UNION,
    ProductionResourceData,
    ControllerEnum,
    ResourceControlPolicy, TransportControlPolicy
)
from prodsys.factories import process_factory, state_factory, queue_factory

from prodsys.simulation import control, resources

if TYPE_CHECKING:
    from prodsys.simulation import store
    from prodsys.adapters import adapter


CONTROLLER_DICT: Dict = {
    ControllerEnum.PipelineController: control.ProductionController,
    ControllerEnum.TransportController: control.TransportController,
}

CONTROL_POLICY_DICT: Dict = {
    ResourceControlPolicy.FIFO: control.FIFO_control_policy,
    ResourceControlPolicy.LIFO: control.LIFO_control_policy,
    ResourceControlPolicy.SPT: control.SPT_control_policy,
    TransportControlPolicy.SPT_transport: control.SPT_transport_control_policy,
    TransportControlPolicy.NEAREST_ORIGIN_AND_LONGEST_TARGET_QUEUES_TRANSPORT : control.nearest_origin_and_longest_target_queues_transport_control_policy,
    TransportControlPolicy.NEAREST_ORIGIN_AND_SHORTEST_TARGET_INPUT_QUEUES_TRANSPORT : control.nearest_origin_and_shortest_target_input_queues_transport_control_policy,

}


def register_states(
    resource: resources.Resource,
    states: List[state.STATE_UNION],
    _env: sim.Environment,
):
    for actual_state in states:
        copy_state = copy.deepcopy(actual_state)
        copy_state.env = _env
        resource.add_state(copy_state)

def register_production_states(
    resource: resources.Resource,
    states: List[state.ProductionState],
    _env: sim.Environment,
):
    for actual_state, process_capacity in zip(states, resource.data.process_capacities):
        for _ in range(process_capacity):
            copy_state = copy.deepcopy(actual_state)
            copy_state.env = _env
            resource.add_production_state(copy_state)



def register_production_states_for_processes(
    resource: resources.Resource,
    state_factory: state_factory.StateFactory,
    _env: sim.Environment,
):
    states: List[state.State] = []
    for process_instance, capacity in zip(resource.processes, resource.data.process_capacities):
        values = {
            "new_state": {
                "ID": process_instance.process_data.ID,
                "description": process_instance.process_data.description,
                "time_model_id": process_instance.process_data.time_model_id,
            }
        }
        existence_condition = any(True for state in state_factory.states if state.state_data.ID == process_instance.process_data.ID)
        if (isinstance(process_instance, process.ProductionProcess) or isinstance(process_instance, process.CapabilityProcess)) and not existence_condition:
            state_factory.create_states_from_configuration_data({"ProductionState": values})
        elif isinstance(process_instance, process.TransportProcess) and not existence_condition:
            state_factory.create_states_from_configuration_data({"TransportState": values})
        _state = state_factory.get_states(IDs=[process_instance.process_data.ID]).pop()
        states.append(_state)
    register_production_states(resource, states, _env)  # type: ignore

def adjust_process_breakdown_states(
    resource: resources.Resource,
    state_factory: state_factory.StateFactory,
    _env: sim.Environment,
):  
    process_breakdown_states = [state_instance for state_instance in resource.states if isinstance(state_instance, state.ProcessBreakDownState)]
    for process_breakdown_state in process_breakdown_states:
        process_id = process_breakdown_state.state_data.process_id
        production_states = [state_instance for state_instance in resource.production_states if isinstance(state_instance, state.ProductionState) and state_instance.state_data.ID == process_id]
        process_breakdown_state.set_production_states(production_states)



class ResourceFactory(BaseModel):
    """
    Factory class that creates and stores `prodsys.simulation` resource objects from `prodsys.models` resource objects.

    Args:
        env (sim.Environment): prodsys simulation environment.
        process_factory (process_factory.ProcessFactory): Factory that creates process objects.
        state_factory (state_factory.StateFactory): Factory that creates state objects.
        queue_factory (queue_factory.QueueFactory): Factory that creates queue objects.
    """
    env: sim.Environment
    process_factory: process_factory.ProcessFactory
    state_factory: state_factory.StateFactory
    queue_factory: queue_factory.QueueFactory

    resource_data: List[RESOURCE_DATA_UNION] = []
    resources: List[resources.RESOURCE_UNION] = []
    controllers: List[
        Union[control.ProductionController, control.TransportController]
    ] = []

    class Config:
        arbitrary_types_allowed = True

    def create_resources(self, adapter: adapter.ProductionSystemAdapter):
        """
        Creates resource objects based on the given adapter.

        Args:
            adapter (adapter.ProductionSystemAdapter): Adapter that contains the resource data.
        """
        for resource_data in adapter.resource_data:
            self.add_resource(resource_data.copy(deep=True))

    def get_queues_for_resource(
        self, resource_data: ProductionResourceData
    ) -> Tuple[List[store.Queue], List[store.Queue]]:
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
        values = {"env": self.env, "data": resource_data}
        processes = self.process_factory.get_processes_in_order(resource_data.process_ids)

        values.update({"processes": processes})

        controller_class = get_class_from_str(
            name=resource_data.controller, cls_dict=CONTROLLER_DICT
        )
        control_policy = get_class_from_str(
            name=resource_data.control_policy, cls_dict=CONTROL_POLICY_DICT
        )
        controller: Union[
            control.ProductionController, control.TransportController
        ] = controller_class(control_policy=control_policy, env=self.env)
        self.controllers.append(controller)
        values.update({"controller": controller})

        if isinstance(resource_data, ProductionResourceData):
            input_queues, output_queues = self.get_queues_for_resource(resource_data)
            values.update(
                {"input_queues": input_queues, "output_queues": output_queues}
            )
        resource_object = parse_obj_as(resources.RESOURCE_UNION, values)
        # print(resource_object._env)
        controller.set_resource(resource_object)

        states = self.state_factory.get_states(resource_data.state_ids)
        register_states(resource_object, states, self.env)
        register_production_states_for_processes(
            resource_object, self.state_factory, self.env
        )
        adjust_process_breakdown_states(resource_object, self.state_factory, self.env)
        self.resources.append(resource_object)

    def start_resources(self):
        """
        Method starts the simpy processes of the controllers of the resources to initialize the simulation.
        """
        for _resource in self.resources:
            _resource.start_states()

        for controller in self.controllers:
            self.env.process(controller.control_loop())  # type: ignore

    def get_resource(self, ID: str) -> resources.RESOURCE_UNION:
        """
        Method returns a resource object with the given ID.

        Args:
            ID (str): ID of the resource object.

        Returns:
            resources.RESOURCE_UNION: Resource object with the given ID.
        """
        return [r for r in self.resources if r.data.ID == ID].pop()

    def get_controller_of_resource(
        self, _resource: resources.Resource
    ) -> Optional[Union[control.ProductionController, control.TransportController]]:
        """
        Method returns the controller of the given resource.

        Args:
            _resource (resources.Resource): Resource object.

        Returns:
            Optional[Union[control.ProductionController, control.TransportController]]: Controller of the given resource.
        """
        for controller in self.controllers:
            if controller.resource == _resource:
                return controller

    def get_resources(self, IDs: List[str]) -> List[resources.Resource]:
        """
        Method returns a list of resource objects with the given IDs.

        Args:
            IDs (List[str]): List of IDs that is used to sort the resource objects.

        Returns:
            List[resources.Resource]: List of resource objects with the given IDs.
        """
        return [r for r in self.resources if r.data.ID in IDs]

    def get_resources_with_process(
        self, target_process: process.Process
    ) -> List[resources.Resource]:
        """
        Method returns a list of resource objects that contain the given process.

        Args:
            target_process (process.Process): Process object that is used to filter the resource objects.

        Returns:
            List[resources.Resource]: List of resource objects that contain the given process.
        """
        return [
            res
            for res in self.resources
            if target_process.process_data.ID in res.data.process_ids
        ]
