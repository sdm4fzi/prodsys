import prodsys.express as psx
from prodsys import runner

t1 = psx.FunctionTimeModel("exponential", 0.8, 0, "t1")

p1 = psx.ProductionProcess(t1, "p1")
p2 = psx.ProductionProcess(t1, "p2")

t3 = psx.FunctionTimeModel("normal", 0.05, 0.01, ID="t3")

tp = psx.TransportProcess(t3, "tp")

machine = psx.Resource(
    [p1],
    [5, 0],
    3,
    ID="machine",
    internal_queue_size=0,
)

machine2 = psx.Resource(
    [p2],
    [9, 0],
    3,
    ID="machine2",
    internal_queue_size=0,
)
# FIXME: bug with limited storages and queues... -> no fallbacks if queue is full and simulation stops
storage1 = psx.Store(ID="storage1", location=[6, 0], capacity=4)
storage2 = psx.Store(ID="storage2", location=[11, 0], capacity=4)
machine.buffers = [storage1]
machine2.buffers = [storage2]

transport = psx.Resource([tp], [0, 0], 1, ID="transport")

product1 = psx.Product([p1, p2], tp, "product1")

sink1 = psx.Sink(product1, [10, 0], "sink1")

arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")

source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")

system = psx.ProductionSystem([machine, machine2, transport], [source1], [sink1])
adapter = system.to_model()

runner_instance = runner.Runner(production_system_data=adapter)
runner_instance.initialize_simulation()
runner_instance.run(1000)
runner_instance.print_results()
runner_instance.plot_results()
runner_instance.plot_results_executive()
runner_instance.save_results_as_csv()