import json
from prodsim import adapters
from prodsim.util import optimization_util

with open("data/scenario.json") as json_file:
    scenario_dict = json.load(json_file)
base_scenario = adapters.JsonAdapter()
base_scenario.read_data('data/example_configuration.json')
adapter_object = optimization_util.random_configuration(scenario_dict, base_scenario)
for operation in [
        optimization_util.add_machine,
        optimization_util.add_transport_resource,
        optimization_util.add_process_module,
        # optimization_util.remove_machine,
        # optimization_util.remove_transport_resource,
        # optimization_util.remove_process_module,
        optimization_util.move_machine,
        optimization_util.move_process_module,
        optimization_util.change_control_policy,
    ] * 1000:
    operation(adapter_object, scenario_dict)
    # TODO: add default queues to production resources!
    optimization_util.evaluate(scenario_dict, base_scenario, {"current_generation": "0", "0": []}, {"0": {}}, "data", [adapter_object])