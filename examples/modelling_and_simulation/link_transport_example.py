from prodsys import express as psx
import prodsys


# all time models
time_model_agv = psx.ManhattanDistanceTimeModel(
    speed=360, reaction_time=0, ID="time_model_x"
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

# All nodes
node1 = psx.Node(location=[10, 0], ID="node1")
node2 = psx.Node(location=[0, 15], ID="node2")
node3 = psx.Node(location=[20, 20], ID="node3")
node4 = psx.Node(location=[0, 20], ID="node4")

# All processes
ltp01 = psx.LinkTransportProcess(time_model=time_model_agv, ID="ltp01")
productionprocess01 = psx.ProductionProcess(
    time_model=time_model_machine1, ID="pp01"
)
productionprocess02 = psx.ProductionProcess(
    time_model=time_model_machine2, ID="pp02"
)
productionprocess03 = psx.ProductionProcess(
    time_model=time_model_machine3, ID="pp03"
)

# All resources
machine01 = psx.ProductionResource(
    ID="resource01",
    processes=[productionprocess01],
    location=[10, 10],
)
machine02 = psx.ProductionResource(
    ID="resource02",
    processes=[productionprocess02],
    location=[20, 10],
)
machine03 = psx.ProductionResource(
    ID="resource03",
    processes=[productionprocess03],
    location=[10, 20],
)

agv01 = psx.TransportResource(
    location=[0, 0],
    ID="agv01",
    processes=[ltp01],
)

# All products
product01 = psx.Product(
    processes=[
        productionprocess01,
        productionprocess02,
        productionprocess03,
    ],
    transport_process=ltp01,
    ID="product01",
)

product02 = psx.Product(
    processes=[
        productionprocess03,
        productionprocess02,
        productionprocess01,
    ],
    transport_process=ltp01,
    ID="product02",
)

source01 = psx.Source(
    product=product01,
    ID="source01",
    time_model=timer_model_interarrival_time,
    location=[0, 0],
)
source02 = psx.Source(
    product=product02,
    ID="source02",
    time_model=timer_model_interarrival_time2,
    location=[0, 0],
)

sink01 = psx.Sink(product=product01, ID="sink01", location=[20, 25])
sink02 = psx.Sink(product=product02, ID="sink02", location=[20, 25])


# Update processes
links = [
    [source01, node1],
    [source02, node1],
    [source01, node2],
    [source02, node2],
    [node1, machine01],
    [node2, machine01],
    [node2, node4],
    [machine02, machine03],
    [machine03, machine01],
    [machine01, machine02],
    [machine03, node3],
    [machine02, node3],
    [node4, machine03],
    [node3, sink01],
    [node3, sink02],
]

ltp01.set_links(links)

# Add production system
productionsystem = psx.ProductionSystem(
resources=[
    agv01,
    machine01,
    machine02,
    machine03,
],
sources=[source01, source02],
sinks=[sink01, sink02],
ID="productionsystem01",)

adapter = productionsystem.to_model()
runner = prodsys.runner.Runner(adapter=adapter)
runner.initialize_simulation()
runner.run(1000)
runner.print_results()