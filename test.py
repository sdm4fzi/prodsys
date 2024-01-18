import prodsys.express as psx

time_model_agv = psx.FunctionTimeModel(
    distribution_function="constant", location=62 / 60, ID="time_model_ap01"
)

time_model_conveyor = psx.FunctionTimeModel(
    distribution_function="constant", location=47 / 60, ID="time_model_ap23"
)

time_model_machine1 = psx.FunctionTimeModel(
    distribution_function="constant", location=47 / 60, ID="time_model_ap23"
)
time_model_machine2 = psx.FunctionTimeModel(
    distribution_function="constant", location=47 / 60, ID="time_model_ap23"
)
time_model_machine3 = psx.FunctionTimeModel(
    distribution_function="constant", location=47 / 60, ID="time_model_ap23"
)
time_model_machine4 = psx.FunctionTimeModel(
    distribution_function="constant", location=47 / 60, ID="time_model_ap23"
)
time_model_machine5 = psx.FunctionTimeModel(
    distribution_function="constant", location=47 / 60, ID="time_model_ap23"
)
time_model_machine6 = psx.FunctionTimeModel(
    distribution_function="constant", location=47 / 60, ID="time_model_ap23"
)
timer_model_interarrival_time = psx.FunctionTimeModel(
    distribution_function="constant", location=40 / 60, ID="time_model_source01"
)
timer_model_interarrival_time2 = psx.FunctionTimeModel(
    distribution_function="constant", location=42 / 60, ID="time_model_source02"
)

link01 = psx.Link(from_position=[-1, 0], to_position=[0, 0], ID="link01")
link02 = psx.Link(from_position=[0, 0], to_position=[0, 2], ID="link02")
link03 = psx.Link(from_position=[0, 2], to_position=[5, 2], ID="link03")
link04 = psx.Link(from_position=[5, 0], to_position=[5, 2], ID="link04")
link05 = psx.Link(from_position=[5, 2], to_position=[10, 2], ID="link05")
link06 = psx.Link(from_position=[10, 2], to_position=[10, 8], ID="link06")
link07 = psx.Link(from_position=[10, 8], to_position=[10, 10], ID="link07")
link08 = psx.Link(from_position=[5, 8], to_position=[10, 8], ID="link08")
link09 = psx.Link(from_position=[5, 8], to_position=[5, 10], ID="link09")
link10 = psx.Link(from_position=[0, 8], to_position=[5, 8], ID="link10")
link11 = psx.Link(from_position=[0, 8], to_position=[0, 10], ID="link11")
link12 = psx.Link(from_position=[-1, 10], to_position=[0, 10], ID="link12")
link13 = psx.Link(from_position=[10, 0], to_position=[10, 2], ID="link13")
link14 = psx.Link(from_position=[0, 2], to_position=[0, 8], ID="link14")

ltp01 = psx.LinkTransportProcess(
    links=[
        link01,
        link02,
        link03,
        link04,
        link05,
        link06,
        link07,
        link08,
        link09,
        link10,
        link11,
        link12,
        link13,
        link14,
    ],
    time_model=time_model_agv,
    ID="ltp01",
    type="LinkTransportProcesses",
)
rt01 = psx.RouteTransportProcess(
    links=[link13, link06, link07],
    time_model=time_model_agv,
    ID="rt01",
    type="RouteTransportProcesses",
)

productionprocess01 = psx.ProductionProcess(time_model=time_model_machine1, ID="pp01")
productionprocess02 = psx.ProductionProcess(time_model=time_model_machine2, ID="pp02")
productionprocess03 = psx.ProductionProcess(time_model=time_model_machine3, ID="pp03")
productionprocess04 = psx.ProductionProcess(time_model=time_model_machine4, ID="pp04")
productionprocess05 = psx.ProductionProcess(time_model=time_model_machine5, ID="pp05")
productionprocess06 = psx.ProductionProcess(time_model=time_model_machine6, ID="pp06")


machine01 = psx.ProductionResource(
    ID="r01",
    processes=[productionprocess01],
    location=[0, 0],
)
machine02 = psx.ProductionResource(
    ID="r02",
    processes=[productionprocess02],
    location=[5, 0],
)
machine03 = psx.ProductionResource(
    ID="r03",
    processes=[productionprocess03],
    location=[10, 0],
)
machine04 = psx.ProductionResource(
    ID="r04",
    processes=[productionprocess04],
    location=[10, 10],
)
machine05 = psx.ProductionResource(
    ID="r05",
    processes=[productionprocess05],
    location=[5, 10],
)
machine06 = psx.ProductionResource(
    ID="r06",
    processes=[productionprocess06],
    location=[0, 10],
)

# Während hier der AGV eben alle Routen fahren kann
agv01 = psx.TransportResource(
    location= [0,0],
    ID="agv01",
    processes=[ltp01],
)

agv02 = psx.TransportResource(
    location= [0,0],
    ID="agv02",
    processes=[ltp01],
)

# Sagen wir hier ja welcher AGV eben spezifisch nur die zwei routen fahren kann
# Das heißt wir brauchen ein Matching
agv03 = psx.TransportResource(
    ID="agv03",
    processes=[rt01],
)

product01 = psx.Product(
    processes=[
        productionprocess01,
        productionprocess02,
        productionprocess03,
        productionprocess04,
        productionprocess05,
        productionprocess06,
    ],
    transport_process=ltp01,
    ID="product01",
)
product02 = psx.Product(
    processes=[
        productionprocess01,
        productionprocess02,
        productionprocess05,
        productionprocess06,
    ],
    transport_process=ltp01,
    ID="product02",
)

source01 = psx.Source(
    product=product01,
    ID="source01",
    time_model=timer_model_interarrival_time,
    location=(-1, 0),
)
sink01 = psx.Sink(product=product01, ID="sink01", location=(-1, 10))

source02 = psx.Source(
    product=product02,
    ID="source02",
    time_model=timer_model_interarrival_time2,
    location=(-1, 0),
)
sink02 = psx.Sink(product=product02, ID="sink02", location=(-1, 10))

productionsystem = psx.ProductionSystem(
    resources=[
        agv01,
        agv02,
        agv03,
        machine01,
        machine02,
        machine03,
        machine04,
        machine05,
        machine06,
    ],
    sources=[source01, source02],
    sinks=[sink01, sink02],
    ID="productionsystem01",
)

productionsystem.validate()
productionsystem.run(time_range=8 * 60)
productionsystem.runner.print_results()