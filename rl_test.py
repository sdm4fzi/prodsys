from __future__ import annotations
import fractions
from typing import List, Literal
import json
from gym.spaces import Dict, Discrete, Box, unflatten, flatten, flatten_space
import gym
import numpy as np
from dataclasses import dataclass, field

import ray
from ray.rllib.algorithms import ppo
from ray import rllib

from prodsim import loader, env, control
from prodsim.util import set_seed

@dataclass
class Observation_Space:
    max_num_machines: int = 0
    max_num_process_modules: int = 0
    max_num_transport_resources: int = 0

    num_processes: int = 0
    num_machine_control_policies: int = 0
    num_transport_control_policies: int = 0
    
    layout_x_range: List[int] = field(default_factory=list)
    layout_y_range: List[int] = field(default_factory=list)


    def set_values_from_scenario(self, scenario_dict: dict, loader: loader.CustomLoader):
        self.max_num_machines = scenario_dict["constraints"]["max_num_machines"]
        self.max_num_transport_resources = scenario_dict["constraints"]["max_num_transport_resources"]
        self.max_num_process_modules = scenario_dict["constraints"]["max_num_processes_per_machine"]

        self.num_processes = len(loader.get_processes())
        self.num_machine_control_policies = len(scenario_dict["options"]["machine_controllers"])
        self.num_transport_control_policies = len(scenario_dict["options"]["transport_controllers"])

        locations = scenario_dict["options"]["positions"]
        x_positions = [location[0] for location in locations]
        y_positions = [location[1] for location in locations]
        
        self.layout_x_range = [min(x_positions), max(x_positions)]
        self.layout_y_range = [min(y_positions), max(y_positions)]
    

    def get_space(self) -> gym.Space:
        machine_space = Box(low=0, high=1, shape=(self.max_num_machines,), dtype=int)
        pm_space = Box(low=0, high=1, shape=(self.max_num_machines,self.max_num_process_modules, self.num_processes), dtype=int)
        machine_control_policy_space = Box(low=0, high=1, shape=(self.max_num_machines, self.num_machine_control_policies), dtype=int)

        location_space_x = Box(low=self.layout_x_range[0], high=self.layout_x_range[1], shape=(self.max_num_machines, ), dtype=int)
        location_space_y = Box(low=self.layout_y_range[0], high=self.layout_y_range[1], shape=(self.max_num_machines, ), dtype=int)


        transport_space = Box(low=0, high=1, shape=(self.max_num_transport_resources,), dtype=int)
        transport_resource_control_policy_space = Box(low=0, high=1, shape=(self.max_num_transport_resources, self.num_transport_control_policies), dtype=int)

        # TODO: maybe add max total costs and costs per asset

        space = Dict({
            "machines": machine_space,
            "pm": pm_space,
            "machine_control": machine_control_policy_space,
            "loc_x": location_space_x, 
            "loc_y": location_space_y, 
            "transport": transport_space,
            "transport_control": transport_resource_control_policy_space,

        })
        
        # x = space.sample()
        # # print(x)
        # flattened = flatten(space, x)
        # print(flattened)
        # print("observation length: ", len(flattened))

        # unflattened = unflatten(space, flattened)

        return space


@dataclass
class Action_Space:
    max_num_machines: int = 0
    max_num_transport_resources: int = 0

    num_processes: int = 0
    num_machine_control_policies: int = 0
    num_transport_control_policies: int = 0
    num_positions: int = 0

    def set_space_from_scenario(self, scenario_dict: dict, loader: loader.CustomLoader):
        self.max_num_machines = scenario_dict["constraints"]["max_num_machines"]
        self.max_num_transport_resources = scenario_dict["constraints"]["max_num_transport_resources"]

        self.num_processes = len(loader.get_processes())
        self.num_machine_control_policies = len(scenario_dict["options"]["machine_controllers"])
        self.num_transport_control_policies = len(scenario_dict["options"]["transport_controllers"])
        self.num_positions = len(scenario_dict["options"]["positions"])
    

    def get_space(self) -> gym.Space:
        add_machine_space = Box(low=0, high=1, shape=(self.num_processes, self.num_machine_control_policies, self.num_positions), dtype=float)
        remove_machine_space = Box(low=0, high=1, shape=(self.max_num_machines,), dtype=float)
        move_machine_space = Box(low=0, high=1, shape=(self.max_num_machines, self.num_positions), dtype=float)


        add_transport_space = Box(low=0, high=1, shape=(self.num_transport_control_policies, ), dtype=float)
        remove_transport_space = Box(low=0, high=1, shape=(self.max_num_transport_resources,), dtype=float)

        add_process_space = Box(low=0, high=1, shape=(self.max_num_machines, self.num_processes), dtype=float)
        remove_process_space = Box(low=0, high=1, shape=(self.max_num_machines, self.num_processes), dtype=float)
        move_process_space = Box(low=0, high=1, shape=(self.max_num_machines, self.max_num_machines, self.num_processes), dtype=float)


        space = Dict({
            "add_machine": add_machine_space,
            "remove_machine": remove_machine_space,
            "move_machine_space": move_machine_space,
            "add_transport": add_transport_space,
            "remove_transport": remove_transport_space,
            "add_process": add_process_space,
            "remove_proces_space": remove_process_space, 
            "move_process_space": move_process_space, 
        })
        
        # x = space.sample()
        # # print(x)
        # flattened = flatten(space, x)
        # # print(flattened)
        # print("action length: ", len(flattened))


        # unflattened = unflatten(space, flattened)

        return space

class RLReconfigurator(gym.Env):
        def __init__(self, env_config):

            self.scenario_dict = env_config["scenario_dict"]
            self.scenario_loader = env_config["scenario_loader"]
            self.unflattened_action_space =  env_config["action_space"]
            self.action_space =  flatten_space(self.unflattened_action_space)
            self.unflattened_observation_space = env_config["observation_space"]
            self.observation_space = flatten_space(self.unflattened_observation_space)

            
        def reset(self):
            return self.observation_space.sample()
        def step(self, action):
            # print(action)
            print(action)
            print("________________")
            unflattened_action = unflatten(self.unflattened_action_space, action)
            
            # return <obs>, <reward: float>, <done: bool>, <info: dict>
            return self.observation_space.sample(), 0.1, False, {}
        

if __name__ == "__main__":

    SEED = 22
    env.VERBOSE = 0

    base_scenario = "data/base_scenario.json"

    with open("data/scenario.json") as json_file:
        scenario_dict = json.load(json_file)

    set_seed(SEED)

    scenario_loader = loader.CustomLoader()
    scenario_loader.read_data(base_scenario, "json")
    
    WEIGHTS = (-0.025, 1.0, 0.001)

    # CONTROL_POLICY_DICT: Dict = {
    # 'FIFO': 1,
    # 'LIFO': 2,
    # 'SPT': 3,
    # 'SPT_transport': 4,
    # }

    # CONTROL_POLICY_MAPPING = {key: counter for counter, key in enumerate(CONTROL_POLICY_DICT.keys())}



    os = Observation_Space()
    os.set_values_from_scenario(scenario_dict=scenario_dict, loader=scenario_loader)
    os_gym_space = os.get_space()

    
    a_s = Action_Space()
    a_s.set_space_from_scenario(scenario_dict=scenario_dict, loader=scenario_loader)
    as_gym_space = a_s.get_space()

    
    ray.init()
    
    algo = ppo.PPO(env=RLReconfigurator, config={
        "framework": "tf2", 
        "env_config": {
            "scenario_dict": scenario_dict,
            "scenario_loader": scenario_loader,
            "action_space": as_gym_space,
            "observation_space": os_gym_space
        }, 
    })

    while True:
        print(algo.train())