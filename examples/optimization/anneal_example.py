from prodsys.optimization.simulated_annealing import run_simulated_annealing

SEED = 22
SAVE_FOLDER = "data/anneal_results"
BASE_CONFIGURATION_FILE_PATH = (
    "examples/optimization/optimization_example/base_scenario.json"
)
SCENARIO_FILE_PATH = "examples/optimization/optimization_example/scenario.json"

TMAX = 10000
TMIN = 1
STEPS = 4000
UPDATES = 300
NUMBER_OF_SEEDS = 2

# full optimization
run_simulated_annealing(
    SAVE_FOLDER,
    BASE_CONFIGURATION_FILE_PATH,
    SCENARIO_FILE_PATH,
    False,
    SEED,
    TMAX,
    TMIN,
    STEPS,
    UPDATES,
    NUMBER_OF_SEEDS,
)

PARTIAL_SCENARIO_FILE_PATH = (
    "examples/optimization/optimization_example/scenario_partial.json"
)
INITIAL_SOLUTION_FILE_PATH = "examples/optimization/optimization_example/initial_solutions/generation_9_6524d80a-6ba7-11ef-a586-845cf38935ae.json"

# partial optimization
# run_simulated_annealing(
#     SAVE_FOLDER,
#     BASE_CONFIGURATION_FILE_PATH,
#     PARTIAL_SCENARIO_FILE_PATH,
#     False,
#     SEED,
#     TMAX,
#     TMIN,
#     STEPS,
#     UPDATES,
#     NUMBER_OF_SEEDS,
#     INITIAL_SOLUTION_FILE_PATH
# )
