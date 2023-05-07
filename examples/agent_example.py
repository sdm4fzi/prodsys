from __future__ import annotations

import prodsim
from prodsim.util import gym_env

if __name__ == '__main__':

    adapter_object = prodsim.adapters.JsonAdapter()

    adapter_object.read_data('examples/basic_example/example_configuration.json')
    env = gym_env.ProductionControlEnv(adapter_object, "R2", render_mode="human")
    ob, info = env.reset()

    for _ in range(20):
        action = env.action_space.sample()
        ob, reward, terminated, truncated, info = env.step(action)
        print(f"action: {action}, reward: {reward}, terminated: {terminated}, truncated: {truncated}, time: {env.resource_controller.env.now}")
        if terminated or truncated:
            observation, info = env.reset()
        print("__________")
        import json
        with open("example_log.json", "w") as f:
            json.dump(env.observation_logger.resource_state_data, f)