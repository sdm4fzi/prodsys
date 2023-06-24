from __future__ import annotations


import os
import time

from stable_baselines3 import PPO
from stable_baselines3.common.logger import configure

from stable_baselines3.common.callbacks import BaseCallback

import numpy as np

from gymnasium import spaces

import prodsys
from prodsys.control import control_gym_env
from prodsys.simulation import request


class ProductionControlEnv(control_gym_env.AbstractControlEnv):
    def get_observation(self) -> np.ndarray:
        """
        Function that utilizes the ResourceObserver of the environment class to get an array of observations of processes performed by the resource and in the queue of the resource. The observatino has a dimension CxP, where c is the capacity of resource and queue and P the number of processes.

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
        encoded_processes += [encoded_process] * (
            self.resource.data.capacity - len(processes_observation)
        )

        queue_observations = self.observer.observe_input_queue()
        for queue_observation in queue_observations:
            encoded_process = [0 for _ in range(len(processes))]
            encoded_process[processes.index(queue_observation.process)] = 1
            encoded_processes.append(encoded_process)

        encoded_process = [0 for _ in range(len(processes))]
        queue_capacity = self.resource.input_queues[0].capacity

        encoded_processes += [encoded_process] * (
            queue_capacity - len(queue_observations)
        )

        return np.array(encoded_processes)

    def get_info(self) -> dict:
        return {"info": 0}
    

    def get_termination_condition(self) -> bool:
        return self.runner.env.now >= 100000
    
    def get_reward(self, processed_request: request.Request, invalid_action: bool = False) -> float:
        if invalid_action:
            return -1
        else:
            setup_sparse_reward = (
                self.resource.current_setup is None
                or processed_request.process.process_data.ID
                == self.resource.current_setup.process_data.ID
            )
            if self.step_count % 10 == 0:
                return self.resource.input_queues[0].capacity - len(self.resource_controller.requests) + setup_sparse_reward 
            else:
                return setup_sparse_reward




class TensorboardCallback(BaseCallback):
    """
    Custom callback for plotting additional values in tensorboard.
    """

    def __init__(self, verbose=0):
        super(TensorboardCallback, self).__init__(verbose)

    def _on_step(self) -> bool:                
        self.logger.record('reward', self.training_env.get_attr('reward')[0])
        self.logger.record('step_count', self.training_env.get_attr('step_count')[0])
        self.logger.record('time', self.training_env.get_attr('runner')[0].env.now)

        return True

if __name__ == '__main__':
    resource_id = "R2"
    adapter = prodsys.adapters.JsonProductionSystemAdapter()
    adapter.read_data('examples/control_example/control_configuration.json')
    resource_data = [r for r in adapter.resource_data if r.ID == resource_id][0]
    queue = [q for q in adapter.queue_data if q.ID == resource_data.input_queues[0]][0]
    shape = (queue.capacity + resource_data.capacity, len(resource_data.process_ids))
    observation_space = spaces.Box(0, 1, shape=shape, dtype=int)
    action_space = spaces.Box(0, 1, shape=(queue.capacity,), dtype=float)
    env = ProductionControlEnv(adapter, "R2", observation_space=observation_space, action_space=action_space, render_mode="human")
    
    tmp_path = os.getcwd() + "/tensorboard_log/sb3_log" + time.strftime("%Y%m%d-%H%M%S")
    new_logger = configure(tmp_path, ["stdout", "csv", "tensorboard"])

    model = PPO(env=env, policy='MlpPolicy', verbose=1)
    model.set_logger(new_logger)
    model.learn(total_timesteps=1000000, callback=TensorboardCallback())

    # Start Tensorboard with: tensorboard --logdir tensorboard_log