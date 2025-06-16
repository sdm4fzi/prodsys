import prodsys.express as psx
from prodsys.models import resource_data
from prodsys.simulation import runner


t1 = psx.FunctionTimeModel("exponential", 1.8, 0, "t1")

p1 = psx.ProductionProcess(t1, "p1")

t3 = psx.FunctionTimeModel("constant", 0.1, ID="t3")

tp = psx.TransportProcess(t3, "tp")

machine = psx.Resource(
    [p1],
    [5, 0],
    capacity=2,
    ID="machine",
    controller=resource_data.ControllerEnum.BatchController,
    batch_size=2,
)

transport = psx.Resource([tp], [0, 0], 1, ID="transport")

product1 = psx.Product([p1], tp, "product1")

sink1 = psx.Sink(product1, [10, 0], "sink1")

arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")

source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")

system = psx.ProductionSystem([machine, transport], [source1], [sink1])
system_data = system.to_model()
runner_instance = runner.Runner(production_system_data=system_data)
runner_instance.initialize_simulation()
runner_instance.run(2000)
runner_instance.print_results()
runner_instance.save_results_as_csv()