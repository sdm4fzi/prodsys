# Analyzing simulation results

In the following tutorial, we will explore the analysis capabilities of `prodsys` for examining simulation results. In `prodsys`, every single of a simulation run get's tracked and logged, thus allowing to review the complete event log of a simulation run, as in the real world. Similarly, all KPIs can be calculated in the post processing. This allows for a very flexible analysis of the simulation results. `prodsys` allready provides many utility functions for calculating KPIs and plotting the results. In this tutorial, we will explore some of them.

For this example, we will use another production system which we will load from a json-file (example_configuration.json), which can be found in the examples folder of [prodsys' github page](https://github.com/sdm4fzi/prodsys/tree/main/examples/tutorials). Download it and store it in the same folder as this notebook. Load the configuration and run a simulation with the following commands:

```python
import prodsys

production_system = prodsys.adapters.ProductionSystemData()
production_system.read_data('example_configuration.json')

runner = prodsys.runner.Runner(adapter=production_system)
runner.initialize_simulation()
runner.run(20000)
runner.print_results()
```

When reviewing the simulation results, we will see that the production system consists of 4 prudction resources (R1, R2, R3, R4) and two transport resources (TR1, TR2). Additionally, we see that three different kind of products are produced (product_1, product_2, product_3). When reviewing the KPIs, there doesn't seem to be any problems with the production system. However, this is hard to tell without knowing something about the production system and we will see that there are some problems with the production system, which we will explore in the following.

The basic data structure used for logging all events can be accessed by the `EventLogger` class, which is an attribute of the runner. The logger stores this data in form of dictionaries but we can transform it to a pandas dataframe for more convenient analysis:

```python
df = runner.event_logger.get_data_as_dataframe()
df.head(10)
```

If we have a look at the dataframe, we will see that it contains 8 columns to describe each event:

- Time: The time of the event
- Resource: The resource on which the event occured
- State: The state of the resource that changed
- State Type: The type of the state that changed (e.g. source, transport, breakdwon, etc.)
- Activity: The activity that was performed
- Product: The product that was processed or transported (only for Production or Transport states)
- Expected End Time: The expected end time of the state
- Target location: The target location of a transport (only for Transport states)

Writing scripts that analysis these event logs can be tydious. We can use powerfull process mining tools to automate the analysis of these event logs to analysis all processes, event durations and so on. However, in this tutorial, we will focus on the analysis of the KPIs. For this, we will use the `PostProcessor` class, which can be obtained from runner. The `PostProcessor` class provides many utility functions for calculating KPIs and plotting the results. In this tutorial, we will explore some of them.
Let's get a `PostProcessor` from the runner and have a look at the KPIs:

```python
post_processor = runner.get_post_processor()
print("Throughput per product type:", post_processor.get_aggregated_throughput_data())
print("WIP per product type:", post_processor.get_aggregated_wip_data())
print("Throughput time per product type:", post_processor.get_aggregated_throughput_time_data())
```

`prodsys` also provides some models for KPIs which can be used more easily in algorithms. For example, we can use the `WIP_KPIs`property to calculate the KPI values of the production system:

```python
for wip_kpi in post_processor.WIP_KPIs:
    print("WIP KPI:", wip_kpi)
    print("WIP KPI value:", wip_kpi.value)
```

The `PostProcessor` has some pre-processed data frames, which can be used for custom analyis. For example, we can get a data frame with only products that have been finished during the simulation run:

```python
post_processor.df_finished_product.head()
```

However, most easiest or fastest method for analysing simulation results is using the plotting functionalities of `prodsys`. These can be accesses through the `kpi_visualization` and only require a `PostProcessor` for instantiation. For example, we can plot the time percentages of resources in different states:

```python
from prodsys.util import kpi_visualization

kpi_visualization.plot_time_per_state_of_resources(post_processor)
```

We can observe, that the resources in the production system are not really heavily utilized, since their productive (PR) percentage is lower than 50% for all resources but R2. Let's plot the WIP KPI and see if this aligns with our first observations:

```python
from prodsys.util import kpi_visualization

kpi_visualization.plot_WIP(post_processor)
```

We can see that the production system has at first a stable WIP at around a total of 7 but at roughly 5000 minutes, the WIP starts increasing and does not stabilize anymore. This suggest, that our system is running very full with semi-finished material. We can look more closely at the WIP when considering the WIP at the different resources over time:

``` python
kpi_visualization.plot_WIP_per_resource(post_processor)
```

When observing the WIP per resource, we can observe that WIP at the resources increase steadily until ca. 15500 minutes. Then, suddenly, the WIP curve stops. This is a strong indicator that a Deadlock occured, where all positions of the queues are full and transports are blocked, because their target is blocked. This, is caused as products can have re-entrant flow in this example, thus blocking each other. Let's also look at the throughput time of the products:

```python
kpi_visualization.plot_throughput_time_over_time(post_processor)
```

Again, we see a divergence of throughput time over simualted time. Here, the Start_time relates to the start of production of a product, i.e. the creation at it's source. These observations suggest, that the system is running to a WIP level which cannot be processed efficiently, similar to a crowded parking space after an event. If we take a look at the queue's of the system and the capacity of production resources, we can determine the maximal number of products in the system:

```python
capacity = 0
for resource in production_system.resource_data:
    capacity += resource.capacity

for queue in production_system.queue_data:
    capacity += queue.capacity

print(capacity)
```

We see, that at maximum 69 products can be in the production system in parallel. However, when we examine the queues more in detail, we see, that some resource share also queues (R3 and R4):

```python
machines = prodsys.adapters.get_machines(production_system)
for machine in machines:
    print(machine.ID, machine.input_queues, machine.output_queues)
```

Let's investigate if the production system's storage capacity for products is too low that there is some blocking or if the production system's throughput is not high enough for the arrival processes. To do this, we test how the WIP changes if we make the queues of the production system unlimited (capacity=0).

```python
adjusted_production_system = production_system.copy(deep=True)

for queue in adjusted_production_system.queue_data:
    queue.capacity = 0

runner = prodsys.runner.Runner(adapter=adjusted_production_system)
runner.initialize_simulation()
runner.run(20000)
new_post_processor = runner.get_post_processor()
kpi_visualization.plot_WIP(new_post_processor)
```

If we look at the results again, we see that the production system WIP increases not as strong as without limited queues. This suggests that both cases were True. At first, the production system got fuller without limited queues which suggest that some queues overflowed when limited causing some blocking. Additionally, we see that the WIP still increases over time, thus the production system requires more resources or another configuration to satisfy the arrival processes. `prodsys` provides also some functionality to optimize production system configuration. See the optimization example for more detailed information. For a complete overview of the package's ies for simulation analysis, please see the [API reference](../API_reference/API_reference_0_overview.md).
