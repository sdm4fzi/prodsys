from prodsys.optimization.tabu_search import run_tabu_search
from prodsys.simulation import sim

sim.VERBOSE = 1

SEED = 22

SAVE_FOLDER = "data/tabu_results"
BASE_CONFIGURATION_FILE_PATH = "examples/optimization/optimization_example/base_scenario.json"
SCENARIO_FILE_PATH = "examples/optimization/optimization_example/scenario.json"

TABU_SIZE = 10
MAX_STEPS = 300
MAX_SCORE = 500
NUMBER_OF_SEEDS = 2

# full optimization
run_tabu_search(
    SAVE_FOLDER,
    BASE_CONFIGURATION_FILE_PATH,
    SCENARIO_FILE_PATH,
    SEED,
    TABU_SIZE,
    MAX_STEPS,
    MAX_SCORE,
    NUMBER_OF_SEEDS,
    full_save=False
)

PARTIAL_SCENARIO_FILE_PATH = "examples/optimization/optimization_example/scenario_partial.json"
INITIAL_SOLUTION_FILE_PATH = "examples/optimization/optimization_example/initial_solutions/generation_9_6524d80a-6ba7-11ef-a586-845cf38935ae.json"

# partial optimization
# run_tabu_search(
#     SAVE_FOLDER,
#     BASE_CONFIGURATION_FILE_PATH,
#     PARTIAL_SCENARIO_FILE_PATH,
#     SEED,
#     TABU_SIZE,
#     MAX_STEPS,
#     MAX_SCORE,
#     NUMBER_OF_SEEDS,
#     INITIAL_SOLUTION_FILE_PATH
# )