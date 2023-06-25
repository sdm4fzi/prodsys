# Optimizing a production system

This tutorial will guide you through the optimization functionalities of `prodsys` to optimize the configuration of a production system. With the `prodsys.optimization` package, we can utilize meta-heuristics and mathematical optimization for this task. All algorithms can be conviently used with the `prodsys.models` API.

For this example, we will use a production system which we will load from a json-file (base_configuration.json), which can be found in the examples folder of [prodsys' github page](https://github.com/sdm4fzi/prodsys/tree/main/examples/tutorials). Download it and store it in the same folder as this notebook. Load the configuration and run a simulation with the following commands:

```python
import prodsys
from prodsys.simulation import sim
sim.VERBOSE = 0

production_system = prodsys.adapters.JsonProductionSystemAdapter()
production_system.read_data('base_configuration.json')

prodsys.adapters.add_default_queues_to_adapter(production_system)

runner = prodsys.runner.Runner(adapter=production_system)
runner.initialize_simulation()
runner.run(2880)
runner.print_results()
```

As already concluded in the seccond tutorial, production system configurations can be suboptimal for a certain load of products. In this example, we also see that resoures M2, M3, M4 are very heavily utilized, whereas resource M1 has only a productivy of 34.4%. In order to satify the product needs of our customers and to balance the load on the resources more evenly, we want to find a more suitable configuration with the `prodsys.optimization` package. However, for starting optimization, we also need to provide an optimization scenario, that models constraints, options, information and the objectives. Let's start by creating the constraints of the scenario with the `prodsys.models` API:

```python
from prodsys.models import scenario_data

constraints = scenario_data.ScenarioConstrainsData(
    max_reconfiguration_cost=100000,
    max_num_machines=8,
    max_num_processes_per_machine=3,
    max_num_transport_resources=2
)
```

As you can see, the constraints consist of the maximum cost for reconfigruation and the maximumm number of machines, processes per machine and transport resources. Next, we define the options of our scenario for optimization:

```python
positions = [[x*4, y*4] for x in range(4) for y in range(10)]
options = scenario_data.ScenarioOptionsData(
    transformations=[scenario_data.ReconfigurationEnum.PRODUCTION_CAPACITY],
    machine_controllers=["FIFO", "SPT"],
    transport_controllers=["FIFO", "SPT_transport"],
    routing_heuristics=["shortest_queue"],
    positions=positions
)
```

We specify in the scenario options the transformations that can be performed by the optmizer, which control policies and routing heuristics are available and what kind of positions are available to place resources. By choosing the transformation `PRODUCTION_CAPACITY`, the optimizer can add, remove or move production resources from the system or processes from single production resources.

At last, we need to specify our info for optimization:

```python
info = scenario_data.ScenarioInfoData(
    machine_cost=40000,
    transport_resource_cost=20000,
    process_module_cost=4000,
    time_range=24*60
)
```

The scenario info contains information about the cost for machines, transport resources and process modules. Additionally, we specify a time range. This value is the time used for evalutation of created configurations during simulation. Since many evaluations are performed during optimization, this parameter can significantly influence the optimmization Time. For now, we specified it to one day. Lastly we can define the objectives used for optimization:

```python
from prodsys.models.performance_indicators import KPIEnum
objectives = [scenario_data.Objective(
    name=KPIEnum.THROUGHPUT
)]
```

Currently, only reconfiguration cost, throughput time, WIP and throughput can be optimized. Yet, similar logic can also be used for optimizing the productivity. With all this data defined, we can now create our optimization scenario and additionally add it to our production system:

```python
scenario = scenario_data.ScenarioData(
    constraints=constraints,
    options=options,
    info=info,
    objectives=objectives
)
production_system.scenario_data = scenario
```

Next, we define the hyper parameters for our optimization. At first, we will use evolutionary algorithm for our optimization, because it allows parallelization. The hyper parameters for optimization are strongly problem dependant and need to be adjusted accordingly. For this example, we will use the following parameters and run the optimization for 10 generations. Note, that this can take some time...

```python
from prodsys.optimization import evolutionary_algorithm_optimization
from prodsys.optimization import evolutionary_algorithm
from prodsys.simulation import sim
sim.VERBOSE = 0

hyper_parameters = evolutionary_algorithm.EvolutionaryAlgorithmHyperparameters(
    seed=0,
    number_of_generations=10,
    population_size=16,
    mutation_rate=0.2,
    crossover_rate=0.1,
    number_of_processes=4
)
evolutionary_algorithm_optimization(
    production_system,
    hyper_parameters,
)
```

All algorithms in `prodsys` can be utilized with the same interface. Also available are the following algorithms:

- `prodsys.optimization.simulated_annealing`: simulated annealing optimization for all transformations
- `prodsys.optimization.tabu_search`: tabu search for all transformations
- `prodsys.optimization.math_opt`: mathematical optimization with Gurobi, allows only optimization of the production capacity

We see in the output, that the algorithm is running and that new best solutions with a higher performance are found. We can analyze them now and see, if we can find a better configuration for our production system. Optimization core results of the objective for the individual solutions and the solutions themselves are saved as default in a `results` folder to make sure that interruptions in optimization won't delete all results. We can load them with the following command and search for the best solution:

```python
from prodsys.optimization import optimization_analysis

df = optimization_analysis.read_optimization_results_file_to_df("results/optimization_results.json", "evolutionary")
df.sort_values(by=["agg_fitness"], ascending=False).head()
```

`prodsys` allows us to load the optimization results as a data frame and analyze them. For validation purposes, we simuate the best solution again and compare it to the initial solutions:

```python
import os 

# Find all files i the result folder that contain the ID of the best individual
best_individual_ID = df.sort_values(by=["agg_fitness"], ascending=False).head()["ID"].values[0]
best_individual_ID = str(best_individual_ID)
files = os.listdir("results")
files = [file for file in files if best_individual_ID in file]
new_production_system = prodsys.adapters.JsonProductionSystemAdapter()
new_production_system.read_data("results/" + files[0])

runner = prodsys.runner.Runner(adapter=new_production_system)
runner.initialize_simulation()
runner.run(2880)

runner.print_results()
```

When comparing the results from the original production system and the new one, we see that two machines were added. However, the machines are still heavily utilized. Most likely, the optimizer did just not find a good solution, because we only ran it for 10 generations and for a small population size. Increasing these will take longer, but will more likely find better solutions.

For a complete overview of the package's functionality, please see the [API reference](/API_reference/API_reference_0_overview.md).
