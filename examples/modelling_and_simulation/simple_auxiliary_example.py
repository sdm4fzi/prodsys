import prodsys.express as psx

import prodsys

# prodsys.set_logging("DEBUG")

t1 = psx.FunctionTimeModel("exponential", 0.8, 0, "t1")

p1 = psx.ProductionProcess(t1, "p1")

# t3 = psx.FunctionTimeModel("constant", 0.1, ID="t3")
t3 = psx.DistanceTimeModel(60, 0.05, "manhattan", ID="t3")

tp = psx.TransportProcess(t3, "tp")

machine = psx.Resource([p1], [5, 0], 1, ID="machine")

transport = psx.Resource([tp], [3, 0], 1, ID="transport")
transport2 = psx.Resource([tp], [4, 0], 1, ID="transport2")

storage1 = psx.Store(ID="storage1", location=[6, 0], capacity=30)
storage2 = psx.Store(ID="storage2", location=[11, 0], capacity=20)

workpiece_carrier = psx.Primitive(
    ID="workpiece_carrier",
    transport_process=tp,
    storages=[storage1, storage2],
    quantity_in_storages=[5, 20],
)

workpiece_carrier_dependencies = psx.PrimitiveDependency(
    ID="workpiece_carrier_dependency",
    required_primitive=workpiece_carrier,
)

product1 = psx.Product(
    processes=[p1],
    transport_process=tp,
    ID="product1",
    dependencies=[workpiece_carrier_dependencies],
)

sink1 = psx.Sink(product1, [10, 0], "sink1")

arrival_model_1 = psx.FunctionTimeModel("constant", 0.9, ID="arrival_model_1")


source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")


system = psx.ProductionSystem([machine, transport, transport2], [source1], [sink1], [workpiece_carrier])

system.validate()
system.run(time_range=1000)
system.runner.print_results()
system.runner.plot_results()
system.runner.plot_results_executive()
system.runner.save_results_as_csv()
