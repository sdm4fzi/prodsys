# Orders and Schedules

This tutorial explores order-based production and schedule-based production control in `prodsys`. These features allow you to model production systems where products are released based on customer orders or predefined schedules.

## Order-Based Production

Order-based production allows you to model production systems where products are created based on customer orders rather than continuous arrival processes. This is useful for make-to-order scenarios.

### Creating Orders

An `Order` specifies what products should be produced, in what quantities, and when they should be released into the production system.

```python
import prodsys.express as psx

# Create time models and processes
t1 = psx.FunctionTimeModel("normal", 1, 0.1, "t1")
t2 = psx.FunctionTimeModel("normal", 2, 0.2, "t2")
p1 = psx.ProductionProcess(t1, "p1")
p2 = psx.ProductionProcess(t2, "p2")

t3 = psx.DistanceTimeModel(speed=180, reaction_time=0.1, ID="t3")
tp = psx.TransportProcess(t3, "tp")

# Create products
product1 = psx.Product(process=[p1, p2], transport_process=tp, ID="product1")
product2 = psx.Product(process=[p2, p1], transport_process=tp, ID="product2")

# Create an order with a single product type
order1 = psx.Order(
    ID="order1",
    ordered_products=[psx.OrderedProduct(product=product1, quantity=2)],
    order_time=0.0,      # When the order was placed
    release_time=10.0,   # When products should be released into the system
    priority=1,
)

# Create an order with multiple product types
order2 = psx.Order(
    ID="order2",
    ordered_products=[
        psx.OrderedProduct(product=product1, quantity=1),
        psx.OrderedProduct(product=product2, quantity=1),
    ],
    order_time=5.0,
    release_time=20.0,
    priority=1,
)
```

### Using OrderSource

An `OrderSource` creates products based on orders rather than a continuous arrival process. Products are released at the times specified in the orders.

```python
# Create order source with multiple orders
order_source = psx.OrderSource(
    orders=[order1, order2],
    location=[0, 0],
    ID="order_source",
)

# Create resources
machine = psx.Resource(
    processes=[p1, p2],
    location=[5, 0],
    capacity=2,
    ID="machine",
)
transport = psx.Resource(
    processes=[tp],
    location=[2, 0],
    capacity=1,
    ID="transport",
)

# Create sinks
sink1 = psx.Sink(product1, [10, 0], "sink1")
sink2 = psx.Sink(product2, [10, 0], "sink2")

# Create production system with order source
system = psx.ProductionSystem(
    resources=[machine, transport],
    sources=[order_source],
    sinks=[sink1, sink2]
)
```

### Combining Orders with ConWIP

You can combine order-based production with ConWIP (Constant Work in Progress) control to limit the number of products in the system:

```python
# Convert to model and set ConWIP limit
model = system.to_model()
model.conwip_number = 5  # Maximum 5 products in the system

# Run simulation
from prodsys.simulation import runner
runner_instance = runner.Runner(production_system_data=model)
runner_instance.initialize_simulation()
system.run(100)
system.runner.print_results()
```

## Schedule-Based Production

Schedule-based production allows you to define exactly when specific products should be released and which resources should process them. This is useful for production planning and scheduling scenarios.

### Creating a Schedule

A schedule is a list of schedule events that specify:
- **Time**: When the event should occur
- **Product**: Which product should be created/processed
- **Resource**: Which resource should process the product
- **Process**: Which process should be performed

```python
from prodsys.models import production_system_data

# Load a configuration with schedule
config = production_system_data.ProductionSystemData.read(
    "examples/modelling_and_simulation/simulation_example_data/schedule_example.json"
)

# The schedule is defined in the configuration file
# Each schedule event specifies:
# - time: When the event occurs
# - product: Product ID to create
# - resource: Resource ID that should process it
# - process: Process ID to perform

print(f"Number of scheduled events: {len(config.schedule) if config.schedule else 0}")
```

### Schedule Structure

A schedule event typically looks like this:

```json
{
    "time": 10.5,
    "product": "Product_A_1",
    "resource": "R1",
    "process": "P1"
}
```

This means: "At time 10.5, create Product_A_1 and route it to resource R1 to perform process P1."

### Running Schedule-Based Simulation

```python
from prodsys.simulation import runner

# Create and run the simulation
sim_runner = runner.Runner(production_system_data=config)
sim_runner.initialize_simulation()

# Calculate simulation time based on schedule
if config.schedule:
    max_schedule_time = max(event.time for event in config.schedule)
    simulation_time = max_schedule_time + 100  # Add buffer for processing
else:
    simulation_time = 2000

sim_runner.run(simulation_time)

# Analyze results
performance = sim_runner.get_performance_data()
print(f"Number of events in event log: {len(performance.event_log)}")
```

### Validating Schedule Adherence

You can validate that the simulation followed the schedule:

```python
# Get scheduled production starts
scheduled_releases = [
    e for e in performance.event_log 
    if e.activity == "start state" and e.state_type == "Production"
]

# Validate routing
for scheduled_event in config.schedule:
    actual_events = [
        e for e in scheduled_releases 
        if e.product == scheduled_event.product
        and hasattr(e, 'state') and e.state == scheduled_event.process
    ]
    
    if actual_events:
        actual_event = actual_events[0]
        scheduled_time = scheduled_event.time
        actual_time = actual_event.time
        delay = actual_time - scheduled_time
        
        print(f"Product {scheduled_event.product}: "
              f"Scheduled={scheduled_time:.2f}, "
              f"Actual={actual_time:.2f}, "
              f"Delay={delay:.2f}")
```

## Complete Example: Order-Based Production

Here's a complete example of order-based production:

```python
import prodsys.express as psx
import prodsys

# Create time models
t1 = psx.FunctionTimeModel("normal", 1, 0.1, "t1")
t2 = psx.FunctionTimeModel("normal", 2, 0.2, "t2")

# Create processes
p1 = psx.ProductionProcess(t1, "p1")
p2 = psx.ProductionProcess(t2, "p2")

t3 = psx.DistanceTimeModel(speed=180, reaction_time=0.1, ID="t3")
tp = psx.TransportProcess(t3, "tp")

# Create setup states
s1 = psx.FunctionTimeModel("exponential", 0.5, ID="s1")
setup_state_1 = psx.SetupState(s1, p1, p2, "S1")
setup_state_2 = psx.SetupState(s1, p2, p1, "S2")

# Create resources
machine = psx.Resource(
    processes=[p1, p2],
    location=[5, 0],
    capacity=2,
    states=[setup_state_1, setup_state_2],
    ID="machine",
)
machine2 = psx.Resource(
    processes=[p1, p2],
    location=[7, 0],
    capacity=2,
    states=[setup_state_1, setup_state_2],
    ID="machine2",
)
transport = psx.Resource(
    processes=[tp],
    location=[2, 0],
    capacity=1,
    ID="transport",
)

# Create products
product1 = psx.Product(process=[p1, p2], transport_process=tp, ID="product1")
product2 = psx.Product(process=[p2, p1], transport_process=tp, ID="product2")

# Create sinks
sink1 = psx.Sink(product1, [10, 0], "sink1")
sink2 = psx.Sink(product2, [10, 0], "sink2")

# Create orders with different release times
order1 = psx.Order(
    ID="order1",
    ordered_products=[psx.OrderedProduct(product=product1, quantity=2)],
    order_time=0.0,
    release_time=10.0,
    priority=1,
)

order2 = psx.Order(
    ID="order2",
    ordered_products=[psx.OrderedProduct(product=product2, quantity=1)],
    order_time=5.0,
    release_time=15.0,
    priority=1,
)

# Order with multiple product types
order3 = psx.Order(
    ID="order3",
    ordered_products=[
        psx.OrderedProduct(product=product1, quantity=1),
        psx.OrderedProduct(product=product2, quantity=1),
    ],
    order_time=10.0,
    release_time=20.0,
    priority=1,
)

# Create order source
order_source = psx.OrderSource(
    orders=[order1, order2, order3],
    location=[0, 0],
    ID="order_source",
)

# Create production system
system = psx.ProductionSystem(
    resources=[machine, machine2, transport],
    sources=[order_source],
    sinks=[sink1, sink2]
)

# Set ConWip limit
model = system.to_model()
model.conwip_number = 5

# Run simulation
from prodsys.simulation import runner
runner_instance = runner.Runner(production_system_data=model)
runner_instance.initialize_simulation()
system.run(100)
system.runner.print_results()
```

## Key Points

1. **Order-based production**: Use `OrderSource` with `Order` objects to model make-to-order scenarios where products are created based on customer orders.

2. **Schedule-based production**: Use schedules to define exactly when and where products should be processed, useful for production planning and scheduling.

3. **Order properties**:
   - `order_time`: When the order was placed
   - `release_time`: When products should be released into the system
   - `priority`: Order priority (higher values = higher priority)
   - `ordered_products`: List of products and quantities

4. **ConWIP control**: Combine orders with ConWIP to limit work in progress.

5. **Schedule validation**: You can validate that the simulation followed the schedule by comparing scheduled events with actual events in the event log.

For more information about orders and schedules, please see the [API reference](../API_reference/API_reference_0_overview.md) or check out the examples in the [modelling and simulation examples folder](https://github.com/sdm4fzi/prodsys/tree/main/examples/modelling_and_simulation).

