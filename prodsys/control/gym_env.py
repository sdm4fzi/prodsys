from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, List, Optional, Tuple

import numpy as np
from simpy import events

import gymnasium as gym
from gymnasium import spaces
from prodsys import adapters, runner
from prodsys.simulation import control, sim, observer, router

sim.VERBOSE = 0

if TYPE_CHECKING:
    from prodsys.simulation import resources


class ProductionControlEnv(gym.Env):
    """
    Gym environment for controlling a controller of a resource wtih an agent. This environment is an example for implementing a control agent. Adaptions of observation space and reward are needed when aiming for performance.

    Args:
        adapter (adapters.ProductionSystemAdapter): The adapter.
        resource_id (str): The ID of the resource to control.

    Attributes:
        adapter (adapters.ProductionSystemAdapter): The adapter.
        resource_id (str): The ID of the resource to control.
        runner (runner.Runner): The runner of the adapter.
        interrupt_simulation_event (events.Event): The event to interrupt the simulation when an agent interaction is needed.
        resource_controller (control.Controller): The controller of the resource.
        resource (resources.Resource): The resource to control.
        observer (observer.ResourceObserver): The observer of the resource.
        step_count (int): The number of steps taken in the environment.
        observation_space (spaces.Box): The observation space of the environment.
        action_space (spaces.Box): The action space of the environment.
        render_mode (Optional[str], optional): The render mode of the environment. Defaults to None.
        reward (float): The reward of the environment.
    """

    def __init__(self, adapter: adapters.ProductionSystemAdapter, resource_id: str, render_mode=None):
        self.adapter = adapter
        self.resource_id = resource_id
        self.runner = runner.Runner(adapter=self.adapter)

        self.interrupt_simulation_event: events.Event = None
        self.resource_controller: control.Controller = None
        self.resource: resources.Resource = None
        self.observer: observer.ResourceObserver = None
        self.step_count: int = 0

        resource_data = [r for r in self.adapter.resource_data if r.ID == resource_id][0]
        queue = [q for q in self.adapter.queue_data if q.ID == resource_data.input_queues[0]][0]
        
        shape = (queue.capacity + resource_data.capacity, len(resource_data.process_ids))

        self.observation_space = spaces.Box(0, 1, shape=shape, dtype=int)

        self.action_space = spaces.Box(0, 1 , shape=(queue.capacity,), dtype=float)

        self.render_mode = render_mode
        self.reward = 0

    def _get_obs(self) -> np.ndarray:
        """
        Get observation of the environment.

        Returns:
            np.ndarray: The observation.
        """
        processes_observation = self.observer.observe_processes()
        encoded_processes = []
        processes = self.resource.data.process_ids

        for process_observation in processes_observation:
            encoded_process = [0 for _ in range(len(processes))]
            encoded_process[processes.index(process_observation.process)] = 1
            encoded_processes.append(encoded_process)

        encoded_process = [0 for _ in range(len(processes))]
        encoded_processes += [encoded_process] * (self.resource.data.capacity - len(processes_observation))

        queue_observations = self.observer.observe_input_queue()
        for queue_observation in queue_observations:
            encoded_process = [0 for _ in range(len(processes))]
            encoded_process[processes.index(queue_observation.process)] = 1
            encoded_processes.append(encoded_process)

        encoded_process = [0 for _ in range(len(processes))]
        queue_capacity = self.resource.input_queues[0].capacity
        
        encoded_processes += [encoded_process] * (queue_capacity - len(queue_observations))
        
        return np.array(encoded_processes)

    def _get_info(self) -> dict:
        """
        Get info of the environment.

        Returns:
            dict: The info.
        """
        return {"info": 0}

    def reset(self, seed=None, options=None):
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
        self.observer = observer.ResourceObserver(resource_factory=self.runner.resource_factory, 
                                                  product_factory=self.runner.product_factory, 
                                                  resource=self.resource)

        self.runner.env.run_until(until=self.interrupt_simulation_event)
        self.interrupt_simulation_event = events.Event(self.runner.env)

        observation = self._get_obs()
        info = self._get_info()

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
            queue_index = np.random.choice([i for i in range(len(self.resource_controller.requests))])
            to_process = self.resource_controller.requests.pop(queue_index)
            setup_sparse_reward = False
        else:
            to_process = self.resource_controller.requests.pop(queue_index)
            setup_sparse_reward = self.resource.current_setup is None or to_process.process.process_data.ID == self.resource.current_setup.process_data.ID

        self.resource_controller.requests.insert(0, to_process)

        self.runner.env.run_until(until=self.interrupt_simulation_event)
        self.step_count += 1
        self.interrupt_simulation_event = events.Event(self.runner.env)

        terminated = self.runner.env.now >= 300000
        reward = self.resource.input_queues[0].capacity - len(self.resource_controller.requests) + setup_sparse_reward if self.step_count % 10 == 0 else setup_sparse_reward  # Binary sparse rewards
        self.reward = reward
        observation = self._get_obs()
        info = self._get_info()

        if self.render_mode == "human":
            self.render()

        return observation, reward, terminated, False, info

    def render(self):
        """
        Render the environment.
        """
        if self.render_mode == "human":
            pass


class ProductionRoutingEnv(gym.Env):
    """
    Gym environment for controlling a router of a product type in a production system with an agent. Serves, at least for now, more as an example to use a routing agent...

    Args:
        adapter (adapters.ProductionSystemAdapter): The adapter for the production system.
        render_mode (str, optional): The render mode. Defaults to None.

    Attributes:
        adapter (adapters.ProductionSystemAdapter): The adapter for the production system.
        runner (runner.Runner): The runner for the production system.
        router (router.Router): The router of the product type.
        possible_resources (List[resources.Resource]): The possible resources for the router.
        chosen_resource (Optional[resources.Resource]): The chosen resource for the router.
        interrupt_simulation_event (events.Event): The event for interrupting the simulation.
        observers (List[observer.ResourceObserver]): The observers for the resources.
        step_count (int): The step count of the environment.
        observation_space (gym.spaces.Box): The observation space of the environment.
        action_space (gym.spaces.Box): The action space of the environment.
        render_mode (str): The render mode of the environment.
        reward (float): The reward of the environment.
    """

    def __init__(self, adapter: adapters.ProductionSystemAdapter, render_mode=None):
        self.adapter = adapter
        self.runner: runner.Runner = runner.Runner(adapter=self.adapter)
        
        self.router: router.Router = None
        self.possible_resources: List[resources.Resource] = []
        self.chosen_resource: Optional[resources.Resource] = None

        self.interrupt_simulation_event: events.Event = None
        self.observers: List[observer.ResourceObserver] = []
        self.step_count = 0
        
        shape = (len(self.adapter.resource_data),)

        self.observation_space = spaces.Box(0, 1, shape=shape, dtype=float)

        self.action_space = spaces.Box(0, 1 , shape=shape, dtype=float)

        self.render_mode = render_mode
        self.reward = 0

    def _get_obs(self) -> np.ndarray:
        """
        Get observation of the environment.

        Returns:
            np.ndarray: The observation.
        """
        available_resources = []
        for obs in self.observers:
            resource_available_status = obs.observe_resource_available()
            available_resources.append(resource_available_status.available)

        return np.array(available_resources)

    def _get_info(self) -> dict:
        """
        Get info of the environment.

        Returns:
            dict: The info.
        """
        return {"info": 0}

    def reset(self, seed=None, options=None):
        """
        Reset env for new episode and run until first point of observation.

        Args:   
            seed (int, optional): The seed for the environment. Defaults to None.
            options (dict, optional): The options for the environment. Defaults to None.
        """

        super().reset(seed=seed)

        self.runner.initialize_simulation()
        self.interrupt_simulation_event = events.Event(self.runner.env)
        agent_routing_heuristic = partial(router.agent_routing_heuristic, self)
        self.router = router.SimpleRouter(self.runner.resource_factory, self.runner.sink_factory, agent_routing_heuristic)  
        
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

        observation = self._get_obs()
        info = self._get_info()

        if self.render_mode == "human":
            self.render()

        return observation, info
    
    def load_possible_resources(self, resources: List[resources.Resource]):
        """
        Load possible resources for the router.

        Args:
            resources (List[resources.Resource]): The possible resources.
        """
        self.possible_resources = resources

    def get_chosen_resource(self) -> resources.Resource:
        """
        Get the chosen resource for the router.

        Returns:
            resources.Resource: The chosen resource.
        """
        return self.chosen_resource

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, dict]:
        """
        Perform action in the environment.

        Args:
            action (np.ndarray): The output of the agent based on the last observation.

        Returns:
            Tuple[np.ndarray, float, bool, dict]: The observation, reward, termination signal, and info.
        """

        resource = np.argmax(action)

        self.chosen_resource = self.runner.resource_factory.resources[resource]
        if not self.chosen_resource.data.ID in [r.data.ID for r in self.possible_resources]:
            sparse_reward = 0
            self.chosen_resource = self.possible_resources.pop()
            self.possible_resources = []
        else:
            sparse_reward = 1
            self.possible_resources = []

        self.runner.env.run_until(until=self.interrupt_simulation_event)
        self.step_count += 1
        self.interrupt_simulation_event = events.Event(self.runner.env)

        terminated = self.runner.env.now >= 300000
        queue_capacity = sum(queue.capacity for queue in self.adapter.queue_data if queue.ID != "SinkQueue")
        resource_capacity = sum(resource.capacity for resource in self.adapter.resource_data)
        wip = len(self.runner.product_factory.products)
        reward = (queue_capacity + resource_capacity) / wip * 100 + sparse_reward if self.step_count % 10 == 0 else sparse_reward  # Binary sparse rewards
        self.reward = reward
        observation = self._get_obs()
        info = self._get_info()

        if self.render_mode == "human":
            self.render()

        return observation, reward, terminated, False, info

    def render(self):
        """
        Render the environment.
        """
        if self.render_mode == "human":
            pass
        
