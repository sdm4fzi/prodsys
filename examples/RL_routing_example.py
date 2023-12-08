from __future__ import annotations

import os
import time
import math
import pandas as pd

from stable_baselines3 import PPO
from stable_baselines3.common.logger import configure
from stable_baselines3.common.callbacks import BaseCallback


import numpy as np
from gymnasium import spaces
#import torch

import prodsys
from prodsys.adapters import adapter
from prodsys.control import routing_control_env
from prodsys.models.resource_data import TransportResourceData
from prodsys.simulation import resources

#import sys 
#sys.path.insert(0, 'E:/prodsys/prodsys/control')
#import routing_control_env_file

class ProductionControlEnv(routing_control_env.AbstractRoutingControlEnv):

    adapter_object = prodsys.adapters.JsonProductionSystemAdapter()
    adapter_object.read_data('examples/basic_example/example_configuration.json')
    product_count = 0
    time = 0.0

    prev_tta = [0] * len(adapter_object.resource_data)
    acc_prev_tta = [0] * len(adapter_object.resource_data)
    mean_time_tta = [0] * len(adapter_object.resource_data)
    variance_tta = [0] * len(adapter_object.resource_data)
    counter_tta = [0] * len(adapter_object.resource_data)
    normalized_tta = [0] * len(adapter_object.resource_data)

    time_increment_pr = [0] * len(adapter_object.resource_data)
    increment = [0] * len(adapter_object.resource_data)
    invalid_step_count = 0

    stepper = 0
    def get_observation(self) -> np.ndarray:    

        """
        Function that utilizes the ResourceObserver of the environment class to get an array of observations concerning the availability of resources.

        Action-related data: feasibility of dispatching actions
        Agent related data: current location
        Resource-related data: availability status, remaining processing time, inbound and outbound buffer availability, and total processing time (including waiting order)
        Order-related data: waiting time and location information

        Returns:
            np.ndarray: The observation.
        """

        encoded_observations_dict = {}
        
        encoded_observations_dict['product setup'] = self.get_product_setup()
        encoded_observations_dict['time till availability'] = self.get_time_till_availability()
        encoded_observations_dict['availability'] = self.get_availability()
        encoded_observations_dict['euclidean_distances'] = self.get_euclidean_distances()
        encoded_observations_dict['queue full'] = self.get_queue_full()    
        encoded_observations_dict['possible resources'] = self.get_possible_resources()
        (
            encoded_observations_dict['output queues'],
            encoded_observations_dict['input queues'],
        ) = self.get_input_output_queues()
        return encoded_observations_dict
        
    def get_product_setup(self):
        
        process_ids = {process.ID: i for i, process in enumerate(adapter_object.process_data)}
        encoded_processes = []
        
        for observer in self.observers:
            a = observer.resource.production_states
            processes = [0] * len(adapter_object.process_data)
            for production_state in observer.resource.production_states:
                if production_state.process and production_state.state_info.ID in process_ids:
                    index = process_ids[production_state.state_info.ID]
                    processes[index] = 1
            encoded_processes.append(processes)
        return encoded_processes   
        

        #1
        #time till availability
        #get the event logger data
   
    def get_time_till_availability(self):
        time_till_availability = [0] * len(adapter_object.resource_data)        
        for index, resource in enumerate(self.runner.resource_factory.resources):
            expected_end_time = resource.production_states[0].start + resource.production_states[0].done_in            
            tta = expected_end_time - self.runner.env.now
            if tta < 0:
                tta = 0
            time_till_availability[index] = tta
            if time_till_availability[index] != self.prev_tta[index]:
                self.counter_tta[index] += 1
                self.mean_time_tta[index] = (time_till_availability[index]+self.acc_prev_tta[index])/self.counter_tta[index]    
                self.variance_tta[index] += ((time_till_availability[index]-self.mean_time_tta[index])**2)/self.counter_tta[index]
                if self.variance_tta[index] == 0:
                    self.variance_tta[index] = 1
                self.normalized_tta[index] = (time_till_availability[index]-self.mean_time_tta[index])/math.sqrt(self.variance_tta[index])
                self.acc_prev_tta[index] += time_till_availability[index]
                self.prev_tta[index] = time_till_availability[index]
           
        return self.normalized_tta
    
        #2
        #bool | is the resource available or does it have a breakdown
    def get_availability(self):
        availability_data = []
        for available_observations in self.observers:
            resource_available_status = available_observations.observe_resource_available()
            availability_data.append(int(resource_available_status.available))
        return availability_data      
        
        #3
        #euclidean distance of production resources to transport resources
        #could change to simple x and y distance, maybe more realistic
    
    def get_euclidean_distances(self):
        resource_data = adapter_object.resource_data        
        resource_event = self.runner.product_factory.event_logger.event_data[-1]['Resource']         
        resource_event_x, resource_event_y = [0, 0]
        
        #get the location of the resource where the event takes place. product can't request when its at sink thats why its not here
        for resource in resource_data:
            if resource.ID == resource_event:
                resource_event_x, resource_event_y = resource.location[0:2]
                break
        for resource in adapter_object.source_data:
            if resource.ID == resource_event:
                resource_event_x, resource_event_y = resource.location[0:2]
                break

        euclidean_distances_data = []
        all_locations = []

        # extend the list with all resources, sources and sinks
        all_locations.extend(adapter_object.source_data)
        all_locations.extend(adapter_object.sink_data)
        all_locations.extend(resource_data)

        #calculate euclidean distance of the event resource with all other entities in the all locations list and use min-max normalization
        all_locations = np.array([location.location[:2] for location in all_locations])

        # euclidean distance (vector)
        location_x, location_y = all_locations.T
        resource_event_x = resource_event_x * np.ones_like(location_x)
        resource_event_y = resource_event_y * np.ones_like(location_y)

        euclidean_distances_data = np.sqrt((resource_event_x - location_x)**2 + (resource_event_y - location_y)**2)
    
        # normalization of distance
        max_distance = np.max(euclidean_distances_data)
        normalized_distances = euclidean_distances_data / max_distance

        return normalized_distances
    
    
        #4
        #bool: if the queue of a resource is full or not (input and output queue and source queue)
    def get_queue_full(self):
        queues_full_data = []
        for queue_full in self.runner.queue_factory.queues:
            queue_filled = queue_full.full
            queues_full_data.append(queue_filled)

        return queues_full_data

    def get_possible_resources(self):       
        list_resource_IDs = sorted({observer.resource.data.ID for observer in self.observers})
        enc_possible_resources = [int(resource in [r.data.ID for r in self.possible_resources]) for resource in list_resource_IDs]
        return enc_possible_resources


        #5
        #location of product, reserved location
    def get_input_output_queues(self):
        
        product_locations = []
        output_queues = []
        input_queues = []
        for products in self.runner.product_factory.products:
            product_ID = products.product_data.ID
            product_resource = products.product_info.resource_ID
            product_at_resource = [product_ID, product_resource]
            product_locations.append(product_at_resource)

        #a list for every queue a resource has        
        for observer in self.observers:
            if isinstance(observer.resource, resources.ProductionResource):
                observer_queue_output = observer.resource.output_queues
                observer_queue_input = observer.resource.input_queues
                output_queues.append(observer_queue_output)
                input_queues.append(observer_queue_input)

        #one hot encoded matrixes for every output queue
        #the number of rows is the number of product types 
        #and a 1 gets to the row added when an item is in the queue

        columns = 2

        encoded_output_queues = np.zeros((len(adapter_object.product_data), columns, len(output_queues)))
        encoded_input_queues = np.zeros((len(adapter_object.product_data), columns, len(input_queues)))

        for i, observer in enumerate(self.observers):
            if isinstance(observer.resource, resources.ProductionResource):
                for j, queue in enumerate(observer.resource.output_queues):
                    for item in queue.items:
                        product_id = int(item.description[-1])
                         
                        k = product_id - 1
                        encoded_output_queues[k, j, i] = 1

                for j, queue in enumerate(observer.resource.input_queues):
                    for item in queue.items:
                        product_id = int(item.description[-1])
                        
                        k = product_id - 1
                        encoded_input_queues[k, j, i] = 1
        
        return encoded_output_queues, encoded_input_queues


    def get_info(self) -> dict:
        return {"info": 0}
    

    def get_termination_condition(self) -> bool:
        
        termination_condition = False
        # time-based termination like shift or day
        # action-based termination after certain amount of steps the agent is allowed to make for a task 
        # action-based termination steps until a product has to reach the sink
        # action-based termination allowed amount of invalid/valid actions

        #termination after a workday 24h
        if self.runner.env.now > 2880:
        #if self.stepper >= 5200:
            self.product_count = 0
            self.time = 0.0

            self.prev_tta = [0] * len(adapter_object.resource_data)
            self.acc_prev_tta = [0] * len(adapter_object.resource_data)
            self.mean_time_tta = [0] * len(adapter_object.resource_data)
            self.variance_tta = [0] * len(adapter_object.resource_data)
            self.counter_tta = [0] * len(adapter_object.resource_data)
            self.normalized_tta = [0] * len(adapter_object.resource_data)

            self.time_increment_pr = [0] * len(adapter_object.resource_data)
            self.increment = [0] * len(adapter_object.resource_data)
            self.invalid_step_count = 0
            self.stepper = 0
            termination_condition = True
            
            post_processor = prodsys.post_processing.PostProcessor(df_raw=self.runner.event_logger.get_data_as_dataframe())

            # Extract output data
            a = post_processor.df_aggregated_output_and_throughput

            output_all = a['Output'].sum()
            # Create DataFrame for output data
            df_output = pd.DataFrame({
                'ProductType': [str(product_type) for product_type in a['Output'].index],
                'OutputValue': a['Output'].tolist()
            })

            # Calculate cumulative PR
            df_resource_state = post_processor.df_aggregated_resource_states
            cumulated_PR = df_resource_state.loc[df_resource_state['Time_type'] == 'PR', 'percentage'].sum() / (100 * len(adapter_object.resource_data))
            df_throughput_time = post_processor.df_aggregated_throughput_time.reset_index()
            df_throughput_time.columns = ['Produkttyp', 'Throughput_time']
            # Create DataFrame for resource state data
            df_resource_state_pr = pd.DataFrame({'CumulatedPR': [cumulated_PR]})

            # Combine all DataFrames
            df_all_data = pd.concat([df_output, pd.DataFrame({'Metric': ['Output_all'], 'Value': [output_all]}), df_resource_state_pr, df_resource_state, df_throughput_time], axis=1)

            if not os.path.exists(results_csv_path):
                # Save to CSV with header
                df_all_data.to_csv(results_csv_path, index=False)
            else:
                # Save to CSV (Append mode)
                df_all_data.to_csv(results_csv_path, mode='a', header=False, index=False)
            #self.invalid_step_count = 0
                        
        return termination_condition   
    
    def get_reward(self, invalid_action: bool = False) -> float:
        a = self.possible_resources      
        reward = 0
        if self.runner.env.now <= 2800:
        #if self.stepper < 5180:    
            for index, resource in enumerate(self.runner.resource_factory.resources):
                if (resource.production_states[0].state_info._state_type == 'Production' or resource.production_states[0].state_info._state_type == 'Transport') and self.runner.env.now <= resource.production_states[0].state_info._expected_end_time:
                    self.increment[index] += self.runner.env.now - self.time   
            if invalid_action == True:
                reward = -1
                self.invalid_step_count += 1 
        
            else:              
                reward_PR = 0     
                #percentage of production state in ratio to the time minus breakdown  
                percentage_pr = self.increment/self.runner.env.now
                for value in percentage_pr:
                    reward_PR+=value
                
                reward_PR = reward_PR/len(self.adapter_object.resource_data)
                if reward_PR>1:
                    raise ValueError
                #reward_out = 0        
                #reward_out = (self.time / self.runner.env.now) * len(self.runner.product_factory.finished_products)/400
                
                #self.product_count = len(self.runner.product_factory.finished_products)


                reward = reward_PR 

            self.time = self.runner.env.now
            #self.stepper+=1
        
        return reward
    
class TensorboardCallback(BaseCallback):
    """
    Custom callback for plotting additional values in tensorboard.
    """

    def __init__(self, verbose=0):
        super(TensorboardCallback, self).__init__(verbose)
        self.env = env       
    def _on_rollout_end(self) -> None:
        return super()._on_rollout_end()
    def _on_step(self) -> bool:                      
        #for resource in self.env.runner.resource_factory.resources:
        #    if not isinstance(resource.data, TransportResourceData):
        #        wip_resource = resource.count + len(resource.input_queues[0].items) + len(resource.output_queues[0].items)
        #        self.logger.record('wip ' + resource.data.ID, wip_resource)
        self.logger.record('reward', self.training_env.get_attr('reward')[0])   
        return True

if __name__ == '__main__':

    adapter_object = prodsys.adapters.JsonProductionSystemAdapter()
    adapter_object.read_data('examples/basic_example/example_configuration.json')
    num_resources_SI_SO = len(adapter_object.resource_data) + len(adapter_object.source_data) + len(adapter_object.sink_data)
    num_of_resources = len(adapter_object.resource_data)

    #to do: change number to variables
    observation_space = spaces.Dict({
        'availability': spaces.MultiBinary(num_of_resources), 
        'time till availability': spaces.Box(low=-3, high=3, shape=(num_of_resources,)),
        'euclidean_distances': spaces.Box(low=0, high=1, shape=(num_resources_SI_SO,)), 
        'queue full': spaces.MultiBinary(18),  
        'output queues': spaces.Box(0,1, shape = (3, 2, 8)),
        'input queues': spaces.Box(0,1, shape = (3, 2, 8)),
        'product setup': spaces.Box(0,1, shape = (num_of_resources, 9)),
        'possible resources': spaces.MultiBinary(num_of_resources)
        })
    action_space = spaces.Box(0,1,shape=(num_of_resources,), dtype=float)
    
    env = ProductionControlEnv(adapter_object, observation_space=observation_space, action_space=action_space, render_mode="human")

    #save path for custom dataframes 
    results_csv_path = os.getcwd() + "\\tensorboard_log\\Custom_routing\\" + time.strftime("%Y%m%d-%H%M%S") + ".csv"
    tmp_path = os.getcwd() + "\\tensorboard_log\\routing\\" + time.strftime("%Y%m%d-%H%M%S")
    new_logger = configure(tmp_path, ["stdout", "csv", "tensorboard"])

    model = PPO(env=env, policy='MultiInputPolicy', verbose=1, learning_rate= 0.0003)
    model.set_logger(new_logger)
    model.learn(total_timesteps=3000000, callback=TensorboardCallback()) #comment out if using trained agent
    save_path = os.getcwd() + "\\tensorboard_log\\trained_Agent_" + time.strftime("%Y%m%d-%H%M%S")
    #save_path = 'E:/prodsys/RLAgent_Routing/20231123-055437.zip'
    model.save(save_path) #comment out if using trained agent

    
    #code to use a saved model
    #load_model = PPO.load(save_path)
    #observation, info = env.reset(seed=24)
    #while env.runner.env.now < 1440:
    #    action = load_model.predict(observation, deterministic=True) 
    #    observation, reward, terminated, truncated, info = env.step(action[0])  # Fuehre die Aktion in der Umgebung aus
    #    #print(f"Step: {step} with a reward of {reward}")
     
    #    if terminated or truncated:
    #        break
    #        observation, info = env.reset()
    #print(env.runner.get_post_processor().df_aggregated_output)
    #print(env.runner.get_post_processor().df_aggregated_resource_states)
    #env.close()  
    

    # Start Tensorboard with: tensorboard --logdir=E:/prodsys/tensorboard_log/routing
    #snakeviz python -m cProfile -o output.prof E:/prodsys/examples/Test_routing.py
    #snakeviz output.prof
