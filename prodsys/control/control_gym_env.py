from __future__ import annotations

from abc import ABC, abstractmethod

from functools import partial
from typing import TYPE_CHECKING, List, Optional, Tuple, Callable, Union

import numpy as np
from simpy import events

import gymnasium as gym
from gymnasium import spaces
from prodsys import adapters, runner
from prodsys.simulation import control, sim, observer, router

sim.VERBOSE = 0

if TYPE_CHECKING:
    from prodsys.simulation import resources, request


class AbstractControlEnv(gym.Env, ABC):
    """
    Abstract Gym environment for controlling a controller of a resource wtih an agent.
    This class defines the methods that need to be implemented in order to use a Reinforcement learning agent for production control.

    Args:
        adapter (adapters.ProductionSystemAdapter): The adapter.
        resource_id (str): The ID of the resource to control.
        observation_space (Optional[spaces.Space], optional): The observation space of the environment.
        action_space (Optional[spaces.Space], optional): The action space of the environment.
        render_mode (Optional[str], optional): The render mode of the environment. Defaults to None.

    Attributes:
        adapter (adapters.ProductionSystemAdapter): The adapter.
        resource_id (str): The ID of the resource to control.
        observation_space (Optional[spaces.Space], optional): The observation space of the environment.
        action_space (Optional[spaces.Space], optional): The action space of the environment.
        render_mode (Optional[str], optional): The render mode of the environment. Defaults to None.
        runner (runner.Runner): The runner of the adapter.
        interrupt_simulation_event (events.Event): The event to interrupt the simulation when an agent interaction is needed.
        resource_controller (control.Controller): The controller of the resource.
        resource (resources.Resource): The resource to control.
        observer (observer.ResourceObserver): The observer of the resource.
        step_count (int): The number of steps taken in the environment.
        reward (float): The reward of the environment.
    """

    def __init__(
        self,
        adapter: adapters.ProductionSystemAdapter,
        resource_id: str,
        observation_space: Optional[spaces.Space] = None,
        action_space: Optional[spaces.Space] = None,
        render_mode: Optional[str]=None,
    ):
        self.adapter = adapter
        self.resource_id = resource_id
        self.observation_space = observation_space
        self.action_space = action_space
        self.render_mode = render_mode

        self.runner = runner.Runner(adapter=self.adapter)

        self.interrupt_simulation_event: events.Event = None
        self.resource_controller: control.Controller = None
        self.resource: Union[resources.ProductionResource, resources.TransportResource] = None
        self.observer: observer.ResourceObserver = None
        self.step_count: int = 0
        self.reward = 0

    @abstractmethod
    def get_observation(self) -> np.ndarray:
        """
        Get observation of the environment.

        Returns:
            np.ndarray: The observation.
        """
        pass

    @abstractmethod
    def get_info(self) -> dict:
        """
        Get info of the environment.

        Returns:
            dict: The info.
        """
        pass

    @abstractmethod
    def get_reward(self, processed_request: request.Request, invalid_action:bool=False) -> float:
        """
        Get reward of the environment.

        Returns:
            float: The reward.
        """
        pass

    @abstractmethod
    def get_termination_condition(self) -> bool:
        """
        Get termination condition of the environment.

        Returns:
            bool: The termination condition.
        """
        pass

    def reset(self, seed=None):
        """
        Reset env for new episode and run until first point of observation.

        Args:
            seed (Optional[int], optional): The seed for the environment. Defaults to None.
            options (Optional[dict], optional): The options for the environment. Defaults to None.
        """
        super().reset(seed=seed)

        self.runner.initialize_simulation()
        self.interrupt_simulation_event = events.Event(self.runner.env)
        self.resource_controller = self.runner.resource_factory.get_resource(
            self.resource_id
        ).get_controller()
        self.resource = self.resource_controller.resource
        control_policy = partial(control.agent_control_policy, self)
        self.resource_controller.control_policy = control_policy
        self.observer = observer.ResourceObserver(
            resource_factory=self.runner.resource_factory,
            product_factory=self.runner.product_factory,
            resource=self.resource,
        )

        self.runner.env.run_until(until=self.interrupt_simulation_event)
        queue_situation = self.resource.input_queues[0].items[0]
        print("Reset done", queue_situation)
        self.interrupt_simulation_event = events.Event(self.runner.env)

        observation = self.get_observation()
        info = self.get_info()

        if self.render_mode == "human":
            self.render()

        return observation, info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, dict]:
        """
        Take a step in the environment.

        Args:
            action (np.ndarray): The output of the agent for actions.

        Returns:
            Tuple[np.ndarray, float, bool, dict]: The observation, reward, done, and info.
        """
        queue_index = np.argmax(action)
        if queue_index >= len(self.resource_controller.requests):
            queue_index = np.random.choice(
                [i for i in range(len(self.resource_controller.requests))]
            )
            to_process = self.resource_controller.requests.pop(queue_index)
            invalid_action = True
        else:
            to_process = self.resource_controller.requests.pop(queue_index)
            invalid_action = False

        self.resource_controller.requests.insert(0, to_process)

        self.runner.env.run_until(until=self.interrupt_simulation_event)
        self.step_count += 1
        self.interrupt_simulation_event = events.Event(self.runner.env)

        terminated = self.get_termination_condition()
        self.reward = self.get_reward(to_process, invalid_action)
        observation = self.get_observation()
        info = self.get_info()

        if self.render_mode == "human":
            self.render()

        return observation, self.reward, terminated, False, info
    
    def render(self):
        """
        Render the environment.
        """
        if self.render_mode == "human":
            pass
            
    def set_observation_space(self, observation_space: spaces.Space):
        """
        Set the observation space of the environment.

        Args:
            observation_space (spaces.Space): The observation space of the environment.
        """
        self.observation_space = observation_space

    def set_action_space(self, action_space: spaces.Space):
        """
        Set the action space of the environment.

        Args:
            action_space (spaces.Space): The action space of the environment.
        """
        self.action_space = action_space

    def set_binary_box_observation_space_from_shape(self, shape: Tuple[int, ...]):
        """
        Set the observation space of the environment to a binary box space.

        Args:
            shape (Tuple[int, ...]): The shape of the observation space.
        """
        self.observation_space = spaces.Box(0, 1, shape=shape, dtype=int)


    def set_binary_box_action_space_from_shape(self, shape: Tuple[int, ...]):
        """
        Set the action space of the environment to a binary box space.

        Args:
            shape (Tuple[int, ...]): The shape of the action space.
        """
        self.action_space = spaces.Box(0, 1, shape=shape, dtype=float)


class FunctionalControlEnv(AbstractControlEnv):
    """
    Gym environment for controlling a controller of a resource wtih an agent. This environment allows to pass function for getting observation, info, reward, and termination condition, which makes it easy to use by exchanging single functions.
    
    Args:
        adapter (adapters.ProductionSystemAdapter): The adapter.
        resource_id (str): The ID of the resource to control.
        observation_space (Optional[spaces.Space], optional): The observation space of the environment.
        action_space (Optional[spaces.Space], optional): The action space of the environment.
        render_mode (Optional[str], optional): The render mode of the environment. Defaults to None.

    Attributes:
        adapter (adapters.ProductionSystemAdapter): The adapter.
        resource_id (str): The ID of the resource to control.
        observation_space (Optional[spaces.Space], optional): The observation space of the environment.
        action_space (Optional[spaces.Space], optional): The action space of the environment.
        render_mode (Optional[str], optional): The render mode of the environment. Defaults to None.
        runner (runner.Runner): The runner of the adapter.
        interrupt_simulation_event (events.Event): The event to interrupt the simulation when an agent interaction is needed.
        resource_controller (control.Controller): The controller of the resource.
        resource (resources.Resource): The resource to control.
        observer (observer.ResourceObserver): The observer of the resource.
        step_count (int): The number of steps taken in the environment.
        reward (float): The reward of the environment.
        _get_observation (Optional[Callable[[observer.ResourceObserver], np.ndarray]]): The function for getting the observation.
        _get_info (Optional[Callable[[observer.ResourceObserver], dict]]): The function for getting the info.
        _get_reward (Optional[Callable[[observer.ResourceObserver, request.Request, Optional[bool]], float]]): The function for getting the reward.
        _get_termination_condition (Optional[Callable[[observer.ResourceObserver], bool]]): The function for getting the termination condition.
    """

    def __init__(
        self,
        adapter: adapters.ProductionSystemAdapter,
        resource_id: str,
        observation_space: Optional[spaces.Space] = None,
        action_space: Optional[spaces.Space] = None,
        render_mode: Optional[str]=None,
    ):
        super().__init__(adapter, resource_id, observation_space, action_space, render_mode)
        self._get_observation: Optional[Callable[[observer.ResourceObserver], np.ndarray]] = None
        self._get_info: Optional[Callable[[observer.ResourceObserver], dict]] = None
        self._get_reward: Optional[Callable[[observer.ResourceObserver, request.Request, Optional[bool]], float]] = None
        self._get_termination_condition: Optional[Callable[[observer.ResourceObserver], bool]] = None

    def get_observation(self) -> np.ndarray:
        """
        Get observation of the environment.

        Returns:
            np.ndarray: The observation.
        """
        return self._get_observation(self.observer)
    
    def get_info(self) -> dict:
        """
        Get info of the environment.

        Returns:
            dict: The info.
        """
        return self._get_info(self.observer)
    
    def get_reward(self, processed_request: request.Request, invalid_action:bool=False) -> float:
        """
        Get reward of the environment.

        Returns:
            float: The reward.
        """
        return self._get_reward(self.observer, processed_request, invalid_action)
    
    def get_termination_condition(self) -> bool:
        """
        Get termination condition of the environment.

        Returns:
            bool: The termination condition.
        """
        return self._get_termination_condition(self.observer)
    
    def set_observation_function(self, function: Callable[[observer.ResourceObserver], np.ndarray]):
        """
        Set the function for getting the observation.

        Args:
            function (Callable[[observer.ResourceObserver], np.ndarray]): The function for getting the observation.
        """
        self._get_observation = function

    def set_info_function(self, function: Callable[[observer.ResourceObserver], dict]):
        """
        Set the function for getting the info.

        Args:
            function (Callable[[observer.ResourceObserver], dict]): The function for getting the info.
        """
        self._get_info = function

    def set_reward_function(self, function: Callable[[observer.ResourceObserver, request.Request, Optional[bool]], float]):
        """
        Set the function for getting the reward.

        Args:
            function (Callable[[observer.ResourceObserver, Optional[bool]], float]): The function for getting the reward.
        """
        self._get_reward = function
