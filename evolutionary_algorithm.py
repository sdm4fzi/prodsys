from env import Environment
import loader
import print_util
from post_processing import PostProcessor

import multiprocessing
from deap import base, creator, tools, algorithms




#weights für: (logging_time, total_costs, OEE_ges, wip, AOET,)
creator.create('FitnessMin', base.Fitness, weights=(-1.0,-1.0, 1.0,-1.0,-1.0,)) # als Tupel
creator.create('Individual', list, fitness=creator.FitnessMin)

toolbox = base.Toolbox()

options_dict = {}
def initPopulation(options_dict, pcls, ind_init):
    # Generate initial population without evaluation -> 
    pass

# Startpopulation erzeugen
toolbox.register("population", initPopulation, options_dict, list, creator.Individual)
population = toolbox.population()

def evaluate(options_dict, dict_results):
    # Do Simulation runs of all options and return dict_results
    pass

def crossover(dict_results):
    pass

def mutation(options_dict, dict_results, indpb):
    pass

dict_results = {}
toolbox.register('evaluate', evaluate, options_dict, dict_results)
toolbox.register('mate', crossover, dict_results) #pass
toolbox.register('mutate', mutation, options_dict, dict_results, indpb=0.05)
#toolbox.register('select', tools.selTournament, tournsize=3)
toolbox.register('select', tools.selNSGA2)



c = loader.CustomLoader()
c.read_data("data/base_scenario.json", "json")


capacity = 100

c.add_queue(ID="IQM1", description="Input queue 1", capacity=capacity)
c.add_queue(ID="IQM2", description="Input queue 2", capacity=capacity)
c.add_queue(ID="IQM3", description="Input queue 3", capacity=capacity)
c.add_queue(ID="IQM4", description="Input queue 4", capacity=capacity)
c.add_queue(ID="IQM5", description="Input queue 5", capacity=capacity)

c.add_queue(ID="OQM1", description="Output queue 1", capacity=capacity)
c.add_queue(ID="OQM2", description="Output queue 2", capacity=capacity)
c.add_queue(ID="OQM3", description="Output queue 3", capacity=capacity)
c.add_queue(ID="OQM4", description="Output queue 4", capacity=capacity)
c.add_queue(ID="OQM5", description="Output queue 5", capacity=capacity)


c.add_resource(ID="M1", description="Machine 1", controller="SimpleController", control_policy="FIFO", location=[0, 0], capacity=1, processes=["P1", "P3"], states="BS1", input_queues=["IQM1"], output_queues=["OQM1"])
c.add_resource(ID="M2", description="Machine 2", controller="SimpleController", control_policy="SPT", location=[0, 5], capacity=1, processes=["P2", "P5"], states="BS1", input_queues=["IQM2"], output_queues=["OQM2"])
c.add_resource(ID="M3", description="Machine 3", controller="SimpleController", control_policy="FIFO", location=[5, 0], capacity=1, processes=["P4"], states="BS1", input_queues=["IQM3"], output_queues=["OQM3"])
c.add_resource(ID="M4", description="Machine 4", controller="SimpleController", control_policy="FIFO", location=[5, 5], capacity=1, processes=["P2"], states="BS1", input_queues=["IQM4"], output_queues=["OQM4"])


c.add_resource(ID="TR1", description="Transport Resource 1", controller="TransportController", control_policy="SPT_transport", location=[10, 20], capacity=1, processes=["TP1"], states="BS2")

c.to_json("data/resulting.json")


e = Environment()
e.loader = c
e.initialize_simulation()


import time

t_0 = time.perf_counter()

e.run(4000)

t_1 = time.perf_counter()

print_util.print_simulation_info(e, t_0, t_1)    

e.data_collector.log_data_to_csv(filepath="data/data21.csv")


p = PostProcessor(filepath="data/data21.csv")
p.print_aggregated_data()
# p.plot_WIP()
# p.plot_throughput_over_time()
# p.plot_time_per_state_of_resources()