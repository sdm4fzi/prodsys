import prodsys
from prodsys.models.production_system_data import (
add_default_queues_to_production_system,
)
from prodsys.models.queue_data import Queue_Per_Product_Data
from prodsys.util import post_processing
#from prodsys.models.queue_data import Queue_Per_Product_Data

# Create a time model for a production process and a transport process

welding_time_model = prodsys.time_model_data.FunctionTimeModelData(
ID="time model 1",
description="Time model 1 is create!",
distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Exponential,
location=60.0,
scale=0.0,
)

assembly_time_model = prodsys.time_model_data.FunctionTimeModelData(
ID="time model 8",
description="Time model 8 is create!",
distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Exponential,
location=120.0,
scale=0.0,
)


transport_time_model = prodsys.time_model_data.DistanceTimeModelData(
ID="time model 2",
description="Time model 2 is create!",
speed=50.0,
reaction_time=0.0,
)


# create a process to produce a part and a process to transport it

'''welding_process = prodsys.processes_data.ProductionProcessData(
ID="Welding",
description="Welding process",
time_model_id=welding_time_model.ID,
type=prodsys.processes_data.ProcessTypeEnum.ProductionProcesses,
required_product_types = ["assemblyproduct"],# muss noch geändetr werden, muss auch mainproduct rein
is_assembly= False,
)'''
assembly_process = prodsys.processes_data.ProductionProcessData(
ID="Assembly",
description="Assembly process",
time_model_id=assembly_time_model.ID,
type=prodsys.processes_data.ProcessTypeEnum.ProductionProcesses,
required_product_types = ["product 1"],# muss noch geändetr werden, muss auch mainproduct rein
is_assembly= True,
)

transport_process = prodsys.processes_data.TransportProcessData(
ID="NormalTransport",
description="Normal transport process",
time_model_id=transport_time_model.ID,
type=prodsys.processes_data.ProcessTypeEnum.TransportProcesses,
)

transport_process2 = prodsys.processes_data.TransportProcessData(
ID="NormalTransport2",
description="Normal transport process2",
time_model_id=transport_time_model.ID,
type=prodsys.processes_data.ProcessTypeEnum.TransportProcesses,
)

# Create a production resource
queuea = Queue_Per_Product_Data(
ID = "Q1",
description = "assemblyarriba",
capacity= 2,
product= "assemblyproduct",
)

queuep = Queue_Per_Product_Data(
ID = "Q2",
description = "productarriba",
capacity= 2,
product= "product 1",
)

queueout1 = Queue_Per_Product_Data(
ID = "Q31",
description = "assemblyarriba",
capacity= 2,
product= "assemblyproduct",
)

queueout2 = Queue_Per_Product_Data(
ID = "Q32",
description = "productarriba",
capacity= 2,
product= "product 1",
)
'''queueao = prodsys.queue_data.QueueData(
ID = "Q3",
description = "asdaa",
capacity= 4,
)'''
queueaofork = prodsys.queue_data.QueueData(
ID = "Q4",
description = "asdassdada",
capacity= 1,
)
queueaofork2 = prodsys.queue_data.QueueData(
ID = "Q5",
description = "asdasasa4dda",
capacity= 1,
)
queuesource1 = prodsys.queue_data.QueueData(
ID = "Q11",
description = "asdasas23adda",
capacity= 4,
)
queuesource2 = prodsys.queue_data.QueueData(
ID = "Q12",
description = "a23sdasasadda",
capacity= 4,
)
queuesink1 = prodsys.queue_data.QueueData(
ID = "Q21",
description = "asdasas23fdaadda",
capacity= 4,
)
queuesink2 = prodsys.queue_data.QueueData(
ID = "Q22",
description = "a23sdasasasdadda",
capacity= 4,
)


machine = prodsys.resource_data.ResourceData(
ID="machine 1",
description="Machine 1 data description",
capacity=2,
location=[10.0, 10.0],
controller=prodsys.resource_data.ControllerEnum.PipelineController,
control_policy=prodsys.resource_data.ResourceControlPolicy.FIFO,
process_ids=[assembly_process.ID],
input_queues= [queuea.ID, queuep.ID],
output_queues= [queueout2.ID, queueout1.ID]
#location auch ?
)



# create a transport resource

transport_resource = prodsys.resource_data.ResourceData(
ID="Forklift1",
description="Forklift 1 data description",
capacity=1,
location=[5.0, 0.0],
controller=prodsys.resource_data.ControllerEnum.PipelineController,
control_policy=prodsys.resource_data.TransportControlPolicy.SPT_transport,
process_ids=[transport_process.ID, transport_process2.ID],
input_queues= [queueaofork.ID],
output_queues= [queueaofork2.ID],

)
'''
transport_resource2 = prodsys.resource_data.ResourceData(
ID="Forklift2",
description="Forklift 2 data description",
capacity=1,
location=[10.0, 0.0],
controller=prodsys.resource_data.ControllerEnum.PipelineController,
control_policy=prodsys.resource_data.TransportControlPolicy.SPT_transport,
process_ids=[transport_process2.ID],
)
'''

# create a product

product = prodsys.product_data.ProductData(
ID="product 1",
description="Product 1 data description",
type="product 1",
processes=[assembly_process.ID],
transport_process=transport_process.ID,

)

assemblyproduct = prodsys.product_data.ProductData(
ID="assemblyproduct",
description="Product 2 data descrisadption",
type="assemblyproduct",
processes=[assembly_process.ID],
transport_process=transport_process.ID,
#mounted_products= [product.ID]# wird doch einfach nur erstellt und dynamisch befüllt

)

# Create a time model for product arrival in the system and a source that creates the product

arrival_time_model = prodsys.time_model_data.FunctionTimeModelData(
ID="time model 3",
description="Time model 3 is create!",
type=prodsys.time_model_data.TimeModelEnum.FunctionTimeModel,
distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Exponential,
location=30,
scale=0,
)

source = prodsys.source_data.SourceData(
ID="source 1",
description="Source 1 data description",
location=[0.0, 0.0],
product_type="product 1",
time_model_id="time model 3",
routing_heuristic=prodsys.source_data.RoutingHeuristic.random,
output_queues= [queuesource1.ID],
)
#zweite
arrival_time_model2 = prodsys.time_model_data.FunctionTimeModelData(
ID="time model 4",
description="Time model 4 is create!",
type=prodsys.time_model_data.TimeModelEnum.FunctionTimeModel,
distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Exponential,
location=30, # noch mit anderer ausprobieren
scale=0,

)

source2 = prodsys.source_data.SourceData(
ID="source 2",
description="Source 1 data description",
location=[1.0, 1.0],
product_type="assemblyproduct",
time_model_id="time model 4",
routing_heuristic=prodsys.source_data.RoutingHeuristic.random,
output_queues= [queuesource2.ID],
)


# Create a sink to drop the product

sink = prodsys.sink_data.SinkData(
ID="sink 1",
description="Sink 1 data description",
location=[20.0, 20.0],
product_type="product 1",
input_queues= [queuesink1.ID],
)

# Create a sink to drop the product

sink2 = prodsys.sink_data.SinkData(
ID="sink 2",
description="Sink 2 data description",
location=[20.0, 20.0],
product_type="assemblyproduct",
input_queues= [queuesink2.ID],
)

production_system_instance = prodsys.production_system_data.ProductionSystemData(
time_model_data=[welding_time_model, transport_time_model, arrival_time_model, arrival_time_model2, assembly_time_model],
process_data=[transport_process, transport_process2, assembly_process],
resource_data=[machine, transport_resource],
product_data=[product, assemblyproduct],
source_data=[source, source2],
sink_data=[sink, sink2],
queue_data= [queuea,queuep, queueaofork2, queueaofork, queuesink2, queuesink1, queuesource1, queuesource2, queueout1, queueout2],

)

#add_default_queues_to_production_system(production_system_instance)
production_system_instance.validate_configuration()

runner = prodsys.runner.Runner(production_system_data=production_system_instance)
runner.initialize_simulation()
runner.run(100000)

runner.print_results()