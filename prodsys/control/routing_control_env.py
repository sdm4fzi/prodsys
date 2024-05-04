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


class AbstractRoutingControlEnv(gym.Env, ABC):
    """
    Abstract Gym environment for controlling a router of a production system with an reinforcement learning agent.
    This class defines the methods that need to be implemented in order to use a Reinforcement learning agent for production routing control.

    Args:
        adapter (adapters.ProductionSystemAdapter): The adapter.
        observation_space (Optional[spaces.Space], optional): The observation space of the environment.
        action_space (Optional[spaces.Space], optional): The action space of the environment.
        render_mode (Optional[str], optional): The render mode of the environment. Defaults to None.

    Attributes:
        adapter (adapters.ProductionSystemAdapter): The adapter.
        observation_space (Optional[spaces.Space], optional): The observation space of the environment.
        action_space (Optional[spaces.Space], optional): The action space of the environment.
        render_mode (Optional[str], optional): The render mode of the environment. Defaults to None.
        runner (runner.Runner): The runner of the adapter.
        router: (router.Router): The router of the adapter.
        possible_resources (List[resources.Resource]): The possible resources to route to.
        interrupt_simulation_event (events.Event): The event to interrupt the simulation when an agent interaction is needed.
        observers (List[observer.ResourceObserver]): The observers for the reosurces to route to.
        step_count (int): The number of steps taken in the environment.
        reward (float): The reward of the environment.
    """

    def __init__(
        self,
        adapter: adapters.ProductionSystemAdapter,
        observation_space: Optional[spaces.Space] = None,
        action_space: Optional[spaces.Space] = None,
        render_mode: Optional[str]=None,
    ):
        self.adapter = adapter
        self.observation_space = observation_space
        self.action_space = action_space
        self.render_mode = render_mode

        self.runner = runner.Runner(adapter=self.adapter)

        self.router: router.Router = None
        self.possible_requests: List[request.Request] = []
        self.chosen_resource: Optional[resources.Resource] = None
        self.interrupt_simulation_event: events.Event = None
        self.observers: List[observer.ResourceObserver] = []
        self.step_count = 0
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
    def get_reward(self, invalid_action:bool=False) -> float:
        """
        Get reward of the environment.

        Args:
            invalid_action (bool, optional): Whether the last action was invalid. Defaults to False.

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
        self.chose_resource_event = events.Event(self.runner.env)
        agent_routing_heuristic = partial(router.agent_routing_heuristic, self)
        self.router = router.Router(self.runner.resource_factory, self.runner.sink_factory, agent_routing_heuristic)  
        
        sources = self.runner.source_factory.sources
        for source in sources:
            source.router = self.router
        
        self.observers = []
        for resource in self.runner.resource_factory.resources:
            obs = observer.ResourceObserver(resource_factory=self.runner.resource_factory, 
                                                  product_factory=self.runner.product_factory, 
                                                  resource=resource)
            self.observers.append(obs)

        self.runner.env.run_until(until=self.interrupt_simulation_event)
        self.interrupt_simulation_event = events.Event(self.runner.env)

        observation = self.get_observation()
        info = self.get_info()

        if self.render_mode == "human":
            self.render()

        return observation, info
    
    def set_possible_requests(self, requests: List[request.Request]):
        """
        Set possible requests for the RL agent environment.

        Args:
            resources (List[request.Request]): The possible requests to route.
        """
        self.possible_requests = requests

    def get_chosen_resource(self) -> resources.Resource:
        """
        Get the chosen resource of the RL agent for the router.

        Returns:
            resources.Resource: The chosen resource.
        """
        return self.chosen_resource

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, dict]:
        """
        Take a step in the environment.

        Args:
            action (np.ndarray): The output of the agent for actions.

        Returns:
            Tuple[np.ndarray, float, bool, dict]: The observation, reward, done, and info.
        """
        # TODO: implement action masking here!
        resource_index = np.argmax(action)

        self.chosen_resource = self.runner.resource_factory.resources[resource_index]
        if not self.chosen_resource.data.ID in [r.resource.data.ID for r in self.possible_requests]:
            invalid_action = True
            self.chosen_resource = np.random.choice(self.possible_requests)
        else:
            invalid_action = False

        self.possible_requests.sort(key=lambda r: r.resource.data.ID == self.chosen_resource.data.ID, reverse=True)

        self.runner.env.run_until(until=self.interrupt_simulation_event)
        self.step_count += 1
        self.interrupt_simulation_event = events.Event(self.runner.env)
        
        terminated = self.get_termination_condition()
        self.reward = self.get_reward(invalid_action)
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
