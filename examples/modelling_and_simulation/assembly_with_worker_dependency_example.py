"""
Example demonstrating a simple assembly system with:
- Primitives (basic components)
- A subassembly consisting of primitives
- A main assembly that depends on the subassembly
- One assembly station that requires a worker as a dependency for all assemblies
"""

import prodsys.express as psx
from prodsys import runner

# Time models for primitive production
t_screw = psx.FunctionTimeModel("normal", 2, 0.2, "t_screw")
t_bolt = psx.FunctionTimeModel("normal", 3, 0.3, "t_bolt")
t_washer = psx.FunctionTimeModel("normal", 1, 0.1, "t_washer")

# Production processes for primitives
p_screw = psx.ProductionProcess(t_screw, "p_screw")
p_bolt = psx.ProductionProcess(t_bolt, "p_bolt")
p_washer = psx.ProductionProcess(t_washer, "p_washer")

# Transport process
t_transport = psx.DistanceTimeModel(speed=100, reaction_time=0.1, ID="t_transport")
tp = psx.TransportProcess(t_transport, "tp")

# Create primitive products
screw = psx.Product([p_screw], tp, "screw")
bolt = psx.Product([p_bolt], tp, "bolt")
washer = psx.Product([p_washer], tp, "washer")

# Time models for assembly processes
t_subassembly = psx.FunctionTimeModel("normal", 5, 0.5, "t_subassembly")
t_main_assembly = psx.FunctionTimeModel("normal", 10, 1.0, "t_main_assembly")

# Create dependencies for subassembly (requires screw and bolt)
screw_dependency = psx.PrimitiveDependency(required_primitive=screw)
bolt_dependency = psx.PrimitiveDependency(required_primitive=bolt)

# Production process for subassembly with primitive dependencies
p_subassembly = psx.ProductionProcess(
    t_subassembly, 
    "p_subassembly",
    dependencies=[screw_dependency, bolt_dependency]
)

# Create subassembly product
subassembly = psx.Product([p_subassembly], tp, "subassembly")

# Create dependency for main assembly (requires subassembly and washer)
subassembly_dependency = psx.PrimitiveDependency(required_primitive=subassembly)
washer_dependency = psx.PrimitiveDependency(required_primitive=washer)

# Production process for main assembly with dependencies
p_main_assembly = psx.ProductionProcess(
    t_main_assembly,
    "p_main_assembly",
    dependencies=[subassembly_dependency, washer_dependency]
)

# Create main assembly product
main_assembly = psx.Product([p_main_assembly], tp, "main_assembly")

# Create worker resource (required for assembly operations)
worker_process = psx.ProductionProcess(
    psx.FunctionTimeModel("exponential", 0.5, ID="worker_process_time"),
    "worker_process"
)
worker_transport = psx.TransportProcess(t_transport, "worker_transport")
from prodsys.models.resource_data import TransportControlPolicy
worker = psx.Resource(
    [worker_transport, worker_process, tp],
    [1, 1],
    1,
    control_policy=TransportControlPolicy.SPT_transport,
    ID="worker",
)

# Create interaction node for worker dependency
interaction_node = psx.Node(location=[5, 5], ID="interaction_node")

# Create resource dependency: assembly station requires worker
worker_dependency = psx.ResourceDependency(
    ID="worker_dependency",
    required_resource=worker,
    interaction_node=interaction_node,
)

# Create assembly station (one station that performs both subassembly and main assembly)
# This station requires the worker for all assembly operations
assembly_station = psx.Resource(
    [p_subassembly, p_main_assembly, p_screw, p_bolt, p_washer],
    [5, 5],
    1,
    ID="assembly_station",
    dependencies=[worker_dependency],
    output_location=[5, 5],
)


# Create sinks
sink_screw = psx.Sink(screw, [10, 0], "sink_screw")
sink_bolt = psx.Sink(bolt, [10, 0], "sink_bolt")
sink_washer = psx.Sink(washer, [10, 0], "sink_washer")
sink_subassembly = psx.Sink(subassembly, [10, 5], "sink_subassembly")
sink_main_assembly = psx.Sink(main_assembly, [10, 5], "sink_main_assembly")

# Create sources for primitives
arrival_model = psx.FunctionTimeModel("constant", 5, ID="arrival_model")

source_screw = psx.Source(screw, arrival_model, [0, 0], ID="source_screw")
source_bolt = psx.Source(bolt, arrival_model, [0, 0], ID="source_bolt")
source_washer = psx.Source(washer, arrival_model, [0, 0], ID="source_washer")

subassembly_source = psx.Source(subassembly, arrival_model, [0, 0], ID="subassembly_source")
main_assembly_source = psx.Source(main_assembly, arrival_model, [0, 0], ID="main_assembly_source")

# Create production system
system = psx.ProductionSystem(
    resources=[
        assembly_station,
        worker,
    ],
    sources=[source_screw, source_bolt, source_washer, subassembly_source, main_assembly_source],
    sinks=[sink_screw, sink_bolt, sink_washer, sink_subassembly, sink_main_assembly],
)

# Convert to model and run simulation
model = system.to_model()
runner_instance = runner.Runner(production_system_data=model)
runner_instance.initialize_simulation()
runner_instance.run(1000)
runner_instance.print_results()
runner_instance.save_results_as_csv()

