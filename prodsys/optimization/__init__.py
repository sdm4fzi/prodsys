"""
The `optimization` package of `prodsys` provides different optimization algorithms for configuration planning of production systems. 

In configuration planning, the goal is to find a configuration of a production system that maximizes a given objective function. The objective function is a function that maps a configuration to a real number. The configuration is a set of parameters that describe the production system. For example, the configuration of a production system could be the number of machines of a certain type. The objective function could be the output of the production system. The goal is then to find the configuration that maximizes the output. With `prodsys.optimization`, you can use the modelling capacities of  `prodsys.adapters` to specifiy configurations and optimize them according to a scenario and chosen degrees of freedom for optimization.

The following degrees of freedom are supported and can be specified by the scenario data attribute `transformations`:

- Adding or removing production resources
- Adding or removing transport resources
- Adding or removing processes of a production resource
- Changing the position of production resources
- Moving processes between production resources
- Changing the control policy of a production resource
- Changing the control policy of a transport resource
- Changing the routing policy of product types

The following algorithms are supported:

- Evolutionary Algorithms (NGSGA-II)
- Simulated Annealing
- Tabu Search
- Mathematical optimization (Gurobi, only a restricted set of degrees of freedom is supported)

Whilst the mathematical optimization uses a mathematical model for evalutation of production system performance, the other algorithms use `prodsys.simulation` for evaluation. This allows these algorithms to consider more degrees of freedom and optimize according to multiple objectives.

The following KPIs are supported for objectives in optimization with the simulation based optimization algorithms:

- Minimize the WIP (Work in Progress)
- Minimize the throughput time
- Minimize the reconfiguration cost considering capital expenditure (CAPEX)
- Maximize the output / throughput


For a more detailed explanation on the algorithms, degrees of freedom and choice of objectives, please consider the following literature: [Paper](https://doi.org/10.15488/13440)
"""

VERBOSE = 1
"""
The verbosity level of the optimization algorithms. The higher the level, the more information is printed to the console.
"""