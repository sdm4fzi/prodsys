import prodsys

production_system = prodsys.adapters.JsonAdapter(ID="example_production_system", seed=2)

# Create a time model for a production process and a transport process

welding_time_model = prodsys.time_model_data.FunctionTimeModelData(
    ID="time model 1",
    description="Time model 1 is create!",
    distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Exponential,
    location=25.0,
    scale=0.0
)

transport_time_model = prodsys.time_model_data.ManhattanDistanceTimeModelData(
    ID="time model 2",
    description="Time model 2 is create!",
    speed=5.0,
    reaction_time=0.0,
)


# create a process to produce a part and a process to transport it

welding_process = prodsys.processes_data.ProductionProcessData(
    ID="Welding",
    description="Welding process",
    time_model_id=welding_time_model.ID,
    type=prodsys.processes_data.ProcessTypeEnum.ProductionProcesses,
)

transport_process = prodsys.processes_data.TransportProcessData(
    ID="NormalTransport",
    description="Normal transport process",
    time_model_id=transport_time_model.ID,
    type=prodsys.processes_data.ProcessTypeEnum.TransportProcesses,
)

# Create a production resource

machine = prodsys.resource_data.ProductionResourceData(
    ID="machine 1",
    description="Machine 1 data description",
    capacity=2,
    location=[10.0, 10.0],
    controller=prodsys.resource_data.ControllerEnum.PipelineController,
    control_policy=prodsys.resource_data.ResourceControlPolicy.FIFO,
    process_ids=[welding_process.ID],
)

machine_queues = prodsys.adapters.get_default_queues_for_resource(resource=machine, queue_capacity=3)

# create a transport resource

transport_resource = prodsys.resource_data.TransportResourceData(
    ID="Forklift1",
    description="Forklift 1 data description",
    capacity=1,
    location=[5.0, 0.0],
    controller=prodsys.resource_data.ControllerEnum.TransportController,
    control_policy=prodsys.resource_data.TransportControlPolicy.SPT_transport,
    process_ids=[transport_process.ID],
)


# create a material

material = prodsys.material_data.MaterialData(
    ID="material 1",
    description="Material 1 data description",
    processes=[welding_process.ID],
    transport_process=transport_process.ID
)

# Create a time model for material arrival in the system and a source that creates the material

arrival_time_model = prodsys.time_model_data.FunctionTimeModelData(
    ID="time model 3",
    description="Time model 3 is create!",
    type=prodsys.time_model_data.TimeModelEnum.FunctionTimeModel,
    distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Exponential,
    location=30,
    scale=0
)

source_q = prodsys.queue_data.QueueData(
    ID="SourceQueue",
    description="Source queue",
)


sink_q = prodsys.queue_data.QueueData(
    ID="SinkQueue",
    description="Sink queue",
)



source = prodsys.source_data.SourceData(
    ID="source 1",
    description="Source 1 data description",
    location=[0.0, 0.0],
    material_type="material 1",
    time_model_id="time model 3",
    router=prodsys.source_data.RouterType.SimpleRouter,
    routing_heuristic=prodsys.source_data.RoutingHeuristic.random,
    output_queues=["SourceQueue"],
)

# Create a sink to drop the material

sink = prodsys.sink_data.SinkData(
    ID="sink 1",
    description="Sink 1 data description",
    location=[20.0, 20.0],
    material_type="material 1",
    input_queues=["SinkQueue"],
)
    

production_system.time_model_data = [welding_time_model, transport_time_model, arrival_time_model]
production_system.process_data = [welding_process, transport_process]
production_system.resource_data = [machine, transport_resource]
production_system.material_data = [material]
production_system.queue_data = [source_q, sink_q] + machine_queues[0] + machine_queues[1]
production_system.source_data = [source]
production_system.sink_data = [sink]

runner = prodsys.runner.Runner(adapter=production_system)
runner.initialize_simulation()
runner.run(100000)


runner.print_results()




