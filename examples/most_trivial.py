import prodsys.express as psx


t1 = psx.FunctionTimeModel("normal", 1, 0.1, "t1")
t2 = psx.FunctionTimeModel("normal", 2, 0.2, "t2")

p1 = psx.ProductionProcess(t1, "p1")
p2 = psx.ProductionProcess(t2, "p2")

t3 = psx.FunctionTimeModel("constant", 0.2, ID="t3")

tp = psx.TransportProcess(t3, "tp")

s1 = psx.FunctionTimeModel("exponential", 0.5, ID="s1")
setup_state_1 = psx.SetupState(s1, p1, p2, "S1")
setup_state_2 = psx.SetupState(s1, p2, p1, "S2")

machine = psx.ProductionResource([p1, p2], [0,0], 2, states=[setup_state_1, setup_state_2], ID="machine")

transport = psx.TransportResource([tp], [0,0], 1, ID="transport")

product1 = psx.Product([p1], tp, "product1")
product2 = psx.Product([p2], tp, "product2")

sink1 = psx.Sink(product1, [0, 0], "sink1")
sink2 = psx.Sink(product2, [0, 0], "sink2")


arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")
arrival_model_2 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_2")


source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_2")
source2 = psx.Source(product2, arrival_model_2, [0, 0], ID="source_2")



system = psx.ProductionSystem([machine, transport], [source1, source2], [sink1, sink2])
model = system.to_model()
from prodsys import runner
runner_instance = runner.Runner(adapter=model)
runner_instance.initialize_simulation()
system.run(1000)

runner_instance = system.runner

runner_instance.print_results()
# runner_instance.plot_results()
runner_instance.save_results_as_csv("examples")