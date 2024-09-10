import prodsys.express as psx

import prodsys
# prodsys.set_logging("DEBUG")

t1 = psx.FunctionTimeModel("exponential", 0.8, 0, "t1")
t2 = psx.FunctionTimeModel("exponential", 1.2, 0, "t2")


p1 = psx.ProductionProcess(t1, "p1")
p2= psx.ProductionProcess(t2, "p2")

# t3 = psx.FunctionTimeModel("constant", 0.1, ID="t3")
t3 = psx.DistanceTimeModel(60, 0.05, "manhattan", ID="t3")

tp = psx.TransportProcess(t3, "tp")
tp_aux = psx.TransportProcess(t3, "tp_aux")

machine = psx.ProductionResource([p1], [5,0], 1, ID="machine")
machine2 = psx.ProductionResource([p2], [5,5], 2, ID="machine2")

transport = psx.TransportResource([tp], [3,0], 1, ID="transport")
transport2 = psx.TransportResource([tp], [3,0], 1, ID="transport2")
transport_aux = psx.TransportResource([tp_aux], [4,0], 1, ID="transport_aux")

storage1 = psx.Queue(ID="storage1", location=[5,0], capacity=30)
storage2 = psx.Queue(ID="storage2", location=[10,0], capacity=20)


auxiliary1 = psx.Auxiliary(ID="auxiliary1", transport_process=tp_aux, 
                           storages=[storage1], 
                           quantity_in_storages=[10], 
                           relevant_processes=[], 
                           relevant_transport_processes=[tp])

auxiliary2 = psx.Auxiliary(ID="auxiliary2", transport_process=tp_aux, 
                           storages=[storage2], 
                           quantity_in_storages=[20], 
                           relevant_processes=[], 
                           relevant_transport_processes=[tp])

product1 = psx.Product(processes= [p1, p2], transport_process=tp, ID = "product1", auxiliaries= [auxiliary1])
product2 = psx.Product(processes= [p2, p1], transport_process=tp, ID = "product2", auxiliaries= [auxiliary2])

sink1 = psx.Sink(product1, [10, 0], "sink1")
sink2 = psx.Sink(product2, [10, 0], "sink2")

arrival_model_1 = psx.FunctionTimeModel("constant", 2.6, ID="arrival_model_1")
arrival_model_2 = psx.FunctionTimeModel("constant", 1.3, ID="arrival_model_2")


source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")
source2 = psx.Source(product2, arrival_model_2, [0, 0], ID="source_2")



system = psx.ProductionSystem([machine, machine2, transport, transport2, transport_aux], [source1, source2], [sink1, sink2])
system.validate()
system.run(time_range=1000)
system.runner.print_results()
system.runner.plot_results()
# system.runner.save_results_as_csv()