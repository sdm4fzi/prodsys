from __future__ import annotations

from functools import partial

import numpy as np
from simpy import events

import gymnasium as gym
from gymnasium import spaces
from prodsim import adapters, runner
from prodsim.simulation import control

from prodsim.simulation import sim
sim.VERBOSE = 0


class GridWorldEnv(gym.Env):

    def __init__(self, adapter: adapters.Adapter, resource_id: str, render_mode=None):
        self.adapter = adapter
        self.resource_id = resource_id
        self.runner = runner.Runner(adapter=self.adapter)

        self.interrupt_simulation_event: events.Event = None
        self.resource_controller: control.Controller = None

        self.observation_space = spaces.Dict(
            {
                "queue_length": spaces.Box(0, 100, shape=(1,), dtype=int),
            }
        )

        self.action_space = spaces.Discrete(4)

        # """
        # The following dictionary maps abstract actions from `self.action_space` to
        # the direction we will walk in if that action is taken.
        # I.e. 0 corresponds to "right", 1 to "up" etc.
        # """
        # self._action_to_direction = {
        #     0: np.array([1, 0]),
        #     1: np.array([0, 1]),
        #     2: np.array([-1, 0]),
        #     3: np.array([0, -1]),
        # }

        self.render_mode = render_mode

    def _get_obs(self):
        length = len(self.resource_controller.requests)
        if length > 100:
            length = 100
        return {"queue_length": len(self.resource_controller.requests)}

    # %%
    # We can also implement a similar method for the auxiliary information
    # that is returned by ``step`` and ``reset``. In our case, we would like
    # to provide the manhattan distance between the agent and the target:

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


        self.runner.env.run_until(until=self.interrupt_simulation_event)
        print("simulated until decision is needed")
        self.interrupt_simulation_event = events.Event(self.runner.env)
        print(self.resource_controller.resource.data.ID, self.resource_controller.requests)

        observation = self._get_obs()
        info = self._get_info()

        if self.render_mode == "human":
            self.render()

        print("return obs and info", observation, info)


        return observation, info

    # %%
    # Step
    # ~~~~
    #
    # The ``step`` method usually contains most of the logic of your
    # environment. It accepts an ``action``, computes the state of the
    # environment after applying that action and returns the 4-tuple
    # ``(observation, reward, done, info)``. Once the new state of the
    # environment has been computed, we can check whether it is a terminal
    # state and we set ``done`` accordingly. Since we are using sparse binary
    # rewards in ``GridWorldEnv``, computing ``reward`` is trivial once we
    # know ``done``. To gather ``observation`` and ``info``, we can again make
    # use of ``_get_obs`` and ``_get_info``:

    def step(self, action):
        print("action received: ", action)

        print("queue before reshuffle", [r.material.material_data.ID for r in self.resource_controller.requests])
        to_process = self.resource_controller.requests.pop(-1)
        self.resource_controller.requests.insert(0, to_process)
        print("queue after reshuffle", [r.material.material_data.ID for r in self.resource_controller.requests])

        # TODO: implement here logic for computing the new state of the environment
        self.runner.env.run_until(until=self.interrupt_simulation_event)
        self.interrupt_simulation_event = events.Event(self.resource_factory.env)

        terminated = self.runner.env.time >= 100
        reward = 20 - len(self.resource_controller.requests) if terminated else 1  # Binary sparse rewards
        observation = self._get_obs()
        info = self._get_info()

        if self.render_mode == "human":
            self.render()

        print("return obs and info and others", observation, info, terminated, reward)


        return observation, reward, terminated, False, info

    # %%
    # Rendering
    # ~~~~~~~~~
    #
    # Here, we are using PyGame for rendering. A similar approach to rendering
    # is used in many environments that are included with Gymnasium and you
    # can use it as a skeleton for your own environments:

    def render(self):
        if self.render_mode == "human":
            self.runner.print_results()
        
