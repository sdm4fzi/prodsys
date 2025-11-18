from __future__ import annotations

import copy
from functools import partial
from typing import Callable, Dict, List, Optional, Union, Tuple, TYPE_CHECKING

from prodsys.simulation import sim
from prodsys.simulation import process, state
from prodsys.util.util import get_class_from_str


from prodsys.models.resource_data import (
    ControllerEnum,
    ResourceControlPolicy,
    ResourceData,
    SystemResourceData,
    TransportControlPolicy,
)
from prodsys.models import performance_data
from prodsys.factories import port_factory, process_factory, state_factory

from prodsys.simulation import control, resources
from prodsys.simulation.lot_handler import LotHandler

if TYPE_CHECKING:
    from prodsys.simulation import port
    from prodsys.models import production_system_data


CONTROLLER_DICT: Dict = {
    ControllerEnum.PipelineController: control.Controller,
    ControllerEnum.BatchController: control.BatchController,
}

CONTROL_POLICY_DICT: Dict = {
    ResourceControlPolicy.FIFO: control.FIFO_control_policy,
    ResourceControlPolicy.LIFO: control.LIFO_control_policy,
    ResourceControlPolicy.SPT: control.SPT_control_policy,
    TransportControlPolicy.SPT_transport: control.SPT_transport_control_policy,
    TransportControlPolicy.NEAREST_ORIGIN_AND_LONGEST_TARGET_QUEUES_TRANSPORT: control.nearest_origin_and_longest_target_queues_transport_control_policy,
    TransportControlPolicy.NEAREST_ORIGIN_AND_SHORTEST_TARGET_INPUT_QUEUES_TRANSPORT: control.nearest_origin_and_shortest_target_input_queues_transport_control_policy,
}


def get_scheduled_control_policy(
    schedule: List[performance_data.Event], fallback_policy: Callable
) -> Callable:
    product_sequence_indices = {}
    for index, event in enumerate(schedule):
        product_sequence_indices[event.product] = index

    return partial(
        control.scheduled_control_policy, product_sequence_indices, fallback_policy
    )


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
            actual_state.env = None
            active_before = actual_state.active
            actual_state.active = None
            copy_state = copy.deepcopy(actual_state)
            actual_state.env = _env
            copy_state.active = active_before
            copy_state.env = _env
            copy_state.active = _env.event()
            resource.add_production_state(copy_state)


def register_production_state_for_process(
    resource: resources.Resource,
    process_instance: process.PROCESS_UNION,
    state_factory: state_factory.StateFactory,
    _env: sim.Environment,
):
    state_data_dict = {
        "new_state": {
            "ID": process_instance.data.ID,
            "description": process_instance.data.description,
            "time_model_id": process_instance.data.time_model_id,
        }
    }
    existence_condition = any(
        True
        for state in state_factory.states.values()
        if state.data.ID == process_instance.data.ID
    )
    if (
        isinstance(process_instance, process.ProductionProcess)
        or isinstance(process_instance, process.CapabilityProcess)
        or isinstance(process_instance, process.ReworkProcess)
    ) and not existence_condition:
        state_factory.create_states_from_configuration_data(
            {"ProductionState": state_data_dict}
        )
    elif (
        isinstance(
            process_instance,
            (process.TransportProcess, process.LinkTransportProcess),
        )
        and not existence_condition
    ):
        if process_instance.data.loading_time_model_id:
            state_data_dict["new_state"][
                "loading_time_model_id"
            ] = process_instance.data.loading_time_model_id
        if process_instance.data.unloading_time_model_id:
            state_data_dict["new_state"][
                "unloading_time_model_id"
            ] = process_instance.data.unloading_time_model_id
        state_factory.create_states_from_configuration_data(
            {"TransportState": state_data_dict}
        )
    _state = state_factory.get_states(IDs=[process_instance.data.ID]).pop()
    register_production_states(resource, [_state], _env)  # type: ignore


def register_production_states_for_processes(
    resource: resources.Resource,
    state_factory: state_factory.StateFactory,
    _env: sim.Environment,
):
    for process_instance, capacity in zip(
        resource.processes, resource.data.process_capacities
    ):
        # Skip ProcessModelProcess as it doesn't have a time_model_id
        # ProcessModels are containers for other processes and don't need their own production state
        if isinstance(process_instance, process.ProcessModelProcess):
            continue
        
        register_production_state_for_process(
            resource, process_instance, state_factory, _env
        )


def adjust_process_breakdown_states(
    resource: resources.Resource,
    state_factory: state_factory.StateFactory,
    _env: sim.Environment,
):
    process_breakdown_states = [
        state_instance
        for state_instance in resource.states
        if isinstance(state_instance, state.ProcessBreakDownState)
    ]
    for process_breakdown_state in process_breakdown_states:
        process_id = process_breakdown_state.data.process_id
        production_states = [
            state_instance
            for state_instance in resource.production_states
            if isinstance(state_instance, state.ProductionState)
            and state_instance.data.ID == process_id
        ]
        process_breakdown_state.set_production_states(production_states)


class ResourceFactory:
    """
    Factory class that creates and stores `prodsys.simulation` resource objects from `prodsys.models` resource objects.

    Args:
        env (sim.Environment): prodsys simulation environment.
        process_factory (process_factory.ProcessFactory): Factory that creates process objects.
        state_factory (state_factory.StateFactory): Factory that creates state objects.
        queue_factory (queue_factory.QueueFactory): Factory that creates queue objects.
    """

    def __init__(
        self,
        env: sim.Environment,
        process_factory: process_factory.ProcessFactory,
        state_factory: state_factory.StateFactory,
        queue_factory: port_factory.QueueFactory,
        schedule: Optional[List[performance_data.Event]] = None,
    ):
        self.env = env
        self.process_factory = process_factory
        self.state_factory = state_factory
        self.queue_factory = queue_factory
        self.schedule = schedule
        self.global_system_resource: resources.SystemResource = None
        self.all_resources: Dict[str, resources.Resource] = {}
        self.system_resources: Dict[str, resources.SystemResource] = {}
        self.transport_resources: Dict[str, resources.Resource] = {}
        self.resources_can_process: Dict[str, resources.Resource] = {}
        self.controllers: List[
            Union[
                control.ProductionProcessHandler,
                control.BatchController,
            ]
        ] = []
        self.lot_handler = LotHandler()

    def create_resources(self, adapter: production_system_data.ProductionSystemData):
        """
        Creates resource objects based on the given adapter.

        Args:
            adapter (adapter.ProductionSystemAdapter): Adapter that contains the resource data.
        """
        for resource_data in adapter.resource_data:
            self.add_resource(resource_data.model_copy(deep=True))
        self.create_global_system_resource()

    def is_resource_a_subresource(self, resource: resources.Resource) -> bool:
        """
        Checks if the resource is a subresource.
        """
        if any(resource.data.ID in system_resource.data.subresource_ids for system_resource in self.system_resources.values()):
            return True
        return False

    def create_global_system_resource(self):
        """
        Creates the global system resource.
        """
        # TODO: resolve later that users can specify a system resource, so this function is only needed if no global system resource is specified!
        all_resources = [resource for resource in self.all_resources.values() if not self.is_resource_a_subresource(resource)]

        resource_data = SystemResourceData(
            ID="GlobalSystemResource",
            description="Global System Resource",
            capacity=0,
            process_ids=[],
            location=[0, 0],
            control_policy=ResourceControlPolicy.FIFO,
            controller=ControllerEnum.PipelineController,
            subresource_ids=[resource.data.ID for resource in all_resources],
        )
        controller_class = get_class_from_str(
            name=resource_data.controller, cls_dict=CONTROLLER_DICT
        )
        control_policy = get_class_from_str(
            name=resource_data.control_policy, cls_dict=CONTROL_POLICY_DICT
        )
        controller: Union[
            control.Controller,
            control.BatchController,
        ] = controller_class(control_policy=control_policy, env=self.env, lot_handler=self.lot_handler)
        self.global_system_resource = resources.SystemResource(
            env=self.env,
            data=resource_data,
            processes=[],
            controller=controller,
            subresources=[resource for resource in all_resources],
        )
        controller.set_resource(self.global_system_resource)

        states = self.state_factory.get_states(resource_data.state_ids)
        register_states(self.global_system_resource, states, self.env)
        register_production_states_for_processes(
            self.global_system_resource, self.state_factory, self.env
        )
        adjust_process_breakdown_states(self.global_system_resource, self.state_factory, self.env)

    def get_ports_for_resource(
        self, resource_data: ResourceData
    ) -> List[port.Queue]:
        ports = []
        if resource_data.ports:
            ports = self.queue_factory.get_queues(resource_data.ports)
        elif resource_data.control_policy not in TransportControlPolicy:
            raise ValueError("Ports not found for resource" + resource_data.ID)

        return ports

    def get_buffers_for_resource(
        self, resource_data: ResourceData
    ) -> List[port.Queue]:
        if not resource_data.buffers:
            return []
        buffers = self.queue_factory.get_queues(resource_data.buffers)
        return buffers

    def add_resource(self, resource_data: ResourceData):
        values = {"env": self.env, "data": resource_data}
        processes = self.process_factory.get_processes_in_order(
            resource_data.process_ids
        )
        values.update({"processes": processes})
        if resource_data.can_move is None:
            if any(isinstance(p, process.TransportProcess) for p in processes):
                values.update({"can_move": True})
            else:
                values.update({"can_move": False})
        else:
            values.update({"can_move": resource_data.can_move})
        if any(isinstance(p, process.ProductionProcess) for p in processes) or any(
            isinstance(p, process.CapabilityProcess) for p in processes
        ):
            values.update({"can_process": True})

        controller_class = get_class_from_str(
            name=resource_data.controller, cls_dict=CONTROLLER_DICT
        )
        control_policy = get_class_from_str(
            name=resource_data.control_policy, cls_dict=CONTROL_POLICY_DICT
        )
        controller: Union[
            control.Controller,
            control.BatchController,
        ] = controller_class(control_policy=control_policy, env=self.env, lot_handler=self.lot_handler)
        self.controllers.append(controller)
        values.update({"controller": controller})

        ports = self.get_ports_for_resource(resource_data)
        values.update({"ports": ports})
        buffers = self.get_buffers_for_resource(resource_data)
        values.update({"buffers": buffers})

        # Create appropriate resource type based on data type
        if isinstance(resource_data, SystemResourceData):
            # Get subresources for SystemResource
            subresources = [self.all_resources[sub_id] for sub_id in resource_data.subresource_ids if sub_id in self.all_resources]
            values.update({
                "subresources": subresources,
            })
            resource_object = resources.SystemResource(**values)
            self.system_resources[resource_object.data.ID] = resource_object
        else:
            resource_object = resources.Resource(**values)
        controller.set_resource(resource_object)

        states = self.state_factory.get_states(resource_data.state_ids)
        register_states(resource_object, states, self.env)
        register_production_states_for_processes(
            resource_object, self.state_factory, self.env
        )
        adjust_process_breakdown_states(resource_object, self.state_factory, self.env)
        self.all_resources[resource_object.data.ID] = resource_object
        if resource_object.can_process:
            self.resources_can_process[resource_object.data.ID] = resource_object
        else:
            self.transport_resources[resource_object.data.ID] = resource_object


    def start_resources(self):
        """
        Method starts the simpy processes of the controllers of the resources to initialize the simulation.
        """
        for _resource in self.all_resources.values():
            _resource.start_states()

        for controller in self.controllers:
            self.env.process(controller.control_loop())  # type: ignore


        self.global_system_resource.start_states()
        self.env.process(self.global_system_resource.controller.control_loop())  # type: ignore

    def get_resource(self, ID: str) -> resources.Resource:
        """
        Method returns a resource object with the given ID.

        Args:
            ID (str): ID of the resource object.

        Returns:
            resources.RESOURCE_UNION: Resource object with the given ID.
        """
        return self.all_resources[ID]

    def get_controller_of_resource(self, _resource: resources.Resource) -> Optional[
        Union[
            control.Controller,
            control.BatchController,
        ]
    ]:
        """
        Method returns the controller of the given resource.

        Args:
            _resource (resources.Resource): Resource object.

        Returns:
            Optional[Union[control.ProductionController, control.TransportController, control.BatchController]]: Controller of the given resource.
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
        return [self.all_resources[ID] for ID in IDs]

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
            for res in self.all_resources.values()
            if target_process.data.ID in res.data.process_ids
        ]

    def get_transport_resources(self) -> List[resources.Resource]:
        """
        Method returns a list of transport resource objects.

        Returns:
            List[resources.ResourceData]: List of transport resource objects.
        """
        return self.transport_resources.values()

    def get_production_resources(self) -> List[resources.Resource]:
        """
        Method returns a list of production resource objects.

        Returns:
            List[resources.ResourceData]: List of production resource objects.
        """
        return self.resources_can_process.values()

    def add_process_to_resource(
        self, resource: resources.Resource, process_id: str
    ) -> resources.Resource:
        """
        Method patches a resource with a process.
        
        Args:
            resource (resources.Resource): Resource object.
            process_id (str): Process ID.
            
        Returns:
            resources.Resource: Resource object with the process.
        """
        resource.data.process_ids.append(process_id)
        resource.data.process_capacities.append(1)
        process_obj = self.process_factory.get_process(process_id)
        resource.processes.append(process_obj)
        register_production_state_for_process(
            resource, process_obj, self.state_factory, self.env
        )
        # active production states
        relevant_production_states = [
            state_instance
            for state_instance in resource.production_states
            if state_instance.data.ID == process_id
        ]
        for relevant_production_state in relevant_production_states:
            relevant_production_state.activate_state()

        # this might not work since breakdown states are not automatically added
        process_breakdown_states = [
            state_instance.model_copy(deep=True)
            for state_instance in self.state_factory.states.values()
            if isinstance(state_instance, state.ProcessBreakDownState)
            and state_instance.data.process_id == process_id
        ]
        resource.data.state_ids.extend(
            [
                state_instance.data.ID
                for state_instance in process_breakdown_states
            ]
        )
        resource.states.extend(process_breakdown_states)
        adjust_process_breakdown_states(resource, self.state_factory, self.env)
        return resource
