import prodsys.express as psx
from prodsys.simulation import runner


t1 = psx.FunctionTimeModel("constant", 1.8, 0, "t1")

p1 = psx.ProductionProcess(t1, "p1")

t3 = psx.DistanceTimeModel(speed=300, reaction_time=0.01, ID="t3")

carrier_tp = psx.TransportProcess(t3, "carrier_tp")


work_piece_carrier_storage = psx.Queue(ID="work_piece_carrier_storage", location=[0, 0], capacity=2)

work_piece_carriers = psx.Primitive(
    ID="work_piece_carriers",
    transport_process=carrier_tp,
    storages=[work_piece_carrier_storage],
    quantity_in_storages=[2],
)

lot_dependency_with_carrier = psx.LotDependency(
    min_lot_size=1,
    max_lot_size=4,
    ID="lot_dependency",
)
work_piece_carrier_dependency = psx.PrimitiveDependency(
    required_primitive=work_piece_carriers
)

lot_dependency_without_carrier = psx.LotDependency(
    min_lot_size=2,
    max_lot_size=3,
    ID="lot_dependency",
)

machine = psx.Resource(
    [p1],
    [5, 0],
    capacity=5,
    ID="machine",
    dependencies=[lot_dependency_without_carrier],
)


# tp = psx.TransportProcess(t3, "tp", dependencies=[lot_dependency_with_carrier, work_piece_carrier_dependency])
tp = psx.TransportProcess(t3, "tp", dependencies=[work_piece_carrier_dependency])

transport = psx.Resource([tp], [0, 0], 1, ID="transport")
carrier_transport = psx.Resource([carrier_tp], [0, 0], 1, ID="carrier_transport")

product1 = psx.Product([p1], tp, "product1")

sink1 = psx.Sink(product1, [10, 0], "sink1")

arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")

source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")

system = psx.ProductionSystem([machine, transport, carrier_transport], [source1], [sink1], [work_piece_carriers])
system_data = system.to_model()
runner_instance = runner.Runner(production_system_data=system_data)
runner_instance.initialize_simulation()
runner_instance.run(1000)
runner_instance.print_results()
runner_instance.save_results_as_csv()