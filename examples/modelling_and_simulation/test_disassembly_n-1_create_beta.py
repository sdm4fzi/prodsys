import prodsys
from prodsys.models.production_system_data import (
add_default_queues_to_production_system,
)

from prodsys.simulation.logger import EventLogger


event_logger = EventLogger()
from prodsys.models.port_data import Queue_Per_Product_Data
from prodsys.util import post_processing
from prodsys.models.port_data import PortInterfaceType
from prodsys.models.primitives_data import StoredPrimitive

welding_time_model = prodsys.time_model_data.FunctionTimeModelData(
ID="time model 1",
description="Time model 1 is create!",
distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Exponential,
location=.060,
scale=0.0,
)



transport_time_model = prodsys.time_model_data.DistanceTimeModelData(
ID="time model 2",
description="Time model 2 is create!",
speed=5.0,
reaction_time=0.0,
)



transport_process = prodsys.processes_data.TransportProcessData(
ID="NormalTransport",
description="Normal transport process",
time_model_id=transport_time_model.ID,
type=prodsys.processes_data.ProcessTypeEnum.TransportProcesses,
)











transport_resource = prodsys.resource_data.ResourceData(
ID="Forklift1",
description="Forklift 1 data description",
capacity=1,
location=[5.0, 0.0],
controller=prodsys.resource_data.ControllerEnum.PipelineController,
control_policy=prodsys.resource_data.TransportControlPolicy.FIFO,# vllt ändern
process_ids=[transport_process.ID],
    

)




arrival_time_model = prodsys.time_model_data.FunctionTimeModelData(
ID="time model 3",
description="Time model 3 is create!",
type=prodsys.time_model_data.TimeModelEnum.FunctionTimeModel,
distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Exponential,
location=50,
scale=0,
)
arrival_time_model1 = prodsys.time_model_data.FunctionTimeModelData(
ID="time model 4",
description="Time model 4 is create!",
type=prodsys.time_model_data.TimeModelEnum.FunctionTimeModel,
distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Exponential,
location=10000000,
scale=0,
)


source2 = prodsys.source_data.SourceData(
ID="source 2",
description="Source 1 data description",
location=[0.0, 0.0],
product_type="mutterprodukt",
time_model_id="time model 3",
routing_heuristic=prodsys.source_data.RoutingHeuristic.random,

)
source4 = prodsys.source_data.SourceData(
ID="source 4",
description="Source 3 data description",
location=[0.0, 0.0],
product_type="product 1",
time_model_id="time model 4",
routing_heuristic=prodsys.source_data.RoutingHeuristic.random,

)


sink = prodsys.sink_data.SinkData(
ID="sink 1",
description="Sink 1 data description",
location=[20.0, 20.0],
product_type="product 1",

)#

sink2 = prodsys.sink_data.SinkData(
ID="sink 2",
description="Sink 1 data description",
location=[20.0, 20.0],
product_type="mutterprodukt",


)
sink3 = prodsys.sink_data.SinkData(
ID="sink 3",
description="Sink 3 data description",
location=[20.0, 20.0],
product_type="product 2",


)

production_process = prodsys.processes_data.ProductionProcessData(
ID="production_process",
description="production_process",
time_model_id=welding_time_model.ID,
type=prodsys.processes_data.ProcessTypeEnum.ProductionProcesses,
)
product = prodsys.product_data.ProductData(
ID="product 1",
description="Product 1 data description",
type="product 1",
processes=[production_process.ID],
transport_process=transport_process.ID,
routing_heuristic=prodsys.source_data.RoutingHeuristic.random, 
)
product2 = prodsys.product_data.ProductData(
ID="product 2",
description="Product 2 data description",
type="product 2",
processes=[production_process.ID],
transport_process=transport_process.ID,
routing_heuristic=prodsys.source_data.RoutingHeuristic.random, 
)
mutterprodukt = prodsys.product_data.ProductData(
ID="mutterprodukt",
description="Productsdsd 1 data description",
type="mutterprodukt",
processes=["disassembly_process"],
transport_process=transport_process.ID,
routing_heuristic=prodsys.source_data.RoutingHeuristic.random,
)
disassembly_process = prodsys.processes_data.ProductionProcessData(
ID="disassembly_process",
description="disAssembly_process",
time_model_id=welding_time_model.ID,
type=prodsys.processes_data.ProcessTypeEnum.ProductionProcesses,
product_disassembly_dict= {"mutterprodukt": [mutterprodukt,product, product2] },
)









disassemblymachine = prodsys.resource_data.ResourceData(
ID="disassemblymachine 1",
description="Machine 1 data description",
capacity=2,
location=[10.0, 10.0],
controller=prodsys.resource_data.ControllerEnum.PipelineController,
control_policy=prodsys.resource_data.ResourceControlPolicy.FIFO,
process_ids=[disassembly_process.ID],

)
machine = prodsys.resource_data.ResourceData(
ID="machine 2",
description="Machine 2 data description",
capacity=1,
location=[15.0, 15.0],
controller=prodsys.resource_data.ControllerEnum.PipelineController,
control_policy=prodsys.resource_data.ResourceControlPolicy.FIFO,
process_ids=[production_process.ID],

)

production_system_instance = prodsys.production_system_data.ProductionSystemData(
time_model_data=[welding_time_model, transport_time_model, arrival_time_model, arrival_time_model1],
process_data=[transport_process,production_process, disassembly_process],
resource_data=[machine, transport_resource, disassemblymachine],
product_data=[product, mutterprodukt, product2],
source_data=[ source2, source4],
sink_data=[sink, sink2, sink3],
)

add_default_queues_to_production_system(production_system_instance)
production_system_instance.validate_configuration()

runner = prodsys.runner.Runner(production_system_data=production_system_instance)
runner.initialize_simulation()

runner.run(10000)

runner.print_results()

#runner.save_results_as_csv("test")

