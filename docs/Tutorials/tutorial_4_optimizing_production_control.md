# Optimizing production control

This tutorial will guide you through the optimization functionalities of `prodsys` to optimize the production control in a production system. With the `prodsys.control` package, we can utilize reinforcement learning, a kind of machine learning, for this task. All algorithms can be conviently used with the `prodsys.models` API.

For this example, we will use again a production system which we will load from a json-file (control_configuration.json), which can be found in the examples folder of [prodsys' github page](https://github.com/sdm4fzi/prodsys/tree/main/examples/tutorials). It is the same example as in tutorial 2, but with lower arrival rates. Download it and store it in the same folder as this notebook. Load the configuration and run a simulation with the following commands:

Let's start at first by loading our production system:

```python

import prodsys
from prodsys.simulation import sim
sim.VERBOSE = 0

production_system = prodsys.adapters.ProductionSystemData()
production_system.read_data('control_configuration.json')

runner = prodsys.runner.Runner(adapter=production_system)
runner.initialize_simulation()
runner.run(2880)
runner.print_results()
```

When reviewing the performance, we see that resource R2 has the highest productivity. In order to reduce WIP and improve overall performance, we want to optimize the production control concerning R2 with Reinforcement Learning. `prodsys.control` provides a convenient API to do so, by defining interfaces for training environments for RL agents for production control task. So far, the following elementary control tasks are considered:

- **Sequencing**: The agent has to decide for a resource which product to process next from a list of available products.
- **Routing**: The agent determines for a product which resource it processes next, given a list of possible resources to perform this process.

In this tutorial, we will focus on the sequencing task. The routing task is similar and can be used analogously. Note that future versions of `prodsys.control` will provide more control tasks (e.g. such as product release control) and that it is also possible to define custom control tasks that are a combination of the existing ones.

## The training environment API

When utilizing reinforcement learning for production control, we need to define a training environment for the RL agent. This environment is responsible for providing the agent with the current state of the production system and for executing the agent's actions. The environment is also responsible for providing the agent with a reward for each action.
The [gymnasium]("https://gymnasium.farama.org/) package is used as a basis for these environments to be compatible with most RL-frameworks available. For more detailed information on the gym-environment API, please read their documentation. Here, we will use [stable-baselines3]("https://stable-baselines3.readthedocs.io/en/master/") as RL-framework. The environments provided by `prodsys.control` are implemented as abstract base classes, specifying the methods that need to be implemented by the user for soving the associated control tasks. To realize a control environment, we need to implement a class that inherits from the abstract base classes and implements it's abstract methods:

```python

from gymnasium import spaces
import numpy as np
import prodsys
from prodsys.simulation import request
from prodsys.control import sequencing_control_env

class ExampleControlEnv(sequencing_control_env.AbstractSequencingControlEnv):
    def get_observation(self) -> np.ndarray:
        # Implement here function that returns the observation that fits to the observation space of the class instances.
        pass

    def get_info(self) -> dict:
        # Implement here function that returns a dictionary with information about the environment.
        pass

    def get_termination_condition(self) -> bool:
        # Implement here function that returns True if the simulation should be terminated, i.e. an episode ends.
        pass

    def get_reward(self, processed_request: request.Request, invalid_action: bool = False) -> float:
        # Implement here function that returns the reward for the current step.
        pass

```

So, only 4 functions have to implemented to start training an RL-agent. These functions define the most critical aspects when training an RL-agent, which makes these environments especially easy to experiment with different RL-agent setups and compare them. Simulation interactions are handled by the environment, so that the user can focus on the RL-agent.

Especially definitions of observations and rewards are critical for the performance of the agent. The following sections will show an exemplary implementation of the environment for the sequencing task.

## Example implementation of a sequencing environment

In this example, we will implement the training environment for an RL-agent that determines the sequence of performed processes for the production resource R2 from the example above.

For a simple optimization of performed processes, we want that the RL-agent can observe all running processes and all upcoming processes from the queue. We want to motivate the agent to sequence in a way, that the WIP is low and as few as little setups are performed, since this lower throughput.

To do so, we define the observation space, to be a binary tensor of shape CxP, where C is the number of possible running processes and the number of slots in the input queue of the resource and P is the number of possible processes. This tensor shows then which slot from resource or queue is taken by which process type.

The reward will be defined by a stepwise reward and a sparse reward:

- **Stepwise reward**: The agent receives a reward of -1 if he selects an invalid action, 1 if he selects a valid action which requires not setup and 0 otherwise.
- **Sparse reward**: The agent receives a reward based on the difference of queue capacity and WIP at the resource.

Lastly, termination is defined by 100k minutes passed in simulation time and the info is just a placeholder.

The following code shows the implementation of the environment:

```python

class ProductionControlEnv(sequencing_control_env.AbstractSequencingControlEnv):
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
            reward = -1
        else:
            reward = (
                self.resource.current_setup is None
                or processed_request.process.process_data.ID
                == self.resource.current_setup.process_data.ID
            )
        if self.step_count % 10 == 0:
            reward += self.resource.input_queues[0].capacity - len(self.resource_controller.requests) 
        
        return reward

```

Note that we utillize the observer, which is an attribute of the environment. The observer brings handy functions to observe the current state of a resource in the simulation.

In order to validate that this environment works, we will at first use just random samping as a agent and step through it. At first, we we define the observation and action space since these are required by the environment and need to fit to our get_observation function:

```python

resource_id = "R2"
resource_data = [r for r in production_system.resource_data if r.ID == resource_id][0]
queue = [q for q in production_system.queue_data if q.ID == resource_data.input_queues[0]][0]
shape = (queue.capacity + resource_data.capacity, len(resource_data.process_ids))
observation_space = spaces.Box(0, 1, shape=shape, dtype=int)
action_space = spaces.Box(0, 1, shape=(queue.capacity,), dtype=float)
    
```

Now, we can create an instance of the environment and step through it:

``` python

env = ProductionControlEnv(production_system, "R2", observation_space=observation_space, action_space=action_space, render_mode="human")
observation, info = env.reset(seed=42)
for step in range(20):
   action = env.action_space.sample()  # this is where you would insert your policy
   observation, reward, terminated, truncated, info = env.step(action)
   print(f"Step: {step} with a reward of {reward}")

   if terminated or truncated:
      observation, info = env.reset()
env.close()
    
```

Lastly, we want to use a PPO RL-agent from stable-baselines3 to train the environment. We will use the default hyperparameters for the agent and train it for 20k steps. The following code shows the training:

``` python

import os
import time
from stable_baselines3 import PPO
from stable_baselines3.common.logger import configure

tmp_path = os.getcwd() + "\\tensorboard_log\\sequencing\\" + time.strftime("%Y%m%d-%H%M%S")
new_logger = configure(tmp_path, ["stdout", "csv", "tensorboard"])

model = PPO(env=env, policy='MlpPolicy', verbose=1)
model.set_logger(new_logger)
model.learn(total_timesteps=20000)

```

You can review the training progress by looking at the tensorboard logs in the folder `tensorboard_log\sequencing` in the current working directory. The following code will show the tensorboard logs in the notebook:

``` bash
tensorboard --logdir tensorboard_log\sequencing
```

This example should only show the required implementation for an RL-agent for production control tasks. The routing control task can be implemented in a similar fashion. For more information on the implementation of the environment, please refer to the documentation of the abstract base classes in the [API reference](../API_reference/API_reference_0_overview.md) of `prodsys.control`.
