from __future__ import annotations

import copy
from typing import Dict, List, Optional, Union, Tuple, TYPE_CHECKING

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
from prodsys.factories import port_factory, process_factory, state_factory

from prodsys.simulation import control, resources

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
    for process_instance, capacity in zip(
        resource.processes, resource.data.process_capacities
    ):
        process_instance: process.PROCESS_UNION
        state_data_dict = {
            "new_state": {
                "ID": process_instance.data.ID,
                "description": process_instance.data.description,
                "time_model_id": process_instance.data.time_model_id,
            }
        }
        existence_condition = process_instance.data.ID in state_factory.states
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
        states.append(_state)
    register_production_states(resource, states, _env)  # type: ignore


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
    ):
        self.env = env
        self.process_factory = process_factory
        self.state_factory = state_factory
        self.queue_factory = queue_factory
        self.all_resources: Dict[str, resources.Resource] = {}
        self.resources_can_move: Dict[str, resources.Resource] = {}
        self.resources_can_process: Dict[str, resources.Resource] = {}
        self.controllers: List[
            Union[
                control.ProductionProcessHandler,
                control.BatchController,
            ]
        ] = []

    def create_resources(self, adapter: production_system_data.ProductionSystemData):
        """
        Creates resource objects based on the given adapter.

        Args:
            adapter (adapter.ProductionSystemAdapter): Adapter that contains the resource data.
        """
        for resource_data in adapter.resource_data:
            self.add_resource(resource_data.model_copy(deep=True))

    def get_ports_for_resource(
        self, resource_data: ResourceData
    ) -> List[port.Queue]:
        ports = []
        if resource_data.ports:
            ports = self.queue_factory.get_queues(resource_data.ports)
        else:
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
        ] = controller_class(control_policy=control_policy, env=self.env)
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
        if resource_object.can_move:
            self.resources_can_move[resource_object.data.ID] = resource_object
        if resource_object.can_process:
            self.resources_can_process[resource_object.data.ID] = resource_object

    def start_resources(self):
        """
        Method starts the simpy processes of the controllers of the resources to initialize the simulation.
        """
        for _resource in self.all_resources.values():
            _resource.start_states()

        for controller in self.controllers:
            self.env.process(controller.control_loop())  # type: ignore

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

    def get_movable_resources(self) -> List[resources.Resource]:
        """
        Method returns a list of transport resource objects.

        Returns:
            List[resources.ResourceData]: List of transport resource objects.
        """
        return self.resources_can_move.values()

    def get_production_resources(self) -> List[resources.Resource]:
        """
        Method returns a list of production resource objects.

        Returns:
            List[resources.ResourceData]: List of production resource objects.
        """
        return self.resources_can_process.values()
