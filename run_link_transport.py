import prodsys.express as psx

time_model_agv = psx.ManhattanDistanceTimeModel(
    speed=90, reaction_time=0.2, ID="time_model_x"
)

time_model_machine1 = psx.FunctionTimeModel(
    distribution_function="constant", location=3, ID="time_model_ap23"
)
time_model_machine2 = psx.FunctionTimeModel(
    distribution_function="constant", location=3, ID="time_model_ap23"
)
time_model_machine3 = psx.FunctionTimeModel(
    distribution_function="constant", location=6, ID="time_model_ap23"
)
time_model_machine4 = psx.FunctionTimeModel(
    distribution_function="constant", location=6, ID="time_model_ap23"
)
time_model_machine5 = psx.FunctionTimeModel(
    distribution_function="constant", location=6, ID="time_model_ap23"
)
time_model_machine6 = psx.FunctionTimeModel(
    distribution_function="constant", location=3, ID="time_model_ap23"
)
timer_model_interarrival_time = psx.FunctionTimeModel(
    distribution_function="constant", location=6, ID="time_model_source01"
)
timer_model_interarrival_time2 = psx.FunctionTimeModel(
    distribution_function="constant", location=6, ID="time_model_source02"
)

node1 = psx.Node(location=[0, 20], ID="node1")
node2 = psx.Node(location=[50, 20], ID="node2")
node3 = psx.Node(location=[100, 20], ID="node3")
node4 = psx.Node(location=[100, 80], ID="node4")
node5 = psx.Node(location=[50, 80], ID="node5")
node6 = psx.Node(location=[0, 80], ID="node6")


ltp01 = psx.LinkTransportProcess(time_model=time_model_agv, ID="ltp01")
productionprocess01 = psx.ProductionProcess(time_model=time_model_machine1, ID="pp01")
productionprocess02 = psx.ProductionProcess(time_model=time_model_machine2, ID="pp02")
productionprocess03 = psx.ProductionProcess(time_model=time_model_machine3, ID="pp03")
productionprocess04 = psx.ProductionProcess(time_model=time_model_machine4, ID="pp04")
productionprocess05 = psx.ProductionProcess(time_model=time_model_machine5, ID="pp05")
productionprocess06 = psx.ProductionProcess(time_model=time_model_machine6, ID="pp06")


machine01 = psx.ProductionResource(
    ID="resource01",
    processes=[productionprocess01],
    location=[0, 0],
)
machine02 = psx.ProductionResource(
    ID="resource02",
    processes=[productionprocess02],
    location=[50, 0],
)
machine03 = psx.ProductionResource(
    ID="resource03",
    processes=[productionprocess03],
    location=[100, 0],
)
machine04 = psx.ProductionResource(
    ID="resource04",
    processes=[productionprocess04],
    location=[100, 100],
)
machine05 = psx.ProductionResource(
    ID="resource05",
    processes=[productionprocess05],
    location=[50, 100],
)
machine06 = psx.ProductionResource(
    ID="resource06",
    processes=[productionprocess06],
    location=[0, 100],
)

agv01 = psx.TransportResource(
    location=[100, 100],
    ID="agv01",
    processes=[ltp01],
)

agv02 = psx.TransportResource(
    location=[0, 0],
    ID="agv02",
    processes=[ltp01],
)

agv03 = psx.TransportResource(
    location=[100, 100],
    ID="agv03",
    processes=[ltp01],
)


agv04 = psx.TransportResource(
    location=[100, 100],
    ID="agv04",
    processes=[ltp01],
)

agv05 = psx.TransportResource(
    location=[100, 100],
    ID="agv05",
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
        productionprocess06,
    ],
    transport_process=ltp01,
    ID="product02",
)

source01 = psx.Source(
    product=product01,
    ID="source01",
    time_model=timer_model_interarrival_time,
    location=[-10, 0],
)
sink01 = psx.Sink(product=product01, ID="sink01", location=[-10, 100])

source02 = psx.Source(
    product=product02,
    ID="source02",
    time_model=timer_model_interarrival_time2,
    location=[-10, 0],
)
sink02 = psx.Sink(product=product02, ID="sink02", location=[-10, 100])

ltp01.links += [
    [source02, machine01],
    [source01, machine01],
    [machine01, node1],
    [node1, node2],
    [node2, machine02],
    [node2, node3],
    [node3, machine03],
    [node3, node4],
    [node4, machine04],
    [node4, node5],
    [node5, machine05],
    [node5, node6],
    [node6, machine06],
    [machine06, sink01],
    [machine06, sink02],
    [node1, node6],
]

productionsystem = psx.ProductionSystem(
    resources=[
        agv01,
        agv02,
        agv03,
        agv04,
        agv05,
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
productionsystem.run(time_range=10 * 60)
productionsystem.runner.print_results()
productionsystem.runner.save_results_as_csv()
