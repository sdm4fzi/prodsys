import json
from prodsim import adapters
from prodsim.util import optimization_util
from multiprocessing import Pool
from functools import partial


if __name__ == '__main__':

    with open("data/scenario.json") as json_file:
        scenario_dict = json.load(json_file)
    base_scenario = adapters.JsonAdapter()
    base_scenario.read_data('data/example_configuration.json')
    adapter_object = optimization_util.random_configuration(scenario_dict, base_scenario)
    new_adapters = []
    for operation in [
            optimization_util.add_machine,
            optimization_util.add_transport_resource,
            optimization_util.add_process_module,
            optimization_util.remove_machine,
            optimization_util.remove_transport_resource,
            optimization_util.remove_process_module,
            optimization_util.move_machine,
            optimization_util.move_process_module,
            optimization_util.change_control_policy,
        ] * 10:

        operation(adapter_object, scenario_dict)
        new_adapters.append([adapter_object.copy(deep=True)])
        # optimization_util.evaluate([adapter_object], scenario_dict, base_scenario, {"current_generation": "0", "0": []}, {"0": {}}, "data")

    kwargs = {
        "scenario_dict": scenario_dict,
        "base_scenario": base_scenario,
        "solution_dict": {"current_generation": "0", "0": []},
        "performances": {"0": {}},
        "save_folder": "data"
    }

    with Pool(8) as p:
        print(p.map(partial(optimization_util.evaluate, **kwargs), new_adapters))