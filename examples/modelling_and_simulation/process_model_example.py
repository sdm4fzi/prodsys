import prodsys.express as psx
import prodsys
from prodsys.models import port_data


print("version used:", prodsys.VERSION)
prodsys.set_logging("CRITICAL")

t1 = psx.FunctionTimeModel("normal", 1, 0.1, "t1")
t2 = psx.FunctionTimeModel("normal", 2, 0.2, "t2")

lot_dependency_p1 = psx.LotDependency(
    min_lot_size=2,
    max_lot_size=2,
    ID="lot_dependency_p1",
)
lot_dependency_p2 = psx.LotDependency(
    min_lot_size=2,
    max_lot_size=2,
    ID="lot_dependency_p2",
)

p1 = psx.ProductionProcess(t1, "p1", dependencies=[lot_dependency_p1])
p2 = psx.ProductionProcess(t2, "p2", dependencies=[lot_dependency_p2])

t3 = psx.DistanceTimeModel(speed=180, reaction_time=0.1, ID="t3")

tp = psx.TransportProcess(t3, "tp")

s1 = psx.FunctionTimeModel("exponential", 0.5, ID="s1")

process_model = psx.ProcessModel(
    adjacency_matrix={"p1": ["p2"], "p2": []},
    processes=[p1, p2],
    ID="process_model",
)

machine_input_queue = psx.Queue(
    ID="machine_input_queue",
    capacity=4,
    location=[5, 0],
    interface_type=port_data.PortInterfaceType.INPUT,
)

machine_output_queue = psx.Queue(
    ID="machine_output_queue",
    capacity=4,
    location=[5.5, 0],
    interface_type=port_data.PortInterfaceType.OUTPUT,
)
transport = psx.Resource([tp], [2, 0], 1, ID="transport")


machine = psx.Resource(
    [process_model],
    [5, 0],
    2,
    ID="machine",
)
machine.ports = [machine_input_queue, machine_output_queue]




product1 = psx.Product(process=process_model, transport_process=tp, ID="product1")

sink1 = psx.Sink(product1, [10, 0], "sink1")


arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")


source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")


system = psx.ProductionSystem(
    [machine, transport], [source1]  , [sink1]
)
model = system.to_model()

runner_instance = prodsys.runner.Runner(production_system_data=model)
runner_instance.initialize_simulation()
system.run(100)

runner_instance = system.runner

runner_instance.print_results()
runner_instance.plot_results()
runner_instance.save_results_as_csv()
