from __future__ import annotations

from functools import partial

import numpy as np
from simpy import events

import gymnasium as gym
from gymnasium import spaces
from prodsim import adapters, runner
from prodsim.simulation import control, sim, logger

sim.VERBOSE = 0


class ProductionControlEnv(gym.Env):

    def __init__(self, adapter: adapters.Adapter, resource_id: str, render_mode=None):
        self.adapter = adapter
        self.resource_id = resource_id
        self.runner = runner.Runner(adapter=self.adapter)

        self.interrupt_simulation_event: events.Event = None
        self.resource_controller: control.Controller = None
        self.observation_logger: logger.ObservationLogger = None

        self.observation_space = spaces.Dict(
            {
                "queue_length": spaces.Box(0, 100, shape=(1,), dtype=int),
            }
        )

        self.action_space = spaces.Discrete(4)

        self.render_mode = render_mode

    def _get_obs(self):
        length = len(self.resource_controller.requests)
        if length > 100:
            length = 100
        return {"queue_length": len(self.resource_controller.requests)}

    def _get_info(self):
        return {"distance": 0.69696}

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
        control_policy = partial(control.agent_control_policy, self)
        self.resource_controller.control_policy = control_policy
        self.observation_logger = logger.ObservationLogger()
        self.observation_logger.observe_resources(self.resource_controller.resource)

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
        # print("action received: ", action)

        # print("queue before reshuffle", [r.material.material_data.ID for r in self.resource_controller.requests])
        to_process = self.resource_controller.requests.pop(-1)
        self.resource_controller.requests.insert(0, to_process)
        # print("queue after reshuffle", [r.material.material_data.ID for r in self.resource_controller.requests])

        self.runner.env.run_until(until=self.interrupt_simulation_event)
        self.interrupt_simulation_event = events.Event(self.runner.env)

        terminated = self.runner.env.now >= 300000
        reward = 20 - len(self.resource_controller.requests) if terminated else 1  # Binary sparse rewards
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
        
