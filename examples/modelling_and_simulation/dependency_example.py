import prodsys.express as psx
import prodsys

print("version used:", prodsys.VERSION)
prodsys.set_logging("CRITICAL")

t1 = psx.FunctionTimeModel("normal", 1, 0.1, "t1")
t2 = psx.FunctionTimeModel("normal", 2, 0.2, "t2")

p1 = psx.ProductionProcess(t1, "p1")
p2 = psx.ProductionProcess(t2, "p2")

t3 = psx.DistanceTimeModel(speed=180, reaction_time=0.1, ID="t3")

tp = psx.TransportProcess(t3, "tp")
move_p = psx.TransportProcess(t3, "move")

s1 = psx.FunctionTimeModel("exponential", 0.5, ID="s1")
setup_state_1 = psx.SetupState(s1, p1, p2, "S1")
setup_state_2 = psx.SetupState(s1, p2, p1, "S2")


assembly_process = psx.ProductionProcess(
    psx.FunctionTimeModel("exponential", 0.1, ID="fake_process"), "fake_process"
)

worker = psx.Resource(
    [move_p, assembly_process],
    [2, 0],
    1,
    ID="worker",
)

worker2 = psx.Resource(
    [move_p, assembly_process],
    [3, 0],
    1,
    ID="worker2",
)

assembly_dependency = psx.ProcessDependency(
    ID="assembly_dependency",
    required_process=assembly_process,
)
# worker_dependency = psx.ResourceDependency(
#     ID="worker_dependency",
#     required_resource=worker,
# )
# worker_dependency2 = psx.ResourceDependency(
#     ID="worker_dependency2",
#     required_resource=worker2,
# )

machine = psx.Resource(
    [p1, p2],
    [5, 5],
    2,
    states=[setup_state_1, setup_state_2],
    ID="machine",
    output_location=[5, 6],
    # dependencies=[worker_dependency],
    dependencies=[assembly_dependency],
)
# machine2 = psx.Resource(
#     [p1, p2],
#     [7, 2],
#     2,
#     states=[setup_state_1, setup_state_2],
#     ID="machine2",
#     output_location=[7, 3],
#     # dependencies=[worker_dependency2],
#     dependencies=[assembly_dependency],
# )

transport = psx.Resource([tp], [2, 2], 1, ID="transport")

product1 = psx.Product([p1], tp, "product1")
product2 = psx.Product([p2], tp, "product2")

sink1 = psx.Sink(product1, [10, 0], "sink1")
sink2 = psx.Sink(product2, [10, 0], "sink2")


arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")
arrival_model_2 = psx.FunctionTimeModel("exponential", 2, ID="arrival_model_2")


source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")
source2 = psx.Source(product2, arrival_model_2, [0, 0], ID="source_2")


system = psx.ProductionSystem(
    # [machine, machine2, transport, worker, worker2], [source1, source2], [sink1, sink2]
    [machine, transport, worker, worker2],
    [source1, source2],
    [sink1, sink2],
)
model = system.to_model()
model.write("examples/dependency_example_model.json")
from prodsys import runner

runner_instance = runner.Runner(production_system_data=model)
runner_instance.initialize_simulation()
system.run(1000)

runner_instance = system.runner

runner_instance.print_results()
# runner_instance.plot_results()
runner_instance.save_results_as_csv("examples")
