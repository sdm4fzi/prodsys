import prodsys.express as psx
import prodsys
from prodsys.models import port_data

print("version used:", prodsys.VERSION)
prodsys.set_logging("DEBUG")

t1 = psx.FunctionTimeModel("normal", 1, 0.1, "t1")
t2 = psx.FunctionTimeModel("normal", 2, 0.2, "t2")

p1 = psx.ProductionProcess(t1, "p1")
p2 = psx.ProductionProcess(t2, "p2")

t3 = psx.DistanceTimeModel(speed=180, reaction_time=0.1, ID="t3")

tp = psx.TransportProcess(t3, "tp")

s1 = psx.FunctionTimeModel("exponential", 0.5, ID="s1")
setup_state_1 = psx.SetupState(s1, p1, p2, "S1")
setup_state_2 = psx.SetupState(s1, p2, p1, "S2")

machine = psx.Resource(
    [p1],
    [5, 0],
    2,
    states=[setup_state_1, setup_state_2],
    ID="machine",
)
machine2 = psx.Resource(
    [p2],
    [7, 0],
    2,
    states=[setup_state_1, setup_state_2],
    ID="machine2",
)

def set_input_output_queues(resource: psx.Resource):
    resource.ports = [
        psx.Queue(
            ID=f"{resource.ID}_input",
            capacity=1,  # Test with queue size 1 to verify deadlock prevention
            location=resource.location,
            interface_type=port_data.PortInterfaceType.INPUT,
        ),
        psx.Queue(
            ID=f"{resource.ID}_output",
            capacity=1,  # Test with queue size 1 to verify deadlock prevention
            location=resource.location,
            interface_type=port_data.PortInterfaceType.OUTPUT
        )
    ]

def set_input_output_queue(resource: psx.Resource):
    resource.ports = [
        psx.Queue(
            ID=f"{resource.ID}_input",
            capacity=1,  # Test with queue size 1 to verify deadlock prevention
            location=resource.location,
            interface_type=port_data.PortInterfaceType.INPUT_OUTPUT,
        ),
    ]

set_input_output_queue(machine)
set_input_output_queue(machine2)

transport = psx.Resource([tp], [2, 0], 1, ID="transport")

product1 = psx.Product([p1, p2], tp, "product1")
product2 = psx.Product([p1, p2], tp, "product2")

sink1 = psx.Sink(product1, [10, 0], "sink1")
sink2 = psx.Sink(product2, [10, 0], "sink2")


arrival_model_1 = psx.FunctionTimeModel("exponential", 1, ID="arrival_model_1")
arrival_model_2 = psx.FunctionTimeModel("exponential", 2, ID="arrival_model_2")


source1 = psx.Source(product1, arrival_model_1, [0, 0], ID="source_1")
source2 = psx.Source(product2, arrival_model_2, [0, 0], ID="source_2")


system = psx.ProductionSystem(
    [machine, machine2, transport], [source1, source2], [sink1, sink2]
)
model = system.to_model()
from prodsys import runner

runner_instance = runner.Runner(production_system_data=model)
runner_instance.initialize_simulation()
system.run(1000)

runner_instance = system.runner

runner_instance.print_results()
runner_instance.plot_results()
runner_instance.save_results_as_csv()
