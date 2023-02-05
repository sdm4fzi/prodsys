from prodsim import adapters
from prodsim.util.math_opt import MathOptimizer

import json

with open("data/scenario mathopt.json") as json_file:
    scenario_dict = json.load(json_file)
adapter = adapters.JsonAdapter()
# base_scenario.read_data('data/example_configuration.json')
adapter.read_data('data/base_scenario_new.json')



model = MathOptimizer(adapter=adapter, scenario_dict=scenario_dict)
model.optimize()
model.save_model()
model.save_result_to_adapter()