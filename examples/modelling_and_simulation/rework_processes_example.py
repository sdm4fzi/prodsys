import prodsys.express as psx
from prodsys.simulation.runner import Runner

t1 = psx.FunctionTimeModel("exponential", 0.8, 0, "t1")

p1 = psx.ProductionProcess(t1, "p1", failure_rate=0.05)
p2 = psx.ProductionProcess(t1, "p2", failure_rate=0.1)
p3 = psx.ProductionProcess(t1, "p3")

t3 = psx.FunctionTimeModel("constant", 0.1, ID="t3")

tp = psx.TransportProcess(t3, "tp")

rework_time_model = psx.FunctionTimeModel("constant", 1, ID="rework_time_model")
rework_time_model2 = psx.FunctionTimeModel("constant", 5, ID="rework_time_model")
rework_time_model3 = psx.FunctionTimeModel("constant", 2, ID="rework_time_model")

rework_process = psx.ReworkProcess(rework_time_model, [p1], True, "rework_process")
rework_process2 = psx.ReworkProcess(rework_time_model2, [p2], False, "rework_process2")
rework_process3 = psx.ReworkProcess(rework_time_model3, [p1], False, "rework_process3")

breakdown_time_model = psx.FunctionTimeModel("constant", 10, ID="breakdown_time_model")
repair_time_model = psx.FunctionTimeModel("constant", 5, ID="repair_time_model")
breakdown_state = psx.BreakDownState(breakdown_time_model, repair_time_model, ID="breakdown_state")

machine = psx.Resource([p1], [5, 0], 1, states=[breakdown_state], ID="machine")
machine2 = psx.Resource([p2], [10, 0], 1, ID="machine2")
machine3 = psx.Resource([p3], [5, 5], 1, ID="machine3")

reworker = psx.Resource(
    [rework_process, rework_process2, rework_process3], [8, 0], 1, ID="reworker"
)

transport = psx.Resource([tp], [0, 0], 1, ID="transport")

product1 = psx.Product(process=[p1, p2, p3], transport_process=tp, ID="product1")

sink1 = psx.Sink(product1, [15, 0], "sink1")

arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")

source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_2")

system = psx.ProductionSystem(
    [machine, machine2, machine3, reworker, transport], [source1], [sink1]
)
adapter = system.to_model()
runner_instance = Runner(production_system_data=adapter)
runner_instance.initialize_simulation()
runner_instance.run(2000)
runner_instance.print_results()
runner_instance.save_results_as_csv()