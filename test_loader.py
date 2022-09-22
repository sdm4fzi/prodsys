from env import Environment
import loader
import print_util
from post_processing import PostProcessor


c = loader.CustomLoader()

c.add_time_model(type="FunctionTimeModels", ID="ft1", description="function time model 1", parameters=[300], batch_size=100, distribution_function="constant")
c.add_time_model(type="FunctionTimeModels", ID="ft2", description="function time model 2", parameters=[400], batch_size=100, distribution_function="constant")
c.add_time_model(type="FunctionTimeModels", ID="ft3", description="function time model 3", parameters=[13, 3], batch_size=100, distribution_function="normal")
c.add_time_model(type="FunctionTimeModels", ID="ft4", description="function time model 4", parameters=[12, 3], batch_size=100, distribution_function="constant")
c.add_time_model(type="FunctionTimeModels", ID="ft5", description="function time model 5", parameters=[27], batch_size=100, distribution_function="exponential")
c.add_time_model(type="FunctionTimeModels", ID="ft6", description="function time model 6", parameters=[25], batch_size=100, distribution_function="exponential")
c.add_time_model(type="HistoryTimeModels", ID="ht1", description="history time model 1", history=[14.3, 15.2, 21.1, 22.2, 19.3])
c.add_time_model(type="ManhattanDistanceTimeModel", ID="md1", description="manhattan time model 1", speed=12.3, reaction_time=0.15)

c.add_state(type="BreakDownState", ID="BS1", description="Breakdownstate 1 for machine 1", time_model_ID="ft1")
c.add_state(type="BreakDownState", ID="BS2", description="Breakdownstate 2 for machine 2", time_model_ID="ft2")


c.add_process(type="ProductionProcesses", ID="P1", description="Process 1", time_model_ID="ft3")
c.add_process(type="ProductionProcesses", ID="P2", description="Process 2", time_model_ID="ft4")
c.add_process(type="TransportProcesses", ID="TP1", description="Transport Process 1", time_model_ID="md1")

c.add_queue(ID="IQ1", description="Input queue 1", capacity=20)
c.add_queue(ID="IQ2", description="Input queue 2", capacity=10)
c.add_queue(ID="OQ1", description="Output queue 1", capacity=20)
c.add_queue(ID="OQ2", description="Output queue 2", capacity=10)
c.add_queue(ID="SourceQueue", description="Output queue for all sources")
c.add_queue(ID="SinkQueue", description="Input queue for all sinks")


c.add_material(ID="Material 1", description="Material 1", processes=["P2", "P1"], transport_process="TP1")
c.add_material(ID="Material 2", description="Material 2", processes=["P1", "P2"], transport_process="TP1")

c.add_resource(ID="M1", description="Machine 1", controller="SimpleController", control_policy="FIFO", location=[10, 10], capacity=2, processes=["P1", "P2"], states="BS1", input_queues=["IQ1"], output_queues=["OQ1"])
c.add_resource(ID="M2", description="Machine 2", controller="SimpleController", control_policy="SPT", location=[20, 10], capacity=1, processes=["P2"], states="BS2", input_queues=["IQ2"], output_queues=["OQ2"])
c.add_resource(ID="M3", description="Machine 3", controller="SimpleController", control_policy="FIFO", location=[20, 20], capacity=2, processes=["P1"], states="BS1", input_queues=["IQ1"], output_queues=["OQ2"])
c.add_resource(ID="M4", description="Machine 4", controller="SimpleController", control_policy="SPT", location=[10, 20], capacity=1, processes=["P2"], states="BS2", input_queues=["IQ1"], output_queues=["OQ2"])
c.add_resource(ID="TR1", description="Transport Resource 1", controller="TransportController", control_policy="SPT_transport", location=[10, 20], capacity=1, processes=["TP1"], states="BS1")

c.add_sink(ID="SK1", description="Sink 1 for material 1", location=[30, 30], material_type="Material 1", input_queues=["SinkQueue"])
c.add_sink(ID="SK2", description="Sink 2 for material 2", location=[35, 30], material_type="Material 2", input_queues=["SinkQueue"])


c.add_source(ID="S1", description="Source 1 for material 1", location=[5, 5], time_model_id="ft5", material_type="Material 1", router="SimpleRouter", output_queues="SourceQueue")
c.add_source(ID="S2", description="Source 2 for material 2", location=[8, 5], time_model_id="ft6", material_type="Material 2", router="SimpleRouter", output_queues="SourceQueue")

c.to_json("data/result.json")


e = Environment()
e.loader = c
e.initialize_simulation()


import time

t_0 = time.perf_counter()

e.run(40000)

t_1 = time.perf_counter()

print_util.print_simulation_info(e, t_0, t_1)    

e.data_collector.log_data_to_csv(filepath="data/data21.csv")


p = PostProcessor(filepath="data/data21.csv")
p.print_aggregated_data()