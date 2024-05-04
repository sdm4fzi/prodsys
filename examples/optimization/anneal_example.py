from prodsys.optimization.simulated_annealing import run_simulated_annealing

SEED = 22
SAVE_FOLDER = "data/anneal_results"
BASE_CONFIGURATION_FILE_PATH = "examples/optimization/optimization_example/base_scenario.json"
SCENARIO_FILE_PATH = "examples/optimization/optimization_example/scenario.json"

TMAX = 10000
TMIN = 1
STEPS = 4000
UPDATES = 300

# full optimization
run_simulated_annealing(
    SAVE_FOLDER,
    BASE_CONFIGURATION_FILE_PATH,
    SCENARIO_FILE_PATH,
    SEED,
    TMAX,
    TMIN,
    STEPS,
    UPDATES,
)

PARTIAL_SCENARIO_FILE_PATH = "examples/optimization/optimization_example/scenario_partial.json"
INITIAL_SOLUTION_FILE_PATH = "examples/optimization/optimization_example/initial_solutions/f_0_6cf4ba93-d45f-11ed-9932-a670a3eb8803.json"

# partial optimization
# run_simulated_annealing(
#     SAVE_FOLDER,
#     BASE_CONFIGURATION_FILE_PATH,
#     PARTIAL_SCENARIO_FILE_PATH,
#     SEED,
#     TMAX,
#     TMIN,
#     STEPS,
#     UPDATES,
#     INITIAL_SOLUTION_FILE_PATH
# )