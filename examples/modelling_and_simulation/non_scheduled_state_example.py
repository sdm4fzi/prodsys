"""
Example demonstrating Non-Scheduled states for shift modeling.

This example shows how to use NonScheduledState to model resources that are only
available during specific shifts. The NonScheduledState alternates between:
- Scheduled periods: Resource is available for operations
- Non-scheduled periods: Resource is unavailable (blocks all operations, similar to breakdown)

In this example, we model a machine that works in 8-hour shifts with 16-hour breaks.
"""

import prodsys.express as psx
import prodsys

print("version used:", prodsys.VERSION)
prodsys.set_logging("INFO")

# Time models for production processes
t1 = psx.FunctionTimeModel("normal", 1, 0.1, "t1")
t2 = psx.FunctionTimeModel("normal", 2, 0.2, "t2")

p1 = psx.ProductionProcess(t1, "p1")
p2 = psx.ProductionProcess(t2, "p2")

# Time model for transport
t3 = psx.DistanceTimeModel(speed=180, reaction_time=0.1, ID="t3")
tp = psx.TransportProcess(t3, "tp")

# Setup states
s1 = psx.FunctionTimeModel("exponential", 0.5, ID="s1")
setup_state_1 = psx.SetupState(s1, p1, p2, "S1")
setup_state_2 = psx.SetupState(s1, p2, p1, "S2")

# Non-Scheduled State: Models 8-hour shifts with 16-hour breaks
# Scheduled time model: 8 hours (when resource is available)
scheduled_time_model = psx.FunctionTimeModel(
    distribution_function="constant",
    location=8.0,  # 8 hours scheduled (shift duration)
    scale=0.0,
    ID="scheduled_time_model"
)

# Non-scheduled time model: 16 hours (when resource is unavailable)
non_scheduled_time_model = psx.FunctionTimeModel(
    distribution_function="constant",
    location=16.0,  # 16 hours non-scheduled (break between shifts)
    scale=0.0,
    ID="non_scheduled_time_model"
)

# Create NonScheduledState
non_scheduled_state = psx.NonScheduledState(
    time_model=scheduled_time_model,
    non_scheduled_time_model=non_scheduled_time_model,
    ID="shift_state"
)

# Machine with NonScheduledState (shift-based availability)
machine = psx.Resource(
    [p1, p2],
    [5, 0],
    2,
    states=[setup_state_1, setup_state_2, non_scheduled_state],
    ID="machine",
)

# Machine without NonScheduledState (always available for comparison)
machine2 = psx.Resource(
    [p1, p2],
    [7, 0],
    2,
    states=[setup_state_1, setup_state_2],
    ID="machine2",
)

transport = psx.Resource([tp], [2, 0], 1, ID="transport")

# Products
product1 = psx.Product([p1, p2], tp, "product1")
product2 = psx.Product([p2, p1], tp, "product2")

# Sinks
sink1 = psx.Sink(product1, [10, 0], "sink1")
sink2 = psx.Sink(product2, [10, 0], "sink2")

# Arrival models
arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")
arrival_model_2 = psx.FunctionTimeModel("exponential", 2, ID="arrival_model_2")

# Sources
source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")
source2 = psx.Source(product2, arrival_model_2, [0, 0], ID="source_2")

# Production system
system = psx.ProductionSystem(
    [machine, machine2, transport], [source1, source2], [sink1, sink2]
)

# Run simulation
model = system.to_model()

runner_instance = prodsys.runner.Runner(production_system_data=model)
runner_instance.initialize_simulation()
system.run(1000)  # Run for 1000 time units to see shift effects

runner_instance = system.runner

# Print and plot results
runner_instance.print_results()
runner_instance.plot_results()
runner_instance.save_results_as_csv()

print("\n" + "="*60)
print("Non-Scheduled State Example Summary")
print("="*60)
print("Machine 'machine' has a NonScheduledState that models:")
print("  - 8-hour scheduled periods (resource available)")
print("  - 16-hour non-scheduled periods (resource unavailable)")
print("  - This creates a shift pattern: 8h on, 16h off, repeating")
print("\nMachine 'machine2' has no NonScheduledState and is always available.")
print("Compare the utilization and throughput to see the impact of shifts.")
print("="*60)

