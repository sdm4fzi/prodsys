import prodsys
from prodsys.models.production_system_data import (
add_default_queues_to_production_system,
)
# EventLogger importieren
from prodsys.simulation.logger import EventLogger

# EventLogger initialisieren
event_logger = EventLogger()
from prodsys.models.port_data import Queue_Per_Product_Data
from prodsys.util import post_processing
from prodsys.models.port_data import PortInterfaceType


# Create a time model for a production process and a transport process

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





product_process = prodsys.processes_data.ProductionProcessData(
ID="product",
description="product_process",
time_model_id=welding_time_model.ID,
type=prodsys.processes_data.ProcessTypeEnum.ProductionProcesses,
)

machine = prodsys.resource_data.ResourceData(
ID="machine 1",
description="Machine 1 data description",
capacity=1,
location=[10.0, 10.0],
controller=prodsys.resource_data.ControllerEnum.PipelineController,
control_policy=prodsys.resource_data.ResourceControlPolicy.FIFO,
process_ids=[product_process.ID],
is_dedicated=True,
)





transport_resource = prodsys.resource_data.ResourceData(
ID="Forklift1",
description="Forklift 1 data description",
capacity=1,
location=[5.0, 0.0],
controller=prodsys.resource_data.ControllerEnum.PipelineController,
control_policy=prodsys.resource_data.TransportControlPolicy.SPT_transport,
process_ids=[transport_process.ID],
   
   

)


product = prodsys.product_data.ProductData(
ID="product 1",
description="Product 1 data description",
type="product 1",
processes=[product_process.ID],
transport_process=transport_process.ID,

)
assemblyproduct = prodsys.product_data.ProductData(
ID="assemblyproduct",
description="Productsdsd 1 data description",
type="assemblyproduct",
processes=[product_process.ID],
transport_process=transport_process.ID,

)

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

)

source2 = prodsys.source_data.SourceData(
ID="source 2",
description="Source 1 data description",
location=[0.0, 0.0],
product_type="assemblyproduct",
time_model_id="time model 3",
routing_heuristic=prodsys.source_data.RoutingHeuristic.random,

)


# Create a sink to drop the product

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
product_type="assemblyproduct",


)

# Create a sink to drop the product



production_system_instance = prodsys.production_system_data.ProductionSystemData(
time_model_data=[welding_time_model, transport_time_model, arrival_time_model,],
process_data=[transport_process,product_process],
resource_data=[machine, transport_resource],
product_data=[product, assemblyproduct],
source_data=[source, source2],
sink_data=[sink, sink2],

)



#TODO um Assemblyprozesse etc.. kümmern 


add_default_queues_to_production_system(production_system_instance)
production_system_instance.validate_configuration()

runner = prodsys.runner.Runner(production_system_data=production_system_instance)
runner.initialize_simulation()

runner.run(10000)

runner.print_results()

#runner.save_results_as_csv("test")


#FIXME Komisches Verhalten, wenn wenig Kapazität bzw. unterschiedlich große Output zu Inputqueues und umgekehrt siehe unten


















































'''
#TODO Am ENde counter schreiben, wieviele sachen in einer Queue sind
#FACT Warum kommt der Production Prozess bevor dahin transportiert wurde? ich glaube, weil der Transportprozess erst angefragt wird, nachdem der Prozess die Produktionsressource angefragt hat
#FIXME Wahre üproblem: Es wird irgendwann nur noch geputtet und nichts mehr getgettet. Problem liegt vielleicht bei den Transportressourcen, dass die irgendwann geblockt ist
#FIXME: Debugging: 1. capas von prodressourcequeues erhöhen und gucken, ob öfter gegettett wird -> Deadlock vom Forklift
#FIXME bleiebt Forklift am Ende bei sink stehen? weil es wird einmal finished good registered??
#FIXME die Freigabe der Transportresssource nachdem sie in die sink gegangen ist. diese erfolgt vieleleciht nicht?
#FIXME läuft der Transportprozess, wenn ich ihn printe im Router ab oder nur die request? Also nicht der Transportprozess an sich
#FIXME Queue der Source läuft voll -> es wird wirklich nichts rausgeholt
#FIXME Chatgpt Debugging verwenden
#FIXME AGV von Jonas gucken, wie die Queues von Transportressource definiert sind
#FIXME Wird von AGVS
#FIXME COnveer probieren
#FIXME ALles auf einem FLeck (queues auf sinkqueue plazieren ) -> muss an Transport liegen
#FIXME automazische queuezuweisung bei AGVs gucken
#FIXME Eventlog ausgeben lassen!
#FIXME Moriz fragen, wo er diesen Eventlog her hat
#Fact die Source ruft auch die put-Funktion auf 
#FIXME SOLUTION: Transportressource bleibt voll einfach vor Ressourcequeue stehen, weil diese voll ist!!!
#FIXME Was mich noch wundert ist, dass egal welche Zeiten ich eingebe, Zuerst Produkt 1_2 gegettet wird, obwohl der Produktiionsprozess direkt fertig ist ? -> nochmal mit höherer Sourcezeit probieren. 

#FIXME REASON: log confirms it: transporteinheit bleibt vor Ressource stehen ( wahsctheinlich weil kapa voll ist)
#FIXME WEnn ich capa erhöhe von REssource inputqueue: wirft Error: Queue voll!! Selbst wenn ich alle inputqueues hochsetze. Erst wenn outputqueues auch angepasst werden, geht es wieder waeiter
#FIXME Wenn outputqueue hochgesetzt wird, inputqueues aber nicht, wirft es auch keinen Fehler 
#FIXME: ! 1. gucken ob input und outputqueue richtig capamäßig hochgesetzt wird. 2. capa index nachgucken welcher vermittelt, wann die queue voll ist: Wird wahrscheinich nicht upgedatet!!!!!
''''''
hier ist NICHT das Problem:! Wahscheinlich unabhängig voneinander, beim produzieren wird immer was in die SOurce gelegt mit put
hier wird geputtet in
ID='Produkt1_Inputqueue' description='productarriba' capacity=2 product='product 1'
0
hier wird geputtet in
ID='Sourcequeue' description='asdasas23adda' capacity=500
1'''