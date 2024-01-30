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

node1 = psx.Node(location=[0, 0], ID="node1")
node2 = psx.Node(location=[0, 2], ID="node2")
node3 = psx.Node(location=[5, 2], ID="node3")
node4 = psx.Node(location=[5, 0], ID="node4")
node5 = psx.Node(location=[10, 2], ID="node5")
node6 = psx.Node(location=[10, 8], ID="node6")
node7 = psx.Node(location=[10, 10], ID="node7")
node8 = psx.Node(location=[5, 8], ID="node8")
node9 = psx.Node(location=[5, 10], ID="node9")
node10 = psx.Node(location=[0, 8], ID="node10")
node11 = psx.Node(location=[0, 10], ID="node11")
node12 = psx.Node(location=[10, 0], ID="node13")
node13 = psx.Node(location=[0, 8], ID="node14")




#TODO: Das kann ich noch entfernen und es soll automatisch von allen Links erstellt werden
ltp01 = psx.LinkTransportProcess(
    time_model=time_model_agv,
    ID="ltp01",
    type="LinkTransportProcesses",
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
    location= [-1,0],
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
    processes=[ltp01],
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
    location=[-1, 0],
)
sink01 = psx.Sink(product=product01, ID="sink01", location=[-1, 10])

source02 = psx.Source(
    product=product02,
    ID="source02",
    time_model=timer_model_interarrival_time2,
    location=[-1, 0],
)
sink02 = psx.Sink(product=product02, ID="sink02", location=[-1, 10])

# TODO: maybe set links with method after definition of components of links
ltp01.links += [[node2, node1],
        [node2, node3],
        [node3, node2],
        [node3, node4],
        [node4, node5],
        [node5, node4],
        [node5, node6],
        [node6, node5],
        [node6, node7],
        [node7, node6],
        [node7, node8],
        [node8, node7],
        [node8, node9],[node1, node2], [source01, node1], [node1, source01], [node9, sink01], [sink01, node9]]

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