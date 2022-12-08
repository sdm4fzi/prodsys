from prodsim import loader, print_util
from prodsim.sim import Environment
from prodsim.post_processing import PostProcessor

c = loader.CustomLoader()

c.add_time_model(type="FunctionTimeModels", ID="ftmp1", description="function time model process 1", parameters=[50/60, 5/60], batch_size=100, distribution_function="normal")
c.add_time_model(type="FunctionTimeModels", ID="ftmp2", description="function time model process 2", parameters=[250/60, 25/60], batch_size=100, distribution_function="normal")
c.add_time_model(type="FunctionTimeModels", ID="ftmp3", description="function time model process 3", parameters=[40/60, 4/60], batch_size=100, distribution_function="normal")
c.add_time_model(type="FunctionTimeModels", ID="ftmp4", description="function time model process 4", parameters=[180/60, 18/60], batch_size=100, distribution_function="normal")
c.add_time_model(type="FunctionTimeModels", ID="ftmp5", description="function time model process 5", parameters=[40/60, 4/60], batch_size=100, distribution_function="normal")


c.add_time_model(type="FunctionTimeModels", ID="ftbs1", description="function time model breakdwon state 1", parameters=[700, 4], batch_size=100, distribution_function="exponential")
c.add_time_model(type="FunctionTimeModels", ID="ftbs2", description="function time model breakdwon state 2", parameters=[1100, 4], batch_size=100, distribution_function="exponential")

# c.add_time_model(type="FunctionTimeModels", ID="ftm1", description="function time model material 1", parameters=[183.6 / 60, 5], batch_size=100, distribution_function="exponential")
# c.add_time_model(type="FunctionTimeModels", ID="ftm1", description="function time model material 1", parameters=[200 / 60, 5], batch_size=100, distribution_function="exponential")
c.add_time_model(type="FunctionTimeModels", ID="ftm1", description="function time model material 1", parameters=[200 / 60, 5], batch_size=100, distribution_function="exponential")
# c.add_time_model(type="FunctionTimeModels", ID="ftm2", description="function time model material 2", parameters=[50, 5], batch_size=100, distribution_function="normal")


c.add_time_model(type="ManhattanDistanceTimeModel", ID="md1", description="manhattan time model 1", speed=60, reaction_time=2 / 60)


c.add_state(type="BreakDownState", ID="BS1", description="Breakdownstate for machine", time_model_ID="ftbs1")
c.add_state(type="BreakDownState", ID="BS2", description="Breakdownstate for transport resource", time_model_ID="ftbs2")


c.add_process(type="ProductionProcesses", ID="P1", description="Process 1", time_model_ID="ftmp1")
c.add_process(type="ProductionProcesses", ID="P2", description="Process 2", time_model_ID="ftmp2")
c.add_process(type="ProductionProcesses", ID="P3", description="Process 3", time_model_ID="ftmp3")
c.add_process(type="ProductionProcesses", ID="P4", description="Process 4", time_model_ID="ftmp4")
c.add_process(type="ProductionProcesses", ID="P5", description="Process 5", time_model_ID="ftmp5")

c.add_process(type="TransportProcesses", ID="TP1", description="Transport Process 1", time_model_ID="md1")



c.add_material(ID="Material 1", description="Material 1", processes=["P1", "P2", "P3", "P4", "P5"], transport_process="TP1")
# c.add_material(ID="Material 2", description="Material 2", processes=["P1", "P2"], transport_process="TP1")

c.add_queue(ID="SourceQueue", description="Output queue for all sources")
c.add_queue(ID="SinkQueue", description="Input queue for all sinks")


c.add_sink(ID="SK1", description="Sink 1 for material 1", location=[30, 30], material_type="Material 1", input_queues=["SinkQueue"])
# c.add_sink(ID="SK2", description="Sink 2 for material 2", location=[35, 30], material_type="Material 2", input_queues=["SinkQueue"])


c.add_source(ID="S1", description="Source 1 for material 1", location=[-5, -5], time_model_id="ftm1", material_type="Material 1", router="AvoidDeadlockRouter", routing_heuristic="shortest_queue", output_queues="SourceQueue")
# c.add_source(ID="S2", description="Source 2 for material 2", location=[8, 5], time_model_id="ft6", material_type="Material 2", router="SimpleRouter", output_queues="SourceQueue")


############################################ dynamic stuff

capacity = 100

c.add_resource_with_default_queue(ID="M1", description="Machine 1", controller="SimpleController", control_policy="FIFO", location=[0, 0], capacity=1, processes=["P1", "P3"], states="BS1", queue_capacity=capacity)
c.add_resource_with_default_queue(ID="M2", description="Machine 2", controller="SimpleController", control_policy="SPT", location=[0, 5], capacity=1, processes=["P2", "P5"], states="BS1", queue_capacity=capacity)
c.add_resource_with_default_queue(ID="M3", description="Machine 3", controller="SimpleController", control_policy="FIFO", location=[5, 0], capacity=1, processes=["P4"], states="BS1", queue_capacity=capacity)
c.add_resource_with_default_queue(ID="M4", description="Machine 4", controller="SimpleController", control_policy="FIFO", location=[5, 5], capacity=1, processes=["P2"], states="BS1", queue_capacity=capacity)

c.add_resource(ID="TR1", description="Transport Resource 1", controller="TransportController", control_policy="SPT_transport", location=[0, 10], capacity=1, processes=["TP1"], states="BS2")

# c.to_json("data/base_scenario.json")
c.to_json("data/example_configuration.json")


e = Environment()
e.loader = c
e.initialize_simulation()


import time

t_0 = time.perf_counter()

e.run(10000)

t_1 = time.perf_counter()

print_util.print_simulation_info(e, t_0, t_1)    

e.data_collector.log_data_to_csv(filepath="data/data21.csv")


p = PostProcessor(filepath="data/data21.csv")
# p.print_aggregated_data()
p.plot_WIP()
p.plot_throughput_over_time()
p.plot_time_per_state_of_resources()