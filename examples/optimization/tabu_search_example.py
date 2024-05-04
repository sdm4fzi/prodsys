from prodsys.optimization.tabu_search import run_tabu_search
from prodsys.simulation import sim

sim.VERBOSE = 0

SEED = 22

SAVE_FOLDER = "data/tabu_results"
BASE_CONFIGURATION_FILE_PATH = "examples/optimization/optimization_example/base_scenario.json"
SCENARIO_FILE_PATH = "examples/optimization/optimization_example/scenario.json"

TABU_SIZE = 10
MAX_STEPS = 300
MAX_SCORE = 500

# full optimization
run_tabu_search(
    SAVE_FOLDER,
    BASE_CONFIGURATION_FILE_PATH,
    SCENARIO_FILE_PATH,
    SEED,
    TABU_SIZE,
    MAX_STEPS,
    MAX_SCORE,
)

PARTIAL_SCENARIO_FILE_PATH = "examples/optimization/optimization_example/scenario_partial.json"
INITIAL_SOLUTION_FILE_PATH = "examples/optimization/optimization_example/initial_solutions/f_0_6cf4ba93-d45f-11ed-9932-a670a3eb8803.json"

# partial optimization
# run_tabu_search(
#     SAVE_FOLDER,
#     BASE_CONFIGURATION_FILE_PATH,
#     PARTIAL_SCENARIO_FILE_PATH,
#     SEED,
#     TABU_SIZE,
#     MAX_STEPS,
#     MAX_SCORE,
#     INITIAL_SOLUTION_FILE_PATH
# )