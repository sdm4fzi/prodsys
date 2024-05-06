# Modelling a production system

In this example we explore the modeling functionalities of `prodsys`. In `prodsys` we model production systems be specifying the attributes of the following components:

- **Time model**: All relevant timely features of the production system.
- **Processes**: Processes give resources the capabilities to perform certain production or transport processes.
- **Resources**: Resources perform the production and transport processes.
- **Products**: The products that are produced in the production system, requiring a set of processes to be performed.
- **Sources**: Sources create products and place them in the production system.
- **Sinks**: Sinks store finished products.
- **Production system**: The production system is the container for all components and is used to run the simulation.

To make these concepts more understandable, we extend the example from the [getting started](../index.md) section. The production system contains a milling machine, a turning lath and a work center that perform processes on aluminium housings. The transport is thereby performed by a worker.

We will start by importing the express API:

```python
import prodsys.express as psx
```

Additionally, since the progress bar can be buggy sometimes in Jupyter notebooks, we can disable it for this example by setting the verbose level of the simulation to 0:

```python
from prodsys.simulation import sim

sim.VERBOSE = 0
```

## Time models

`prodsys` provides different types of time models to use, the are:

- **FunctionTimeModel**: A time model that is based on a distribution function. Either constant, normal, lognormal or exponential.
- **SequenceTimeModel**: A time model that is based on a sequence of time values that are randomly sampled.
- **ManhattanDistanceTimeMOdel**: A time model that is based on the manhattan distance between two locations and a constant speed and reaction time.

We will use the `FunctionTimeModel` to model the time required for milling and turning processes and model the time needed for transport with the `ManhattanDistanceTimeModel`. We will also model the arrival of housings with the `SequentialTimeModel`, which could, e.g. be observed inter-arrival times:

```python
milling_time = psx.FunctionTimeModel(distribution_function="normal", location=1, scale=0.1, ID="milling_time")
turning_time = psx.FunctionTimeModel(distribution_function="normal", location=0.5, scale=0.1, ID="turning_time")
transport_time = psx.ManhattanDistanceTimeModel(speed=200, reaction_time=0.05, ID="transport_time")
arrival_time_of_housing_1 = psx.SequentialTimeModel([1.6, 1.3, 1.8, 2.0, 1.2, 1.7, 1.3], ID="arrival_time_of_housings")
arrival_time_of_housing_2 = psx.SequentialTimeModel([1.3, 2.3, 2.1, 2.0, 1.4], ID="arrival_time_of_housings")
```

## Processes

After creating the time models, we can define the processes in the system. We will use the `ProductionProcess` to model the milling and turning processes and the `TransportProcess` to model the transport process:

```python
milling_process = psx.ProductionProcess(milling_time, ID="milling_process")
turning_process = psx.ProductionProcess(turning_time, ID="turning_process")
transport_process = psx.TransportProcess(transport_time, ID="transport_process")
```

`prodsys` also provides the possibility for a `CapabilityProcess` instead of normal `ProductionProcess`. These processes are not matched by their ID but by their capability, which gives more flexibility. This extends the typical PPR modeling principle (Product, Process and Resource) of `prodsys` to the Product, Process, Resource and Skill modelling principle [PPRS](https://publica-rest.fraunhofer.de/server/api/core/bitstreams/512978c9-389a-43c1-8cbe-016f08e6952d/content) by considering the capabilities / skills required for performing processes. With this feature, one can specify with `RequiredCapabilityProcess` for products only which kind of capabilities are required and allow that multiple differnt `CapabilityProcess` are matched to these required processes. 

Moreover, there also exists a `LinkTransportProcess` which allows to define that a transport process can only be performed between certain resources. This allows to make transport in `prodsys` more realistic. 

For more information, refer to the API reference in the documentation or checkout the examples folder of `prodsys`.

## Resources

With this, we can create our resources. The milling machine and turning lath can perform their associated processes and the worker can perform the transport process. However, the work center can perform milling and turning. Milling machine, turning lath and work center are `ProductionResource`s and the worker is a `TransportResource`:

```python
milling_machine = psx.ProductionResource([milling_process], location=[5, 5], ID="milling_machine")
turning_lath = psx.ProductionResource([turning_process], location=[10, 10], ID="turning_machine")
work_center = psx.ProductionResource([milling_process, turning_process], location=[5, 10], ID="work_center")
worker = psx.TransportResource([transport_process], location=[0, 0], ID="worker")
```

## Product

Now, with specified resources, we can model our product, the housing. In fact, we don't have only one housing but two different variants for this example. The first product requires milling and afterwards turning, and the second requries turning and afterwards milling:

```python
housing_1 = psx.Product([milling_process, turning_process], transport_process, ID="housing_1")
housing_2 = psx.Product([turning_process, milling_process], transport_process, ID="housing_2")
```

## Sources and sinks

At last, we need to model the sources and sinks. The source creates housings and places them in the production system. The sink stores finished housings:

```python
source_1 = psx.Source(housing_1, arrival_time_of_housing_1, location=[0,0], ID="source_1")
source_2 = psx.Source(housing_2, arrival_time_of_housing_2, location=[0, 1], ID="source_2")

sink_1 = psx.Sink(housing_1, location=[20, 20], ID="sink_1")
sink_2 = psx.Sink(housing_2, location=[20, 21], ID="sink_2")
```

## Production System creation

We now create the production system, validate it and run the simulation for 60 minutes. Afterwards, we print aggregated simulation results:

```python
production_system = psx.ProductionSystem([milling_machine, turning_lath, work_center, worker], [source_1, source_2], [sink_1, sink_2])
production_system.validate()
production_system.run(60)
production_system.runner.print_results()
```

By validating the production system, we can check if all components are valid and if the production system is consistent in a logical or physical sende. If the production system is not valid, the validation will raise an exception and the simulation cannot be run. However, it easily let's you identify where you made some modelling mistakes.

## States

We can also add different states, such as setups and breakdowns, to resources to model their behavior more accurately. For example, we can add a setup and breakdown to the work center by specifying the time models for breakdown an setup, create states and add them to the work center:

```python
breakdwon_time_model = psx.FunctionTimeModel(distribution_function="exponential", location=200, ID="breakdown_time_model")
repair_time_model = psx.FunctionTimeModel(distribution_function="exponential", location=10, ID="repair_time_model")
setup_time_model_1 = psx.FunctionTimeModel(distribution_function="exponential", location=0.2, ID="setup_time_model")
setup_time_model_2 = psx.FunctionTimeModel(distribution_function="exponential", location=0.3, ID="setup_time_model")

breakdown_state = psx.BreakDownState(breakdwon_time_model, repair_time_model, ID="breakdown_state")
setup_state_1 = psx.SetupState(setup_time_model_1, milling_process, turning_process, ID="setup_state_1")
setup_state_2 = psx.SetupState(setup_time_model_2, turning_process, milling_process, ID="setup_state_2")

work_center.states = [breakdown_state, setup_state_1, setup_state_2]
```

Note, that we could have given these states to the resource already in the initialization. Again, we simulate the production system and evaluate its performance.

```python
production_system.validate()
production_system.run(60)
production_system.runner.print_results()
```

The results show that the work center is now for some time in Setup (ST).  However, no time increment for unscheduled downtime due to breakdowns (UD) is visible. This is due to the limited simulation time. If we increase the simulation time to 1000 minutes, we can see that the work center is also in unscheduled downtime for some time:

```python
production_system.validate()
production_system.run(1000)
production_system.runner.print_results()
```

Now we see, that the work center is 6.1% of the time unavailable due to unscheduled downtime.

## Changing the logic of the production system

`prodsys` does not only allow to change the physical configuration of a production system but also the logic. For example, we can change the logic of the work center by changing it's control policy from `FIFO` (first in first out) to `SPT` (shortes process time first). BY changing this, the work center will now get products from the queue with bias on the short process, which is in our case the turning process:

```python
from prodsys.models.resource_data import ResourceControlPolicy

work_center.control_policy = ResourceControlPolicy.SPT

production_system.validate()
production_system.run(1000)
production_system.runner.print_results()
```

Additionally, we can change the routing policy in the production system. A routing policy is not used for heuristically solving a sequencing problem as the control policy but for solving the routing problem for parallel redundant resources. In our example, bot milling machine and work center provide the milling process. While simulating, we need to have some logic how to decide which product is processed on which resource. By default, the routing policy is `random`, which means that the routing is randomly chosen. However, we can also change the routing policy to `shortest_queue`, which means that the product is always routed to the resource with the shortest queue:

```python
from prodsys.models.source_data import RoutingHeuristic

source_1.routing_heuristic = RoutingHeuristic.shortest_queue

production_system.validate()
production_system.run(1000)
production_system.runner.print_results()
```

## prodsys.models API

So far, we only studied the express API of `prodsys`. However, `prodsys` also provides a more detailed API that allows to model more complex production systems with `prodsys.models`. The models API uses ID references for connecting the different entities (processes, products, resources etc.) that results in a flat data structure instead of nested hierarchical relationsship, as the express API. Whilst the hierarchical structure is easy for programmatically creating production systems, the flat data structure is more convenient for serializing the data, i.e. saving and loading production systems. All algorithms in `prodsys` use the models API. For luck, all express API objects can be converted to models API objects and vice versa.

```python
model_production_system = production_system.to_model()
print(model_production_system.process_data[0])
```

For now, the express API allows all modeling features as the models API but the creation of products that require processes in a sequence according to an assembly precedence graph. This feature is only available in the models API. For more information, refer to the API reference in the documentation. However, using the algorithms provided by `prodsys` for optimizing or autonomously controlling a production system requires the models API. For a complete overview of the package's modelling functionalities, please see the [API reference](../API_reference/API_reference_0_overview.md).
