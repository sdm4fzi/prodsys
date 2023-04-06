from prodsim.util.simulated_annealing import run_simulated_annealing

SEED = 22
SAVE_FOLDER = "data/anneal_results"
BASE_CONFIGURATION_FILE_PATH = "examples/optimization_example/base_scenario.json"
SCENARIO_FILE_PATH = "examples/optimization_example/scenario.json"

Tmax = 10000
Tmin = 0.67
steps = 4000
updates = 300

run_simulated_annealing(SAVE_FOLDER, BASE_CONFIGURATION_FILE_PATH, SCENARIO_FILE_PATH, SEED, Tmax, Tmin, steps, updates)