
import prodsys.express as psx
from prodsys import runner


t1 = psx.FunctionTimeModel("normal", 25, 5, "t1")
t2 = psx.FunctionTimeModel("normal", 10, 5, "t2")
t5 = psx.FunctionTimeModel("normal", 5, 0, "t5")
t6 = psx.FunctionTimeModel("normal", 10, 5, "t6")
t7 = psx.FunctionTimeModel("normal", 10, 5, "t7")
t8 = psx.FunctionTimeModel("normal", 60, 8, "t8")

p2 = psx.ProductionProcess(t1, "p2")
p3 = psx.ProductionProcess(t2, "p3")
p4 = psx.ProductionProcess(t5, "p4")
p5 = psx.ProductionProcess(t6, "p5")
p6 = psx.ProductionProcess(t7, "p6")
p7 = psx.ProductionProcess(t8, "p7")

t3 = psx.DistanceTimeModel(speed=5000, reaction_time=0.01, ID="t3")

tp = psx.TransportProcess(t3, "tp")

move_p = psx.TransportProcess(t3, "move")

s1 = psx.FunctionTimeModel("exponential", 0.5, ID="s1")

product1 = psx.Product(process=[p6], transport_process=tp, ID="pump")
product2 = psx.Product(process=[p3, p5], transport_process=move_p, ID="valve block")


primitive_dependency1 = psx.AssemblyDependency(
    required_entity= product1,        
)

primitive_dependency2 = psx.AssemblyDependency(
    required_entity= product2,        
)

p1 = psx.ProductionProcess(t8, "p1", dependencies= [primitive_dependency1,primitive_dependency2])                          

machine = psx.Resource(
    [p1],
    [20,10],
    2,        
    ID="assemblymachine_1",
    output_location=[20,10],
    
)

machine1 = psx.Resource(
    [p2],
    [0,10],
    2,

    ID="machine1",
    output_location=[0,10],
)

machine2 = psx.Resource(
    [p3],
    [5,0],
    2,
    ID="machine2",
    output_location=[5,0],
)

machine3 = psx.Resource(
    [p4],
    [15,0],
    2,
    ID="machine3",
    output_location=[15,0],
)

machine4 = psx.Resource(
    [p5],
    [10,10],
    2,
    ID="machine4",
    output_location=[10,10],
)

machine5 = psx.Resource(
    [p6],
    [5,10],
    2,
    ID="machine5",
    output_location=[5,10],
)

transport = psx.Resource([tp], [2, 2], 3, ID="transport")
transport2 = psx.Resource([move_p], [2, 2], 3, ID="transporta")
mutterproduct = psx.Product(process=[p2,p5,p1], transport_process=tp, ID="tank")

sink1 = psx.Sink(product1, [5,20], "sink1")
sink2 = psx.Sink(product2, [6,10], "sink2")
sink3 = psx.Sink(mutterproduct, [20.05,10.05], "muttersink")

arrival_model_1 = psx.FunctionTimeModel("exponential", 22, ID="arrival_model_1")
arrival_model_2 = psx.FunctionTimeModel("exponential", 22, ID="arrival_model_2")

source1 = psx.Source(product1, arrival_model_2, [0, 0], ID="source_1")
source2 = psx.Source(product2, arrival_model_2, [0, 0], ID="source_2")
source3 = psx.Source(mutterproduct, arrival_model_1, [0, 0], ID="source_3")

assemblymachine_2 = psx.Resource([p1], [22,10], 2, ID="assemblymachine_2", output_location=[22,10])
    
resources_A = [machine, machine1, machine2, machine3, machine4, machine5, transport, transport2, assemblymachine_2]
sources_all = [source1, source2, source3]
sinks_all = [sink1, sink2, sink3]

system = psx.ProductionSystem(resources_A, sources_all, sinks_all)
adapter = system.to_model()

runner_instance = runner.Runner(production_system_data=adapter)
runner_instance.initialize_simulation()
runner_instance.run(2000)
runner_instance.print_results()
runner_instance.save_results_as_csv()