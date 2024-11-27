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
- **SampleTimeModel**: A time model that is based on a sequence of time values that are randomly sampled.
- **ScheduledTimeModel**: A time model that is based on a schedule of time values. The schedule can contain relative or absulte time values. Also the schedule can be executed once or multiple times in a cycle.
- **DistanceTimeMOdel**: A time model that is based on th distance between two locations and a constant speed and reaction time. Manhattan distance or Euclidian distance can be used as distance metrics between the points.

We will use the `FunctionTimeModel` to model the time required for milling and turning processes and model the time needed for transport with the `DistanceTimeModel`. We will also model the arrival of housings with the `ScheduledTimeModel`, which could, e.g. be observed inter-arrival times:

```python
milling_time = psx.FunctionTimeModel(distribution_function="normal", location=1, scale=0.1, ID="milling_time")
turning_time = psx.FunctionTimeModel(distribution_function="normal", location=0.5, scale=0.1, ID="turning_time")
transport_time = psx.DistanceTimeModel(speed=200, reaction_time=0.05, metric="manhattan", ID="transport_time")
arrival_time_of_housing_1 = psx.ScheduledTimeModel([1.6, 1.3, 1.8, 2.0, 1.2, 1.7, 1.3], absolute=False, cyclic=True, ID="arrival_time_of_housings")
arrival_time_of_housing_2 = psx.ScheduledTimeModel([1.3, 2.3, 2.1, 2.0, 1.4], absolute=False, cyclic=True, ID="arrival_time_of_housings")
```

Note, the `ManhattanDistanceTimeModel` and the `SequentialTimeModel` are deprecated. The `ManhattanDistanceTimeModel` is replaced by the `DistanceTimeModel` and the `SequentialTimeModel` is replaced by the `SampleTimeModel`.

## Processes

After creating the time models, we can define the processes in the system. We will use the `ProductionProcess` to model the milling and turning processes and the `TransportProcess` to model the transport process:

```python
milling_process = psx.ProductionProcess(milling_time, ID="milling_process")
turning_process = psx.ProductionProcess(turning_time, ID="turning_process")
transport_process = psx.TransportProcess(transport_time, ID="transport_process")
```

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


## Advanced modeling features

### Capability Processes


`prodsys` also provides the possibility for a `CapabilityProcess` instead of normal `ProductionProcess`. These processes are not matched by their ID but by their capability, which gives more flexibility in modeling the operations of a production system. 

The capabilities extends the typical PPR modeling principle (Product, Process and Resource) of `prodsys` to the Product, Process, Resource and Skill modelling principle [PPRS](https://publica-rest.fraunhofer.de/server/api/core/bitstreams/512978c9-389a-43c1-8cbe-016f08e6952d/content) by considering the capabilities / skills required for performing processes. 

One typical use case where this capability-based modeling is useful is when a product requires a certain process but multiple resources can perform this process with different speeds or capacity.

In prodsys, we can realize this by specifying with a `RequiredCapabilityProcess` for a product which kind of capabilities are required for its production. Additionally, we define multiple different `CapabilityProcess` for resources that satisfy the capability and therefore can perform the process on the prodct. During simulation, processes of resources are matchedto the required processes based on a comparison of the capability attribute. 

For example, we could define the following case, where a turning process is required by a product and two machines are available that can perform this process, but with different speeds:

```python
import prodsys.express as psx
from prodsys.express import production_system

time_model_agv = psx.DistanceTimeModel(speed=90, reaction_time=0.2, ID="time_model_x")
transport_process = psx.TransportProcess(
    time_model=time_model_agv, ID="transport_process"
)
agv = psx.TransportResource(ID="agv", processes=[transport_process], location=[5, 5])

time_model_turning_fast = psx.FunctionTimeModel(
    distribution_function="constant", location=6, ID="time_model_turning_fast"
)
time_model_turning_slow = psx.FunctionTimeModel(
    distribution_function="constant", location=9, ID="time_model_turning_slow"
)

capability_process_turning_fast = psx.CapabilityProcess(
    time_model=time_model_turning_fast, capability="turning", ID="cp_turning_fast"
)
capability_process_turning_slow = psx.CapabilityProcess(
    time_model=time_model_turning_slow, capability="turning", ID="cp_turning_slow"
)

resource_fast = psx.ProductionResource(
    ID="resource_fast", processes=[capability_process_turning_fast], location=[5, 0]
)
resource_slow = psx.ProductionResource(
    ID="resource_slow", processes=[capability_process_turning_slow], location=[5, 10]
)

required_capability_process_turning = psx.RequiredCapabilityProcess(
    capability="turning", ID="rcp_turning"
)

product = psx.Product(
    processes=[required_capability_process_turning],
    transport_process=transport_process,
    ID="product",
)

source = psx.Source(
    time_model=psx.FunctionTimeModel(
        distribution_function="constant", location=6, ID="interarrival_time_model"
    ),
    ID="source",
    product=product,
    location=[0, 5],
)

sink = psx.Sink(ID="sink", product=product, location=[10, 5])

system = production_system.ProductionSystem(
    resources=[resource_fast, resource_slow, agv], sources=[source], sinks=[sink]
)

system.validate()
system.run(1000)
system.runner.print_results()
```

In this example, we model the `RequiredCapabilityProcess` of the product by stating, it requires the capability "turning":

```python
required_capability_process_turning = psx.RequiredCapabilityProcess(
    capability="turning", ID="rcp_turning"
)
product = psx.Product(
    processes=[required_capability_process_turning],
    transport_process=transport_process,
    ID="product",
)
```

Of course, we could extend the process sequence of the product with other processes, both CapabilityProcesses and normal processes.

To specify that two resources can perform this process with different speed, we define two time models, two `CapabilityProcess` with the capability "turning" and two `ProductionResource`s with the processes:

```python
time_model_turning_fast = psx.FunctionTimeModel(
    distribution_function="constant", location=6, ID="time_model_turning_fast"
)
time_model_turning_slow = psx.FunctionTimeModel(
    distribution_function="constant", location=9, ID="time_model_turning_slow"
)
capability_process_turning_fast = psx.CapabilityProcess(
    time_model=time_model_turning_fast, capability="turning", ID="cp_turning_fast"
)
capability_process_turning_slow = psx.CapabilityProcess(
    time_model=time_model_turning_slow, capability="turning", ID="cp_turning_slow"
)

resource_fast = psx.ProductionResource(
    ID="resource_fast", processes=[capability_process_turning_fast], location=[5, 0]
)
resource_slow = psx.ProductionResource(
    ID="resource_slow", processes=[capability_process_turning_slow], location=[5, 10]
)
```

With this, we can achieve that the product is processed on both machines, but with different speeds.

Moreover, there also exists a `LinkTransportProcess` which allows to define that a transport process can only be performed between certain resources. This allows to make transport in `prodsys` more realistic. 

For more information, refer to the API reference in the documentation or checkout the examples folder of `prodsys`.

### Further modeling concepts

For more complex use cases that need to consider more aspects of a real production system, prodsys contains some handy features. Modeling concepts that are not yet described in the tutorial are:

- **Queues and Storages**: If you need to specifically restrict the size of resources queues or storages that contain products, you can manually define them with the `Queue`. The queues can be placed at different locations in the production system.
- **Nodes and Links**: If you need to model a more complex production system with multiple locations and transport routes, you can use the `Node` class to define the locations and create links with a `LinkTransportProcess`.
- **Auxiliaries**: If some processes require supportive material (e.g. work piece carriers or tools), you can define them with the `Auxiliary` class. The auxiliaries can be used to model the transport of supportive material. 

Additionally, prodsys provides the possibility to define your own policies that control the decision making in the production system. With this you can integrate your own logic. The policies are:
- **Routing Policies**: You can create a function that orders a list of requests that contain all possibilities for routing a product to possible resources. Index 0 of the list is the first choice, index 1 the second choice and so on. The routing policy can be used to define the routing of products to resources.
- **Control Policies**: You can create a function that orders a list of requests that contain all possibilities for processing a product on a resource. Index 0 of the list is the first choice, index 1 the second choice and so on. The control policy can be used to define the sequence of processing of products on resources.

You can extended the default policies of prodsys by creating your own policies. For more information, refer to the API reference in the documentation or checkout the examples folder of prodsys. For more hands-on experience, you can also check out the examples in the prodsys [modeling and simulation examples folder](https://github.com/sdm4fzi/prodsys/tree/main/examples/modelling_and_simulation).
