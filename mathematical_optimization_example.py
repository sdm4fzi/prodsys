from prodsim import adapters
from prodsim.util.math_opt import MathOptimizer

import json

BASE_CONFIGURATION_FILE_PATH = "examples/optimization_example/base_scenario.json"
SCENARIO_FILE_PATH = "examples/optimization_example/scenario_mathopt.json"
adapter = adapters.JsonAdapter()
adapter.read_data(BASE_CONFIGURATION_FILE_PATH, SCENARIO_FILE_PATH)



model = MathOptimizer(adapter=adapter)
model.optimize()
model.save_model()
model.save_result_to_adapter()