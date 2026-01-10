# Advanced Dependencies

This tutorial explores advanced dependency modeling in `prodsys`. Dependencies allow you to model complex interactions between resources, processes, and products, such as assembly operations, worker requirements, tool dependencies, and lot-based processing.

## Overview of Dependency Types

`prodsys` supports several types of dependencies:

- **ProcessDependency**: A resource requires a specific process to be performed by another resource (e.g., assembly operations)
- **ResourceDependency**: A resource requires another resource to be available (e.g., a machine needs a worker)
- **AssemblyDependency**: A process requires specific products/components to be available (e.g., assembly needs screws and bolts)
- **ToolDependency**: A process requires a tool or auxiliary resource (e.g., workpiece carriers)
- **LotDependency**: A process requires products to be processed in batches/lots

## ProcessDependency

A `ProcessDependency` models situations where a resource needs another resource to perform a specific process. For example, a machine might need a worker to perform an assembly operation.

```python
import prodsys.express as psx

# Create time models
t1 = psx.FunctionTimeModel("normal", 1, 0.1, "t1")
t2 = psx.FunctionTimeModel("normal", 2, 0.2, "t2")

# Create processes
p1 = psx.ProductionProcess(t1, "p1")
p2 = psx.ProductionProcess(t2, "p2")

# Create transport process
t3 = psx.DistanceTimeModel(speed=180, reaction_time=0.1, ID="t3")
tp = psx.TransportProcess(t3, "tp")
move_p = psx.TransportProcess(t3, "move")

# Create assembly process
assembly_process = psx.ProductionProcess(
    psx.FunctionTimeModel("exponential", 0.1, ID="assembly_time"), 
    "assembly_process"
)

# Create worker resource that can perform assembly
worker = psx.Resource(
    processes=[move_p, assembly_process],
    location=[2, 0],
    capacity=1,
    ID="worker"
)

# Create interaction node where the dependency interaction occurs
interaction_node = psx.Node(location=[5, 6], ID="interaction_node_assembly")

# Create process dependency: machine requires assembly process from worker
assembly_dependency = psx.ProcessDependency(
    ID="assembly_dependency",
    required_process=assembly_process,
    interaction_node=interaction_node,
)

# Create machine with the dependency
machine = psx.Resource(
    processes=[p1, p2],
    location=[5, 5],
    capacity=1,
    dependencies=[assembly_dependency],
    ID="machine"
)
```

## ResourceDependency

A `ResourceDependency` models situations where a resource requires another resource to be available. This is useful for modeling worker-machine interactions or resource sharing scenarios.

```python
# Create worker resource
worker2 = psx.Resource(
    processes=[move_p, assembly_process],
    location=[3, 0],
    capacity=1,
    ID="worker2"
)

# Create interaction node
interaction_node_resource = psx.Node(location=[7, 4], ID="interaction_node_resource_2")

# Create resource dependency: machine2 requires worker2
resource_2_dependency = psx.ResourceDependency(
    ID="resource_2_dependency",
    required_resource=worker2,
    interaction_node=interaction_node_resource,
)

# Create machine with resource dependency
machine2 = psx.Resource(
    processes=[p1, p2],
    location=[7, 2],
    capacity=3,
    dependencies=[resource_2_dependency],
    ID="machine2"
)
```

## AssemblyDependency

An `AssemblyDependency` models situations where a process requires specific products or components to be available. This is essential for modeling assembly operations.

```python
# Create time models for primitive components
t_screw = psx.FunctionTimeModel("normal", 2, 0.2, "t_screw")
t_bolt = psx.FunctionTimeModel("normal", 3, 0.3, "t_bolt")
t_washer = psx.FunctionTimeModel("normal", 1, 0.1, "t_washer")

# Create processes for primitives
p_screw = psx.ProductionProcess(t_screw, "p_screw")
p_bolt = psx.ProductionProcess(t_bolt, "p_bolt")
p_washer = psx.ProductionProcess(t_washer, "p_washer")

# Create transport process
t_transport = psx.DistanceTimeModel(speed=100, reaction_time=0.1, ID="t_transport")
tp = psx.TransportProcess(t_transport, "tp")

# Create primitive products
screw = psx.Product(process=[p_screw], transport_process=tp, ID="screw")
bolt = psx.Product(process=[p_bolt], transport_process=tp, ID="bolt")
washer = psx.Product(process=[p_washer], transport_process=tp, ID="washer")

# Create assembly dependencies
screw_dependency = psx.AssemblyDependency(required_entity=screw)
bolt_dependency = psx.AssemblyDependency(required_entity=bolt)

# Create subassembly process with dependencies
t_subassembly = psx.FunctionTimeModel("normal", 5, 0.5, "t_subassembly")
p_subassembly = psx.ProductionProcess(
    t_subassembly, 
    "p_subassembly",
    dependencies=[screw_dependency, bolt_dependency]
)

# Create subassembly product
subassembly = psx.Product(
    process=[p_subassembly], 
    transport_process=tp, 
    ID="subassembly"
)

# Create main assembly with subassembly and washer dependencies
subassembly_dependency = psx.AssemblyDependency(required_entity=subassembly)
washer_dependency = psx.AssemblyDependency(required_entity=washer)

t_main_assembly = psx.FunctionTimeModel("normal", 10, 1.0, "t_main_assembly")
p_main_assembly = psx.ProductionProcess(
    t_main_assembly,
    "p_main_assembly",
    dependencies=[subassembly_dependency, washer_dependency]
)

# Create main assembly product
main_assembly = psx.Product(
    process=[p_main_assembly], 
    transport_process=tp, 
    ID="main_assembly"
)
```

## ToolDependency

A `ToolDependency` models situations where a process requires a tool or auxiliary resource, such as workpiece carriers, fixtures, or other supporting equipment.

```python
# Create transport process for workpiece carrier
t3 = psx.DistanceTimeModel(60, 0.05, "manhattan", ID="t3")
tp = psx.TransportProcess(t3, "tp")

# Create storage for workpiece carriers
storage1 = psx.Store(ID="storage1", location=[6, 0], capacity=30)
storage2 = psx.Store(ID="storage2", location=[11, 0], capacity=20)

# Create workpiece carrier primitive
workpiece_carrier = psx.Primitive(
    ID="workpiece_carrier",
    transport_process=tp,
    storages=[storage1, storage2],
    quantity_in_storages=[5, 20],
)

# Create tool dependency
workpiece_carrier_dependency = psx.ToolDependency(
    ID="workpiece_carrier_dependency",
    required_entity=workpiece_carrier,
)

# Create product with tool dependency
product1 = psx.Product(
    process=[p1],
    transport_process=tp,
    ID="product1",
    dependencies=[workpiece_carrier_dependency],
)
```

## LotDependency

A `LotDependency` models situations where products must be processed in batches or lots. This is useful for modeling batch processing, where multiple products are processed together.

```python
# Create lot dependency for batch processing
lot_dependency = psx.LotDependency(
    min_lot_size=2,
    max_lot_size=4,
    ID="lot_dependency",
)

# Create machine with lot dependency
machine = psx.Resource(
    processes=[p1],
    location=[5, 0],
    capacity=5,
    ID="machine",
    dependencies=[lot_dependency],
)

# Alternatively, lot dependency can be added to transport process
tp_with_lot = psx.TransportProcess(
    t3, 
    "tp", 
    dependencies=[lot_dependency]
)
```

## Complete Example: Assembly with Worker Dependency

Here's a complete example combining multiple dependency types:

```python
import prodsys.express as psx
from prodsys import runner

# Time models
t_screw = psx.FunctionTimeModel("normal", 2, 0.2, "t_screw")
t_bolt = psx.FunctionTimeModel("normal", 3, 0.3, "t_bolt")
t_washer = psx.FunctionTimeModel("normal", 1, 0.1, "t_washer")
t_transport = psx.DistanceTimeModel(speed=100, reaction_time=0.1, ID="t_transport")

# Processes
p_screw = psx.ProductionProcess(t_screw, "p_screw")
p_bolt = psx.ProductionProcess(t_bolt, "p_bolt")
p_washer = psx.ProductionProcess(t_washer, "p_washer")
tp = psx.TransportProcess(t_transport, "tp")

# Primitive products
screw = psx.Product(process=[p_screw], transport_process=tp, ID="screw")
bolt = psx.Product(process=[p_bolt], transport_process=tp, ID="bolt")
washer = psx.Product(process=[p_washer], transport_process=tp, ID="washer")

# Assembly dependencies
screw_dependency = psx.AssemblyDependency(required_entity=screw)
bolt_dependency = psx.AssemblyDependency(required_entity=bolt)

# Subassembly process
t_subassembly = psx.FunctionTimeModel("normal", 5, 0.5, "t_subassembly")
p_subassembly = psx.ProductionProcess(
    t_subassembly, 
    "p_subassembly",
    dependencies=[screw_dependency, bolt_dependency]
)
subassembly = psx.Product(process=[p_subassembly], transport_process=tp, ID="subassembly")

# Main assembly dependencies
subassembly_dependency = psx.AssemblyDependency(required_entity=subassembly)
washer_dependency = psx.AssemblyDependency(required_entity=washer)

# Main assembly process
t_main_assembly = psx.FunctionTimeModel("normal", 10, 1.0, "t_main_assembly")
p_main_assembly = psx.ProductionProcess(
    t_main_assembly,
    "p_main_assembly",
    dependencies=[subassembly_dependency, washer_dependency]
)
main_assembly = psx.Product(process=[p_main_assembly], transport_process=tp, ID="main_assembly")

# Worker resource
worker_process = psx.ProductionProcess(
    psx.FunctionTimeModel("exponential", 0.5, ID="worker_process_time"),
    "worker_process"
)
worker_transport = psx.TransportProcess(t_transport, "worker_transport")
from prodsys.models.resource_data import TransportControlPolicy
worker = psx.Resource(
    processes=[worker_transport, worker_process, tp],
    location=[1, 1],
    capacity=1,
    control_policy=TransportControlPolicy.SPT_transport,
    ID="worker",
)

# Resource dependency: assembly station requires worker
interaction_node = psx.Node(location=[5, 5], ID="interaction_node")
worker_dependency = psx.ResourceDependency(
    ID="worker_dependency",
    required_resource=worker,
    interaction_node=interaction_node,
)

# Assembly station with worker dependency
assembly_station = psx.Resource(
    processes=[p_subassembly, p_main_assembly, p_screw, p_bolt, p_washer],
    location=[5, 5],
    capacity=1,
    ID="assembly_station",
    dependencies=[worker_dependency],
)

# Create sources, sinks, and production system
arrival_model = psx.FunctionTimeModel("exponential", 30, ID="arrival_model")
source_screw = psx.Source(screw, arrival_model, [0, 0], ID="source_screw")
source_bolt = psx.Source(bolt, arrival_model, [0, 0], ID="source_bolt")
source_washer = psx.Source(washer, arrival_model, [0, 0], ID="source_washer")

sink_main_assembly = psx.Sink(main_assembly, [10, 5], "sink_main_assembly")

system = psx.ProductionSystem(
    resources=[assembly_station, worker],
    sources=[source_screw, source_bolt, source_washer],
    sinks=[sink_main_assembly],
)

# Run simulation
model = system.to_model()
runner_instance = runner.Runner(production_system_data=model)
runner_instance.initialize_simulation()
runner_instance.run(1000)
runner_instance.print_results()
```

## Key Points

1. **Dependencies create constraints**: They ensure that required resources, processes, or products are available before a process can start.

2. **Interaction nodes**: For `ProcessDependency` and `ResourceDependency`, you must specify an `interaction_node` where the dependency interaction occurs.

3. **Assembly dependencies**: Use `AssemblyDependency` to model bill-of-materials relationships where products require components.

4. **Tool dependencies**: Use `ToolDependency` for auxiliary resources like workpiece carriers, fixtures, or tools.

5. **Lot dependencies**: Use `LotDependency` to model batch processing where multiple products are processed together.

For more information about dependencies and their usage, please see the [API reference](../API_reference/API_reference_0_overview.md) or check out the examples in the [modelling and simulation examples folder](https://github.com/sdm4fzi/prodsys/tree/main/examples/modelling_and_simulation).

