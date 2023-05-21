from __future__ import annotations

import prodsys
from prodsys.util import gym_env

from stable_baselines3 import PPO
from stable_baselines3.common.logger import configure

from stable_baselines3.common.callbacks import BaseCallback


class TensorboardCallback(BaseCallback):
    """
    Custom callback for plotting additional values in tensorboard.
    """

    def __init__(self, verbose=0):
        super(TensorboardCallback, self).__init__(verbose)

    def _on_step(self) -> bool:                
        self.logger.record('reward', self.training_env.get_attr('reward')[0])

        return True

if __name__ == '__main__':

    

    adapter_object = prodsys.adapters.JsonProductionSystemAdapter()
    adapter_object.read_data('examples/basic_example/example_configuration.json')
    env = gym_env.ProductionRoutingEnv(adapter_object, render_mode="human")

    tmp_path = "/tmp/sb3_log2/"
    new_logger = configure(tmp_path, ["stdout", "csv", "tensorboard"])

    model = PPO(env=env, policy='MlpPolicy', verbose=1)
    model.set_logger(new_logger)
    model.learn(total_timesteps=1000000, callback=TensorboardCallback())

    # Start Tensorboard with: tensorboard --logdir /tmp/sb3_log/