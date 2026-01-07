# System Resources

This tutorial explores `SystemResource`, a powerful feature in `prodsys` that allows you to model hierarchical production systems where a resource contains other resources as subresources. This is useful for modeling manufacturing cells, production lines, or complex workstations.

## Overview

A `SystemResource` represents a resource that contains other resources (subresources) and can perform processes that are distributed across its subresources. This allows you to:

- Model manufacturing cells with multiple machines
- Create hierarchical production systems
- Group related resources together
- Model complex workstations with internal routing

## Basic SystemResource

A basic `SystemResource` contains a list of subresource IDs and can perform processes that are executed by its subresources.

```python
import prodsys.express as psx

# Create time models
tm_machine1 = psx.FunctionTimeModel("normal", 1.8, 0.2, "tm_machine1")
tm_machine2 = psx.FunctionTimeModel("normal", 2.2, 0.7, "tm_machine2")
tm_transport = psx.DistanceTimeModel(speed=60, reaction_time=0.1, metric="manhattan", ID="tm_transport")
tm_arrival = psx.FunctionTimeModel("exponential", 2.5, ID="tm_arrival")

# Create processes
machine1_process = psx.ProductionProcess(time_model=tm_machine1, ID="machine1_process")
machine2_process = psx.ProductionProcess(time_model=tm_machine2, ID="machine2_process")
transport_process = psx.TransportProcess(time_model=tm_transport, ID="transport_process")

# Create individual machine resources
machine1 = psx.ProductionResource(
    processes=[machine1_process],
    location=[12, 8],
    capacity=1,
    ID="machine1"
)

machine2 = psx.ProductionResource(
    processes=[machine2_process],
    location=[12, 12],
    capacity=1,
    ID="machine2"
)

# Create a ProcessModel for the cell
# This defines how processes are executed within the system resource
cell_process_model = psx.ProcessModel(
    adjacency_matrix={
        "machine1_process": ["machine2_process"],
        "machine2_process": []
    },
    ID="cell_process_model"
)

# Create SystemResource (manufacturing cell)
manufacturing_cell = psx.SystemResource(
    processes=[cell_process_model],
    location=[10, 10],
    subresource_ids=["machine1", "machine2"],
    capacity=5,  # Capacity of the system resource
    ID="manufacturing_cell"
)
```

## SystemResource with ProcessModel

A `SystemResource` typically uses a `ProcessModel` to define how processes are executed across its subresources. The `ProcessModel` can represent sequential, parallel, or complex workflows.

```python
# Create a ProcessModel with parallel execution
# Workflow: machine1_process OR machine2_process (parallel choice)
cell_process_model = psx.ProcessModel(
    adjacency_matrix={
        "machine1_process": [],
        "machine2_process": []
    },
    ID="cell_process_model"
)

# Create SystemResource with the process model
manufacturing_cell = psx.SystemResource(
    processes=[cell_process_model],
    location=[10, 10],
    subresource_ids=["machine1", "machine2"],
    capacity=5,
    ID="manufacturing_cell"
)
```

## Nested SystemResources

You can create nested `SystemResource` objects where a system resource contains other system resources:

```python
# Create a ProcessModel for the outer system resource
product_process_model = psx.ProcessModel(
    can_contain_other_models=True,
    ID="product_process_model",
    adjacency_matrix={
        "machine3_process": ["cell_process_model"],
        "cell_process_model": []
    }
)

# Create outer system resource that contains the manufacturing cell
outer_system = psx.SystemResource(
    processes=[product_process_model],
    location=[15, 10],
    subresource_ids=["machine3", "manufacturing_cell"],
    capacity=10,
    ID="outer_system"
)
```

## SystemResource with Robot

A common use case is a manufacturing cell with a robot that loads and unloads products:

```python
# Create robot time model
tm_robot_handling = psx.FunctionTimeModel(
    distribution_function="normal",
    location=5.0,
    scale=1.0,
    ID="tm_robot_handling"
)

# Create robot process
robot_handling_process = psx.TransportProcess(
    time_model=tm_robot_handling,
    ID="robot_handling"
)

# Create robot resource
robot = psx.ProductionResource(
    processes=[transport_process],  # Robot can also transport
    location=[12, 10],
    capacity=1,
    ID="robot"
)

# Create ProcessModel for the cell
# Workflow: robot loads → (machine1 OR machine2) → robot unloads
cell_process_model = psx.ProcessModel(
    adjacency_matrix={
        "machine1_process": [],
        "machine2_process": []
    },
    ID="cell_process_model"
)

# Create SystemResource with robot and machines
manufacturing_cell = psx.SystemResource(
    processes=[cell_process_model],
    location=[10, 10],
    subresource_ids=["robot", "machine1", "machine2"],
    capacity=5,
    ID="manufacturing_cell"
)
```

## Complete Example: Manufacturing Cell

Here's a complete example of a manufacturing cell with a robot and multiple machines:

```python
import prodsys.express as psx

def main():
    """Main example function."""
    
    # ========== TIME MODELS ==========
    # Robot time models
    tm_robot_handling = psx.FunctionTimeModel(
        distribution_function="normal",
        location=5.0,
        scale=1.0,
        ID="tm_robot_handling"
    )
    
    # Machine time models
    tm_machine1 = psx.FunctionTimeModel(
        distribution_function="normal",
        location=1.8,
        scale=0.2,
        ID="tm_machine1"
    )
    tm_machine2 = psx.FunctionTimeModel(
        distribution_function="normal",
        location=2.2,
        scale=0.7,
        ID="tm_machine2"
    )
    
    # Transport and arrival time models
    tm_agv = psx.DistanceTimeModel(
        speed=60.0,
        reaction_time=0.1,
        metric="manhattan",
        ID="tm_agv"
    )
    tm_arrival = psx.FunctionTimeModel(
        distribution_function="exponential",
        location=2.5,
        ID="tm_arrival"
    )
    
    # ========== PROCESSES ==========
    # Machine processes
    machine1_process = psx.ProductionProcess(
        time_model=tm_machine1,
        ID="machine1_process"
    )
    machine2_process = psx.ProductionProcess(
        time_model=tm_machine2,
        ID="machine2_process"
    )
    
    # Transport process
    agv_transport = psx.TransportProcess(
        time_model=tm_agv,
        ID="agv_transport"
    )
    
    # ========== PROCESS MODEL ==========
    # Create ProcessModel with parallel execution
    # Workflow: (machine1_process OR machine2_process)
    cell_process_model = psx.ProcessModel(
        adjacency_matrix={
            "machine1_process": [],
            "machine2_process": []
        },
        ID="cell_process_model"
    )
    
    # Product process model that includes the cell
    product_process_model = psx.ProcessModel(
        can_contain_other_models=True,
        ID="product_process_model",
        adjacency_matrix={
            "cell_process_model": []
        }
    )
    
    # ========== RESOURCES ==========
    # Robot resource
    robot = psx.ProductionResource(
        processes=[agv_transport],
        location=[12, 10],
        capacity=1,
        ID="robot"
    )
    
    # Machine resources
    machine1 = psx.ProductionResource(
        processes=[machine1_process],
        location=[12, 8],
        capacity=1,
        ID="machine1"
    )
    machine2 = psx.ProductionResource(
        processes=[machine2_process],
        location=[12, 12],
        capacity=1,
        ID="machine2"
    )
    
    # AGV for global transport
    agv = psx.TransportResource(
        processes=[agv_transport],
        location=[0, 10],
        capacity=1,
        ID="agv"
    )
    
    # ========== SYSTEM RESOURCE (CELL) ==========
    manufacturing_cell = psx.SystemResource(
        processes=[cell_process_model],
        location=[10, 10],
        subresource_ids=["robot", "machine1", "machine2"],
        capacity=5,
        ID="manufacturing_cell"
    )
    
    # ========== PRODUCT ==========
    product = psx.Product(
        process=product_process_model,
        transport_process=agv_transport,
        ID="product"
    )
    
    # ========== SOURCES AND SINKS ==========
    source = psx.Source(product, tm_arrival, [0, 10], ID="source")
    sink = psx.Sink(product, [20, 10], ID="sink")
    
    # ========== PRODUCTION SYSTEM ==========
    system = psx.ProductionSystem(
        resources=[robot, machine1, machine2, manufacturing_cell, agv],
        sources=[source],
        sinks=[sink],
        ID="production_system"
    )
    
    # ========== VALIDATION AND SIMULATION ==========
    system.validate()
    system.run(1000)
    system.runner.print_results()
```

## Key Points

1. **Subresources**: A `SystemResource` contains other resources (subresources) identified by their IDs.

2. **ProcessModel**: A `SystemResource` typically uses a `ProcessModel` to define how processes are executed across its subresources.

3. **Capacity**: The `SystemResource` has its own capacity, which limits how many products can be in the system resource at once.

4. **Hierarchical modeling**: You can create nested `SystemResource` objects for complex hierarchical production systems.

5. **Internal routing**: The `ProcessModel` defines how products are routed between subresources within the system resource.

6. **Location**: The `SystemResource` has a location, but subresources can have their own locations relative to the system resource.

## Use Cases

- **Manufacturing cells**: Model cells with multiple machines and a robot
- **Production lines**: Group related resources together
- **Workstations**: Model complex workstations with internal processes
- **Hierarchical systems**: Create multi-level production systems

For more information about system resources, please see the [API reference](../API_reference/API_reference_0_overview.md) or check out the examples in the [modelling and simulation examples folder](https://github.com/sdm4fzi/prodsys/tree/main/examples/modelling_and_simulation).

