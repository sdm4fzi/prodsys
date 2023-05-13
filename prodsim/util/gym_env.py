from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import numpy as np
from simpy import events

import gymnasium as gym
from gymnasium import spaces
from prodsim import adapters, runner
from prodsim.simulation import control, sim, observer

sim.VERBOSE = 0

if TYPE_CHECKING:
    from prodsim.simulation import resources


class ProductionControlEnv(gym.Env):

    def __init__(self, adapter: adapters.Adapter, resource_id: str, render_mode=None):
        self.adapter = adapter
        self.resource_id = resource_id
        self.runner = runner.Runner(adapter=self.adapter)

        self.interrupt_simulation_event: events.Event = None
        self.resource_controller: control.Controller = None
        self.resource: resources.Resource = None
        self.observer: observer.ResourceObserver = None
        self.step_count = 0

        resource_data = [r for r in self.adapter.resource_data if r.ID == resource_id][0]
        queue = [q for q in self.adapter.queue_data if q.ID == resource_data.input_queues[0]][0]
        
        shape = (queue.capacity + resource_data.capacity, len(resource_data.process_ids))

        self.observation_space = spaces.Box(0, 1, shape=shape, dtype=int)

        self.action_space = spaces.Box(0, 1 , shape=(queue.capacity,), dtype=float)

        self.render_mode = render_mode

    def _get_obs(self):
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

    def _get_info(self):
        return {"infoo": 0}

    def reset(self, seed=None, options=None):
        """
        Reset env for new episode and run until first point of observation.
        """

        # TODO: check if necessary, maybe for deterministic agent
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
                                                  material_factory=self.runner.material_factory, 
                                                  resource=self.resource)

        self.runner.env.run_until(until=self.interrupt_simulation_event)
        # print("simulated until decision is needed")
        self.interrupt_simulation_event = events.Event(self.runner.env)
        # print(self.resource_controller.resource.data.ID, self.resource_controller.requests)

        observation = self._get_obs()
        info = self._get_info()

        if self.render_mode == "human":
            self.render()

        # print("return obs and info", observation, info)


        return observation, info

    def step(self, action):

        queue_index = np.argmax(action)
        print("action received: ", action)
        print("queue index: ", queue_index)
        print("queue before reshuffle", [r.material.material_data.ID for r in self.resource_controller.requests])
        if queue_index >= len(self.resource_controller.requests):
            queue_index = np.random.choice([i for i in range(len(self.resource_controller.requests))])
            to_process = self.resource_controller.requests.pop(queue_index)
            setup_sparse_reward = False
        else:
            to_process = self.resource_controller.requests.pop(queue_index)
            setup_sparse_reward = self.resource.current_process is None or to_process.process.process_data.ID == self.resource.current_process.process_data.ID

        self.resource_controller.requests.insert(0, to_process)
        print("queue after reshuffle", [r.material.material_data.ID for r in self.resource_controller.requests])

        self.runner.env.run_until(until=self.interrupt_simulation_event)
        self.step_count += 1
        self.interrupt_simulation_event = events.Event(self.runner.env)

        terminated = self.runner.env.now >= 300000
        reward = self.resource.input_queues[0].capacity - len(self.resource_controller.requests) if self.step_count % 10 == 0 else setup_sparse_reward  # Binary sparse rewards
        print("reward: ", reward)
        observation = self._get_obs()
        info = self._get_info()

        if self.render_mode == "human":
            self.render()

        # print("return obs and info and others", observation, info, terminated, reward)


        return observation, reward, terminated, False, info

    def render(self):
        if self.render_mode == "human":
            # self.runner.print_results()
            pass
        
