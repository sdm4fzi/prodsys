import prodsys.express as psx
import prodsys.express.queue

import prodsys
prodsys.set_logging("DEBUG")

t1 = psx.FunctionTimeModel("exponential", 0.8, 0, "t1")

p1 = psx.ProductionProcess(t1, "p1")

t3 = psx.FunctionTimeModel("constant", 0.1, ID="t3")

tp = psx.TransportProcess(t3, "tp")

machine = psx.ProductionResource([p1], [5,0], 1, ID="machine")

transport = psx.TransportResource([tp], [3,0], 1, ID="transport")

storage1 = psx.Queue(ID="storage1", location=[5,0], capacity=30)
storage2 = prodsys.express.queue.Queue(ID="storage2", location=[10,0], capacity=20)

auxiliary1 = psx.Auxiliary(ID="auxiliary1", transport_process=tp, 
                           storages=[storage1,storage2], 
                           # FIXME: resolve problem that multiple auxiliaries are not routed correctly, after the first transport....
                           initial_quantity_in_stores=[0,1], 
                           relevant_processes=[], 
                           relevant_transport_processes=[tp])

product1 = psx.Product(processes= [p1], transport_process= tp, ID = "product1", auxiliaries= [auxiliary1])

sink1 = psx.Sink(product1, [10, 0], "sink1")

arrival_model_1 = psx.FunctionTimeModel("constant", 0.5, ID="arrival_model_1")


source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")



system = psx.ProductionSystem([machine, transport], [source1], [sink1])

system.validate()
system.run(time_range=10)
system.runner.print_results()
system.runner.save_results_as_csv()