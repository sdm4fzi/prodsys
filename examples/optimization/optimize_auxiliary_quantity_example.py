from prodsys.optimization.evolutionary_algorithm import run_evolutionary_algorithm

seed = 23
NGEN = 9
POPULATION_SIZE = 16
N_PROCESSES = 4
NUMBER_OF_SEEDS = 1
CROSS_OVER_RATE = 0.1
MUTATION_RATE = 0.15

SAVE_FOLDER = "data/ea_results"
BASE_CONFIGURATION_FILE_PATH = "examples/optimization/optimization_example/simple_auxiliary_example.json"
SCENARIO_FILE_PATH = "examples/optimization/optimization_example/auxiliary_scenario.json"


if __name__ == "__main__":
    # Full optimization run
    run_evolutionary_algorithm(
        SAVE_FOLDER,
        BASE_CONFIGURATION_FILE_PATH,
        SCENARIO_FILE_PATH,
        False,
        seed,
        NGEN,
        POPULATION_SIZE,
        MUTATION_RATE,
        CROSS_OVER_RATE,
        NUMBER_OF_SEEDS,
        N_PROCESSES,
    )