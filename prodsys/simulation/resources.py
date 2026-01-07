from __future__ import annotations

from typing import TYPE_CHECKING, List, Generator, Optional, Union

import random

import logging

from prodsys.models import port_data
from prodsys.simulation.dependency import DependencyInfo



from simpy.resources import resource
from simpy import events

if TYPE_CHECKING:
    from prodsys.simulation import control, state
    from prodsys.simulation.dependency import DependedEntity, Dependency

    # from prodsys.simulation.process import PROCESS_UNION
    from prodsys.simulation import sim

    from prodsys.simulation.process import PROCESS_UNION
    from prodsys.simulation.locatable import Locatable
    from prodsys.simulation import router


from prodsys.models.resource_data import (
    ResourceData,
    SystemResourceData,
)
from prodsys.util import util

logger = logging.getLogger(__name__)


class Resource(resource.Resource):
    """
    Base class for all resources.

    Args:
        env (sim.Environment): The simpy environment.
        data (RESOURCE_DATA_UNION): The resource data.
        processes (List[PROCESS_UNION]): The processes.
        controller (control.Controller): The controller.
        states (List[state.State]): The states of the resource for breakdowns.
        production_states (List[state.State]): The states of the resource for production.
        setup_states (List[state.SetupState]): The states of the resource for setups.
        active (events.Event): The event that is triggered when the resource is active.
        current_setup (PROCESS_UNION): The current setup.
        reserved_setup (PROCESS_UNION): The reserved setup.
    """

    def __init__(
        self,
        env: sim.Environment,
        data: ResourceData,
        processes: List[PROCESS_UNION],
        controller: control.Controller,
        can_move: bool = False,
        can_process: bool = False,
        states: List[state.State] = None,
        production_states: List[state.State] = None,
        setup_states: List[state.SetupState] = None,
        charging_states: List[state.ChargingState] = None,
        ports: List[port.Queue] = None,
        buffers: List[port.Queue] = None
    ):
        super().__init__(env, capacity=data.capacity)
        self.env = env
        self.data = data
        self.processes = processes
        self.controller = controller
        self.states = states if states else []
        self.production_states = production_states if production_states else []
        self.setup_states = setup_states if setup_states else []
        self.charging_states = charging_states if charging_states else []

        self.dependencies: List[Dependency] = []
        self.depended_entities: List[DependedEntity] = []
        self.dependency_info: DependencyInfo = DependencyInfo(resource_id=data.ID)

        self.active = events.Event(self.env).succeed()
        self.current_setup: PROCESS_UNION = None
        self.reserved_setup: PROCESS_UNION = None

        self.can_move = can_move
        self.can_process = can_process

        self.bound = False
        self.current_dependant: Union[Resource] = None

        self.ports = ports if ports else []
        self.buffers = buffers if buffers else []
        self.current_locatable = self

        self.full = False

    def bind_to_dependant(self, dependant: Resource) -> None:
        """
        Binds the resource to a depended entity.

        Args:
            dependant (DependedEntity): The depended entity.
        """
        self.current_dependant = dependant
        self.bound = True

    def release_from_dependant(self) -> None:
        """
        Releases the resource from the depended entity.
        """
        self.current_dependant = None
        self.bound = False

    @property
    def capacity_current_setup(self) -> int:
        """
        Returns the capacity of the resource for the current setup with considering that the resource could be in a setup process.

        Returns:
            int: The capacity of the resource for the current setup.
        """
        if not self.current_setup and not self.reserved_setup:
            return self.capacity
        
        # Determine which setup to use for capacity calculation
        setup_to_check = None
        if (
            self.reserved_setup
            and self.current_setup
            and self.current_setup.data.ID != self.reserved_setup.data.ID
        ):
            setup_to_check = self.reserved_setup
        elif self.reserved_setup:
            setup_to_check = self.reserved_setup
        elif self.current_setup:
            setup_to_check = self.current_setup
        
        # If setup is a ProcessModelProcess, it doesn't have production states
        # so return base capacity instead
        from prodsys.simulation.process import ProcessModelProcess
        if setup_to_check and isinstance(setup_to_check, ProcessModelProcess):
            return self.capacity
        
        current_setup_ID = setup_to_check.data.ID
        length = len(
            [
                state
                for state in self.production_states
                if state.data.ID == current_setup_ID
            ]
        )
        # If no production states found for the setup, fall back to base capacity
        # This can happen for process models or other processes without explicit production states
        return length if length > 0 else self.capacity

    def wait_for_free_process(
        self, process: PROCESS_UNION
    ) -> Generator[state.State, None, None]:
        """
        Wait for a free process of a resource.

        Args:
            resource (resources.ResourceData): The resource.
            process (process.Process): The process.

        Returns:
            Generator: The generator yields when a process is free.

        Yields:
            Generator: The generator yields when a process is free.
        """
        while True:
            free_state = self.get_free_process(process)
            if free_state is not None:
                return free_state
            yield self.controller.state_changed

    def reserve_setup(self, process: PROCESS_UNION) -> None:
        """
        Reserves the setup of the resource for a process. This is used to prevent that capacity is wrong estimated during setup.

        Args:
            process (PROCESS_UNION): The process that wants to reserve the setup.
        """
        self.reserved_setup = process

    def unreserve_setup(self) -> None:
        """
        Unreserves the setup of the resource. This is used to prevent that the resource is used for another process while it is in a setup process.
        """
        self.reserved_setup = None

    @property
    def in_setup(self) -> bool:
        """
        Returns if the resource is in a setup process.

        Returns:
            bool: True if the resource is in a setup process, False otherwise.
        """
        return self.reserved_setup is not None

    def update_full(self) -> None:
        """
        Returns if the resource is full.

        Returns:
            bool: True if the resource is full or in setup, False otherwise.
        """
        self.full = self.get_free_capacity() <= 0

    def get_free_capacity(self) -> int:
        """
        Returns the free capacity of the resource.

        Returns:
            int: The free capacity of the resource.
        """
        return self.capacity_current_setup - (
            self.controller.num_running_processes
            + self.controller.reserved_requests_count
        )

    @property
    def requires_charging(self) -> bool:
        """
        Returns if the resource requires charging.

        Returns:
            bool: True if the resource requires charging, False otherwise.
        """
        return any(
            [
                state_instance.requires_charging()
                for state_instance in self.charging_states
                if isinstance(state_instance, state.ChargingState)
            ]
        )

    def charge(self) -> Generator:
        """
        Charges the resource.

        Yields:
            Generator: The type of the yield depends on the resource.
        """
        for input_state in self.charging_states:
            if not input_state.requires_charging():
                continue
            yield self.env.process(input_state.process_state())

    def consider_battery_usage(self, amount: float) -> None:
        """
        Reduces the battery level of the resource.

        Args:
            amount (float): The amount to reduce the battery level.
        """
        for state_instance in self.charging_states:
            state_instance.add_battery_usage_time(amount)

    def get_controller(self) -> control.Controller:
        """
        Returns the controller of the resource.

        Returns:
            control.Controller: The controller of the resource.
        """
        return self.controller

    def add_state(self, input_state: state.STATE_UNION) -> None:
        """
        Adds a state to the resource.

        Args:
            input_state (state.STATE_UNION): The state to add.
        """
        if isinstance(input_state, state.SetupState):
            self.setup_states.append(input_state)
        elif isinstance(input_state, state.ChargingState):
            self.charging_states.append(input_state)
        else:
            self.states.append(input_state)
        input_state.set_resource(self)

    def add_production_state(self, input_state: state.ProductionState) -> None:
        """
        Adds a production state to the resource.

        Args:
            input_state (state.ProductionState): The production state to add.
        """
        self.production_states.append(input_state)
        input_state.set_resource(self)

    def start_states(self):
        """
        Starts the simpy processes of the states of the resource in simpy.
        """
        resource.Resource.__init__(self, self.env, capacity=self.data.capacity)
        self.active = events.Event(self.env).succeed()
        for actual_state in (
            self.states
            + self.production_states
            + self.setup_states
            + self.charging_states
        ):
            actual_state.activate_state()
        for actual_state in self.states:
            actual_state.process = self.env.process(actual_state.process_state())

    def get_process(self, process: PROCESS_UNION) -> state.State:
        """
        Returns the ProducitonState or CapabilityState of the resource for a process.

        Args:
            process (PROCESS_UNION): The process to get the state for.

        Raises:
            ValueError: If the process is not found in the resource.

        Returns:
            state.State: The state of the resource for the process.
        """
        possible_states = [
            actual_state
            for actual_state in self.production_states
            if actual_state.data.ID == process.data.ID
        ]
        if not possible_states:
            raise ValueError(
                f"Process {process.data.ID} not found in resource {self.data.ID}"
            )
        return random.choice(possible_states)

    def get_processes(self, process: PROCESS_UNION) -> List[state.State]:
        """
        Returns the ProducitonState or CapabilityState of the resource for a process.

        Args:
            process (PROCESS_UNION): The process to get the state for.

        Raises:
            ValueError: If the process is not found in the resource.

        Returns:
            List[state.State]: The state of the resource for the process.
        """
        possible_states = [
            actual_state
            for actual_state in self.production_states
            if actual_state.data.ID == process.data.ID
        ]
        if not possible_states:
            raise ValueError(
                f"Process {process.data.ID} not found in resource {self.data.ID}"
            )
        return possible_states

    def get_free_process(self, process: PROCESS_UNION) -> Optional[state.State]:
        """
        Returns a free ProductionState or CapabilityState of the resource for a process.

        Args:
            process (PROCESS_UNION): The process to get the state for.

        Returns:
            Optional[state.State]: The state of the resource for the process.
        """
        for actual_state in self.production_states:
            if (
                actual_state.data.ID == process.data.ID
                and actual_state.process is None
                and not actual_state.reserved
            ):
                return actual_state
        return None

    def get_free_processes(self, process: PROCESS_UNION) -> Optional[List[state.State]]:
        """
        Returns all free ProductionState or CapabilityState of the resource for a process.

        Args:
            process (process.PROCESS_UNION): The process to get the state for.

        Returns:
            List[state.State]: The state of the resource for the process.
        """
        return [
            actual_state
            for actual_state in self.production_states
            if actual_state.data.ID == process.data.ID
            and (actual_state.process is None or not actual_state.process.is_alive)
        ]

    def get_location(
        self
    ) -> List[float]:
        return self.data.location

    def get_input_queue_length(self) -> int:
        """
        Returns total number of items in all input_queues.

        Returns:
            int: Sum of items in the resources input-queues.
        """
        return sum([len(q.items) for q in self.ports if q.data.interface_type in [port_data.PortInterfaceType.INPUT, port_data.PortInterfaceType.INPUT_OUTPUT]])

    def get_output_queue_length(self) -> int:
        """
        Returns total number of items in all output_queues.

        Returns:
            int: Sum of items in the resources output-queues.
        """
        return sum([len(q.items) for q in self.ports if q.data.interface_type in [port_data.PortInterfaceType.OUTPUT, port_data.PortInterfaceType.INPUT_OUTPUT]])

    def set_location(self, new_location: Locatable) -> None:
        """
        Sets the location of the resource.

        Args:
            new_location (List[float]): The new location of the resource. Has to have length 2.
        """
        self.data.location = new_location.get_location()
        self.current_locatable = new_location

    def get_states(self) -> List[state.State]:
        """
        Returns the states of the resource.

        Returns:
            List[state.State]: The states of the resource.
        """
        return self.states

    def activate(self):
        """
        Activates the resource after a breakdwon or non-scheduled period.
        """
        if any(
            [
                state_instance.active_breakdown
                for state_instance in self.states
                if isinstance(state_instance, state.BreakDownState)
            ]
        ):
            return
        if any(
            [
                state_instance.active_non_scheduled
                for state_instance in self.states
                if isinstance(state_instance, state.NonScheduledState)
            ]
        ):
            return
        self.active.succeed()

    def interrupt_states(self):
        """
        Interrupts the states of the resource.
        """
        if self.active.triggered:
            self.active = events.Event(self.env)
        for state_instance in self.setup_states + self.production_states:
            if (
                state_instance.process
                and state_instance.process.is_alive
                and not state_instance.interrupted
            ):
                state_instance.interrupt_process()

    def get_free_of_setups(self) -> Generator:
        """
        Returns a generator that yields when all setups are finished.

        Yields:
            Generator: The generator of the yield, which is yielded when all setups are finished.
        """
        running_setups = [
            state.process
            for state in self.setup_states
            if (state.process and state.process.is_alive)
        ]
        yield events.AllOf(self.env, running_setups)

    def setup(self, _process: PROCESS_UNION) -> Generator:
        """
        Sets up the resource for a process.

        Args:
            _process (PROCESS_UNION): The process to set up the resource for.

        Yields:
            Generator: The type of the yield depends on the process.
        """
        if self.current_setup is None:
            yield self.env.process(util.trivial_process(self.env))
            self.current_setup = _process
            return
        if self.reserved_setup:
            setup_to_compare = self.reserved_setup
        else:
            setup_to_compare = self.current_setup

        if setup_to_compare.data.ID == _process.data.ID:
            yield self.env.process(self.get_free_of_setups())
            yield self.env.process(util.trivial_process(self.env))
            return

        for input_state in self.setup_states:
            if (
                input_state.data.target_setup == _process.data.ID
                and input_state.data.origin_setup == setup_to_compare.data.ID
            ):
                self.reserve_setup(_process)
                yield self.env.process(self.get_free_of_setups())
                input_state.process = self.env.process(input_state.process_state())
                yield input_state.process
                input_state.process = None
                self.current_setup = _process
                self.unreserve_setup()

        else:
            yield self.env.process(self.get_free_of_setups())
            yield self.env.process(util.trivial_process(self.env))

    def add_ports(self, ports: List[port.Queue]):
        self.ports.extend(ports)


class SystemResource(Resource):
    """
    Class that represents a system resource. A system resource is a resource with subresources that can be used interchangeably.

    Args:
        env (sim.Environment): The simpy environment.
        data (SystemResourceData): The system resource data.
        processes (List[PROCESS_UNION]): The processes.
        controller (control.Controller): The controller.
        subresources (List[Resource]): The subresources of this system.
        system_ports (List[port.Queue]): The system ports for external communication.
        internal_routing_matrix (Dict[str, List[str]]): Internal routing matrix for routing within the system.
        can_move (bool): Whether the resource can move.
        can_process (bool): Whether the resource can process.
        states (List[state.State]): The states of the resource for breakdowns.
        production_states (List[state.State]): The states of the resource for production.
        setup_states (List[state.SetupState]): The states of the resource for setups.
        charging_states (List[state.ChargingState]): The states of the resource for charging.
        ports (List[port.Queue]): The ports of the resource.
    """

    def __init__(
        self,
        env: sim.Environment,
        data: SystemResourceData,
        processes: List[PROCESS_UNION],
        controller: control.Controller,
        subresources: List[Resource],
        can_move: bool = False,
        can_process: bool = False,
        states: List[state.State] = None,
        production_states: List[state.State] = None,
        setup_states: List[state.SetupState] = None,
        charging_states: List[state.ChargingState] = None,
        ports: List[port.Queue] = None,
        buffers: List[port.Queue] = None
    ):
        # Store original capacity for systems with capacity 0
        self._actual_capacity = data.capacity
        
        # Just to avoid an instantiation error for simpy resources, which does not allow capacity to be 0
        if data.capacity == 0:
            data.capacity = 1
            
        super().__init__(
            env, data, processes, controller, can_move, can_process,
            states, production_states, setup_states, charging_states, ports, buffers
        )

        self.subresources = subresources
        self.router: router.Router = None        
        # Create mapping for quick lookup
        self.subresource_map = {resource.data.ID: resource for resource in self.subresources}
        self.system_port_map = {port.data.ID: port for port in self.ports}

    def set_router(self, router: router.Router) -> None:
        """
        Sets the router of the system resource.
        """
        self.router = router

    def update_full(self) -> None:
        """
        Returns if the resource is full.

        Returns:
            bool: True if the resource is full or in setup, False otherwise.
        """
        if self._actual_capacity == 0:
            self.full = False
            return
        self.full = self.get_free_capacity() <= 0

    def get_free_capacity(self) -> int:
        """
        Returns the free capacity of the resource.

        Returns:
            int: The free capacity of the resource.
        """
        if self._actual_capacity == 0:
            return float("inf")
        return self._actual_capacity - (
            self.controller.num_running_processes
            + self.controller.reserved_requests_count
        )

    def get_system_port(self, port_id: str) -> Optional[port.Queue]:
        """
        Get a system port by ID.

        Args:
            port_id (str): The port ID.

        Returns:
            Optional[port.Queue]: The system port if found, None otherwise.
        """
        return self.system_port_map.get(port_id)

    def get_subresource(self, resource_id: str) -> Optional[Resource]:
        """
        Get a subresource by ID.

        Args:
            resource_id (str): The resource ID.

        Returns:
            Optional[Resource]: The subresource if found, None otherwise.
        """
        return self.subresource_map.get(resource_id)

    def can_handle_process(self, process_id: str) -> bool:
        """
        Check if this system resource can handle the given process.

        Args:
            process_id (str): The process ID to check.

        Returns:
            bool: True if the system can handle the process.
        """
        # Check if any subresource can handle the process
        return any(
            any(process.data.ID == process_id for process in subresource.processes)
            for subresource in self.subresources
        )


RESOURCE_UNION = Union[Resource, SystemResource]
""" Union Type for Resources. """

from prodsys.simulation import port, state
