from __future__ import annotations

from abc import ABC
from sys import intern
from typing import TYPE_CHECKING, List, Generator, Optional, Union

import random

import logging

from prodsys.simulation.dependency import DependedEntity, Dependency


logger = logging.getLogger(__name__)

from simpy.resources import resource
from simpy import events
from prodsys.simulation import sim, store

if TYPE_CHECKING:
    from prodsys.simulation import control, state

    # from prodsys.simulation.process import PROCESS_UNION

from prodsys.models.resource_data import (
    ResourceData,
)
from prodsys.util import util


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
        input_queues: List[store.Queue] = None,
        output_queues: List[store.Queue] = None,
        batch_size: Optional[int] = None,
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

        self.active = events.Event(self.env).succeed()
        self.current_setup: PROCESS_UNION = None
        self.reserved_setup: PROCESS_UNION = None

        self.can_move = can_move
        self.can_process = can_process

        self.input_queues = input_queues if input_queues else []

        self.output_queues = output_queues if output_queues else []
        self.batch_size = batch_size
        self.current_locatable = self

        self.full = False

    @property
    def capacity_current_setup(self) -> int:
        """
        Returns the capacity of the resource for the current setup with considering that the resource could be in a setup process.

        Returns:
            int: The capacity of the resource for the current setup.
        """
        if not self.current_setup and not self.reserved_setup:
            return self.capacity
        elif (
            self.reserved_setup
            and self.current_setup.data.ID != self.reserved_setup.data.ID
        ):
            current_setup_ID = self.reserved_setup.data.ID
        elif self.current_setup:
            current_setup_ID = self.current_setup.data.ID
        length = len(
            [
                state
                for state in self.production_states
                if state.data.ID == current_setup_ID
            ]
        )
        return length

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

    def update_full(self) -> bool:
        """
        Returns if the resource is full.

        Returns:
            bool: True if the resource is full or in setup, False otherwise.
        """
        self.full = (
            self.capacity_current_setup
            - (
                self.controller.num_running_processes
                + self.controller.reserved_requests_count
            )
        ) <= 0

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

    def get_location(self) -> List[float]:
        """
        Returns the location of the transport resource.

        Returns:
            List[float]: The location of the resource. Has to have length 2.
        """
        return self.data.location

    def get_input_queue_length(self) -> int:
        """
        Returns total number of items in all input_queues.

        Returns:
            int: Sum of items in the resources input-queues.
        """
        return sum([len(q.items) for q in self.input_queues])

    def get_output_queue_length(self) -> int:
        """
        Returns total number of items in all output_queues.

        Returns:
            int: Sum of items in the resources output-queues.
        """
        return sum([len(q.items) for q in self.output_queues])

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
        Activates the resource after a breakdwon.
        """
        if any(
            [
                state_instance.active_breakdown
                for state_instance in self.states
                if isinstance(state_instance, state.BreakDownState)
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

    def get_free_of_processes_in_preparation(self) -> Generator:
        """
        Returns a generator that yields when all processes in preparation are finished.

        Yields:
            Generator: The generator of the yield, which is yielded when all processes in preparation are finished.
        """
        running_processes = [
            state.process
            for state in self.production_states
            if (state.process and state.process.is_alive)
        ]
        yield events.AllOf(self.env, running_processes)

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

    def get_input_location(self) -> List[float]:
        """
        Returns the input location of the production resource.

        Returns:
            List[float]: The input location of the resource. Has to have length 2.
        """
        return self.data.input_location

    def get_output_location(self) -> List[float]:
        """
        Returns the output location of the production resource.

        Returns:
            List[float]: The output location of the resource. Has to have length 2.
        """
        return self.data.output_location

    def add_input_queues(self, input_queues: List[store.Queue]):
        self.input_queues.extend(input_queues)

    def add_output_queues(self, output_queues: List[store.Queue]):
        self.output_queues.extend(output_queues)

    def reserve_internal_input_queues(self):
        internal_queues = [
            q for q in self.input_queues if not isinstance(q, store.Store)
        ]
        for internal_queue in internal_queues:
            internal_queue.reserve()

    def adjust_pending_put_of_output_queues(self, batch_size: int = 1):
        internal_queues = [
            q for q in self.output_queues if not isinstance(q, store.Store)
        ]
        for output_queue in internal_queues:
            for i in range(batch_size):
                output_queue.reserve()


RESOURCE_UNION = Resource
""" Union Type for Resources. """

from prodsys.simulation import control, state
from prodsys.simulation.process import PROCESS_UNION
from prodsys.simulation.product import Locatable
