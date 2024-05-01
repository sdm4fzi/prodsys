import prodsys

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


# create a product

product = prodsys.product_data.ProductData(
    ID="product 1",
    description="Product 1 data description",
    processes=[welding_process.ID],
    transport_process=transport_process.ID
)

# Create a time model for product arrival in the system and a source that creates the product

arrival_time_model = prodsys.time_model_data.FunctionTimeModelData(
    ID="time model 3",
    description="Time model 3 is create!",
    type=prodsys.time_model_data.TimeModelEnum.FunctionTimeModel,
    distribution_function=prodsys.time_model_data.FunctionTimeModelEnum.Exponential,
    location=30,
    scale=0
)

source = prodsys.source_data.SourceData(
    ID="source 1",
    description="Source 1 data description",
    location=[0.0, 0.0],
    product_type="product 1",
    time_model_id="time model 3",
    routing_heuristic=prodsys.source_data.RoutingHeuristic.random,
)

# Create a sink to drop the product

sink = prodsys.sink_data.SinkData(
    ID="sink 1",
    description="Sink 1 data description",
    location=[20.0, 20.0],
    product_type="product 1",
)

production_system = prodsys.adapters.JsonProductionSystemAdapter(
    time_model_data=[welding_time_model, transport_time_model, arrival_time_model],
    process_data=[welding_process, transport_process],
    resource_data=[machine, transport_resource],
    product_data=[product],
    source_data=[source],
    sink_data=[sink],
    )


production_system.validate_configuration()

runner = prodsys.runner.Runner(adapter=production_system)
runner.initialize_simulation()
runner.run(100000)


runner.print_results()




