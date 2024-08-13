from prodsys.optimization.math_opt import run_mathematical_optimization


BASE_CONFIGURATION_FILE_PATH = "examples/optimization/optimization_example/base_scenario.json"
SCENARIO_FILE_PATH = "examples/optimization/optimization_example/scenario.json"
SAVE_FOLDER = "data/math_results"
OPTIMIZATION_TIME_PORTION = 0.1
NUMBER_OF_SOLUTIONS = 2
ADJUSTED_NUMBER_OF_TRANSPORT_RESOURCES = 2
NUMBER_OF_SEEDS = 2

run_mathematical_optimization(
    SAVE_FOLDER,
    BASE_CONFIGURATION_FILE_PATH,
    SCENARIO_FILE_PATH,
    OPTIMIZATION_TIME_PORTION,
    NUMBER_OF_SOLUTIONS,
    ADJUSTED_NUMBER_OF_TRANSPORT_RESOURCES,
    NUMBER_OF_SEEDS
)