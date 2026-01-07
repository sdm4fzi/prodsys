from __future__ import annotations

import os
import time

from stable_baselines3 import PPO
from stable_baselines3.common.logger import configure
from stable_baselines3.common.callbacks import BaseCallback

import numpy as np
from gymnasium import spaces

from prodsys.adapters import ProductionSystemData
from prodsys.control import routing_control_env


class RoutingControlEnv(routing_control_env.AbstractRoutingControlEnv):
    def get_observation(self) -> np.ndarray:
        """
        Function that utilizes the ResourceObserver of the environment class to get an array of observations concerning the availability of resources.

        Returns:
            np.ndarray: The observation.
        """
        available_resources = []
        for obs in self.observers:
            resource_available_status = obs.observe_resource_available()
            available_resources.append(resource_available_status.available)

        return np.array(available_resources)

    def get_info(self) -> dict:
        return {"info": 0}

    def get_termination_condition(self) -> bool:
        return self.runner.env.now >= 300000

    def get_reward(self, invalid_action: bool = False) -> float:
        if invalid_action:
            reward = -1
        else:
            reward = 1

        if self.step_count % 10 == 0:
            queue_capacity = sum(
                queue.capacity
                for queue in self.adapter.port_data
                if queue.ID != "SinkQueue"
            )
            resource_capacity = sum(
                resource.capacity for resource in self.adapter.resource_data
            )
            wip = len(self.runner.product_factory.products)
            reward += (queue_capacity + resource_capacity) / wip * 100

        return reward


class TensorboardCallback(BaseCallback):
    """
    Custom callback for plotting additional values in tensorboard.
    """

    def __init__(self, verbose=0):
        super(TensorboardCallback, self).__init__(verbose)

    def _on_step(self) -> bool:
        self.logger.record("reward", self.training_env.get_attr("reward")[0])

        return True


if __name__ == "__main__":
    adapter_object = ProductionSystemData.read(
        "examples/control/control_example_data/control_configuration.json"
    )

    num_of_resources = len(adapter_object.resource_data)

    observation_space = spaces.Box(0, 1, shape=(num_of_resources,), dtype=float)
    action_space = spaces.Box(0, 1, shape=(num_of_resources,), dtype=float)

    env = RoutingControlEnv(
        adapter_object,
        observation_space=observation_space,
        action_space=action_space,
        render_mode="human",
    )

    tmp_path = os.path.join(
        os.getcwd(), "tensorboard_log", "routing", time.strftime("%Y%m%d-%H%M%S")
    )
    new_logger = configure(tmp_path, ["stdout", "csv", "tensorboard"])

    model = PPO(env=env, policy="MlpPolicy", verbose=1)
    model.set_logger(new_logger)
    model.learn(total_timesteps=1000000, callback=TensorboardCallback())

    # Start Tensorboard with: tensorboard --logdir tensorboard_log\routing
