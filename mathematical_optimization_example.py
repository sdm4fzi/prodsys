from prodsim import adapters
from prodsim.util.math_opt import MathOptimizer
BASE_CONFIGURATION_FILE_PATH = "examples/optimization_example/base_scenario.json"
SCENARIO_FILE_PATH = "examples/optimization_example/scenario.json"
SAVE_FOLDER = "data/math_results"
adapter = adapters.JsonAdapter()
adapter.read_data(BASE_CONFIGURATION_FILE_PATH, SCENARIO_FILE_PATH)



model = MathOptimizer(adapter=adapter, optimization_time_portion=0.4)
model.optimize(n_solutions=2)
model.save_model(save_folder=SAVE_FOLDER)
model.save_results(save_folder=SAVE_FOLDER, adjusted_number_of_transport_resources=2)