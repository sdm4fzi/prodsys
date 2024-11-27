import prodsys.express as psx
from prodsys.express import production_system

time_model_agv = psx.DistanceTimeModel(speed=90, reaction_time=0.2, ID="time_model_x")
transport_process = psx.TransportProcess(
    time_model=time_model_agv, ID="transport_process"
)
agv = psx.TransportResource(ID="agv", processes=[transport_process], location=[5, 5])

time_model_turning_fast = psx.FunctionTimeModel(
    distribution_function="constant", location=6, ID="time_model_turning_fast"
)
time_model_turning_slow = psx.FunctionTimeModel(
    distribution_function="constant", location=9, ID="time_model_turning_slow"
)

capability_process_turning_fast = psx.CapabilityProcess(
    time_model=time_model_turning_fast, capability="turning", ID="cp_turning_fast"
)
capability_process_turning_slow = psx.CapabilityProcess(
    time_model=time_model_turning_slow, capability="turning", ID="cp_turning_slow"
)

resource_fast = psx.ProductionResource(
    ID="resource_fast", processes=[capability_process_turning_fast], location=[5, 0]
)
resource_slow = psx.ProductionResource(
    ID="resource_slow", processes=[capability_process_turning_slow], location=[5, 10]
)

required_capability_process_turning = psx.RequiredCapabilityProcess(
    capability="turning", ID="rcp_turning"
)

product = psx.Product(
    processes=[required_capability_process_turning],
    transport_process=transport_process,
    ID="product",
)

source = psx.Source(
    time_model=psx.FunctionTimeModel(
        distribution_function="constant", location=6, ID="interarrival_time_model"
    ),
    ID="source",
    product=product,
    location=[0, 5],
)

sink = psx.Sink(ID="sink", product=product, location=[10, 5])

system = production_system.ProductionSystem(
    resources=[resource_fast, resource_slow, agv], sources=[source], sinks=[sink]
)

system.validate()
system.run(1000)
system.runner.print_results()
