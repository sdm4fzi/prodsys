from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, List, Generator, Optional, Union

from pydantic import BaseModel, ConfigDict, Field
import random

import logging
logger = logging.getLogger(__name__)

from simpy.resources import resource
from simpy import events
from prodsys.simulation import sim, store
if TYPE_CHECKING:
    from prodsys.simulation import control, state
    from prodsys.simulation.process import PROCESS_UNION

from prodsys.models.resource_data import (
    RESOURCE_DATA_UNION,
    ProductionResourceData,
    TransportResourceData,
)
from prodsys.util import util

class Resource(BaseModel, ABC, resource.Resource):
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
        got_free (events.Event): The event that is triggered when the resource gets free of processes.
        active (events.Event): The event that is triggered when the resource is active.
        current_setup (PROCESS_UNION): The current setup.
        reserved_setup (PROCESS_UNION): The reserved setup.
    """
    env: sim.Environment
    data: RESOURCE_DATA_UNION
    processes: List[PROCESS_UNION]
    controller: control.Controller

    states: List[state.State] = Field(default_factory=list, init=False)
    production_states: List[state.State] = Field(default_factory=list, init=False)
    setup_states: List[state.SetupState] = Field(default_factory=list, init=False)

    got_free: events.Event = Field(default=None, init=False)
    active: events.Event = Field(default=None, init=False)
    current_setup: PROCESS_UNION = Field(default=None, init=False)
    reserved_setup: PROCESS_UNION = Field(default=None, init=False)

    model_config=ConfigDict(arbitrary_types_allowed=True, extra="allow")

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
            and self.current_setup.process_data.ID
            != self.reserved_setup.process_data.ID
        ):
            current_setup_ID = self.reserved_setup.process_data.ID
        elif self.current_setup:
            current_setup_ID = self.current_setup.process_data.ID
        length = len(
            [
                state
                for state in self.production_states
                if state.state_data.ID == current_setup_ID
            ]
        )
        return length

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

    @property
    def full(self) -> bool:
        """
        Returns if the resource is full.

        Returns:
            bool: True if the resource is full or in setup, False otherwise.
        """
        if self.in_setup:
            return True
        return (
            self.capacity_current_setup
            - (len(self.controller.running_processes) + self.controller.reserved_requests_count)
        ) <= 0

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
        self.got_free = events.Event(self.env)
        for actual_state in self.states + self.production_states + self.setup_states:
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
            if actual_state.state_data.ID == process.process_data.ID
        ]
        if not possible_states:
            raise ValueError(
                f"Process {process.process_data.ID} not found in resource {self.data.ID}"
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
            if actual_state.state_data.ID == process.process_data.ID
        ]
        if not possible_states:
            raise ValueError(
                f"Process {process.process_data.ID} not found in resource {self.data.ID}"
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
            if actual_state.state_data.ID == process.process_data.ID and (
                actual_state.process is None or not actual_state.process.is_alive
            ):
                return actual_state
        return None

    def get_location(self) -> List[float]:
        """
        Returns the location of the resource.

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

    def set_location(self, new_location: List[float]) -> None:
        """
        Sets the location of the resource.

        Args:
            new_location (List[float]): The new location of the resource. Has to have length 2.
        """
        self.data.location = new_location

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
        if any([state_instance.active_breakdown for state_instance in self.states if isinstance(state_instance, state.BreakDownState)]):
            logger.debug({"ID": self.data.ID, "sim_time": self.env.now, "resource": self.data.ID, "event": f"Breakdown still active that blocks activation of resource"})
            return
        self.active.succeed()

    def interrupt_states(self):
        """
        Interrupts the states of the resource.
        """
        logger.debug({"ID": self.data.ID, "sim_time": self.env.now, "resource": self.data.ID, "event": f"Start interrupting processes of resource"})
        if self.active.triggered:
            self.active = events.Event(self.env)
        for state_instance in self.setup_states + self.production_states:
            if state_instance.process and state_instance.process.is_alive and not state_instance.interrupted:
                state_instance.interrupt_process()
        logger.debug({"ID": self.data.ID, "sim_time": self.env.now, "resource": self.data.ID, "event": f"Interrupted processes of resource"})


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
        logger.debug({"ID": self.data.ID, "sim_time": self.env.now, "resource": self.data.ID, "event": f"Start waiting for free of setups"})
        yield events.AllOf(self.env, running_setups)
        logger.debug({"ID": self.data.ID, "sim_time": self.env.now, "resource": self.data.ID, "event": f"Finished waiting for free of setups"})

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
        logger.debug({"ID": self.data.ID, "sim_time": self.env.now, "resource": self.data.ID, "event": f"Start waiting for free of processes in preparation"})
        yield events.AllOf(self.env, running_processes)
        logger.debug({"ID": self.data.ID, "sim_time": self.env.now, "resource": self.data.ID, "event": f"Finished waiting for free of processes in preparation"})

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

        if setup_to_compare.process_data.ID == _process.process_data.ID:
            yield self.env.process(self.get_free_of_setups())
            yield self.env.process(util.trivial_process(self.env))
            return

        for input_state in self.setup_states:
            if (
                input_state.state_data.target_setup == _process.process_data.ID
                and input_state.state_data.origin_setup
                == setup_to_compare.process_data.ID
            ):
                self.reserve_setup(_process)
                yield self.env.process(self.get_free_of_setups())
                input_state.prepare_for_run()
                input_state.process = self.env.process(input_state.process_state())
                logger.debug({"ID": self.data.ID, "sim_time": self.env.now, "resource": self.data.ID, "process": _process.process_data.ID, "event": f"Start setup process"})
                yield input_state.process
                logger.debug({"ID": self.data.ID, "sim_time": self.env.now, "resource": self.data.ID, "process": _process.process_data.ID, "event": f"Finished setup process"})
                input_state.process = None
                self.current_setup = _process
                self.unreserve_setup()

        else:
            yield self.env.process(self.get_free_of_setups())
            yield self.env.process(util.trivial_process(self.env))


class ProductionResource(Resource):
    """
    A production resource to perform production processes. Has additionally to a Resource input and output queues and a fixed location.

    Args:
        env (sim.Environment): The simpy environment.
        data (ProductionResourceData): The resource data.
        processes (List[PROCESS_UNION]): The processes.
        controller (control.ProductionController): The controller.
        states (List[state.State]): The states of the resource for breakdowns.
        production_states (List[state.State]): The states of the resource for production.
        setup_states (List[state.SetupState]): The states of the resource for setups.
        got_free (events.Event): The event that is triggered when the resource gets free of processes.
        active (events.Event): The event that is triggered when the resource is active.
        current_setup (PROCESS_UNION): The current setup.
        reserved_setup (PROCESS_UNION): The reserved setup.
        input_queues (List[store.Queue]): The input queues.
        output_queues (List[store.Queue]): The output queues.


    """
    data: ProductionResourceData
    controller: control.ProductionController

    input_queues: List[store.Queue] = []
    output_queues: List[store.Queue] = []

    def add_input_queues(self, input_queues: List[store.Queue]):
        self.input_queues.extend(input_queues)

    def add_output_queues(self, output_queues: List[store.Queue]):
        self.output_queues.extend(output_queues)

    def reserve_input_queues(self):
        for input_queue in self.input_queues:
            input_queue.reserve()

    def unreserve_input_queues(self):
        for input_queue in self.input_queues:
            input_queue.unreseve()

class TransportResource(Resource):
    """
    A transport resource to perform transport processes. Can change its and the product's location during transport processes.

    Args:
        env (sim.Environment): The simpy environment.
        data (TransportResourceData): The resource data.
        processes (List[PROCESS_UNION]): The processes.
        controller (control.TransportController): The controller.
        states (List[state.State]): The states of the resource for breakdowns.
        production_states (List[state.State]): The states of the resource for production.
        setup_states (List[state.SetupState]): The states of the resource for setups.
        got_free (events.Event): The event that is triggered when the resource gets free of processes.
        active (events.Event): The event that is triggered when the resource is active.
        current_setup (PROCESS_UNION): The current setup.
        reserved_setup (PROCESS_UNION): The reserved setup.
    """
    data: TransportResourceData
    controller: control.TransportController


RESOURCE_UNION = Union[ProductionResource, TransportResource]
""" Union Type for Resources. """

from prodsys.simulation import control, state
from prodsys.simulation.process import PROCESS_UNION
