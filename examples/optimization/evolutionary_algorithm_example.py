from prodsys.optimization.evolutionary_algorithm import run_evolutionary_algorithm

seed = 23
NGEN = 9
POPULATION_SIZE = 8
N_PROCESSES = 8
CROSS_OVER_RATE = 0.1
MUTATION_RATE = 0.15

SAVE_FOLDER = "data/ea_results"
BASE_CONFIGURATION_FILE_PATH = "examples/optimization/optimization_example/base_scenario.json"
SCENARIO_FILE_PATH = "examples/optimization/optimization_example/scenario.json"

PARTIAL_SCENARIO_FILE_PATH = "examples/optimization/optimization_example/scenario_partial.json"
INITIAL_SOLUTION_FOLDER = "examples/optimization/optimization_example/initial_solutions"


if __name__ == "__main__":
    # Full optimization run
    run_evolutionary_algorithm(
        SAVE_FOLDER,
        BASE_CONFIGURATION_FILE_PATH,
        SCENARIO_FILE_PATH,
        seed,
        NGEN,
        POPULATION_SIZE,
        MUTATION_RATE,
        CROSS_OVER_RATE,
        N_PROCESSES,
    )

    # Partial optimization with initial solutions
    # run_evolutionary_algorithm(
    #     SAVE_FOLDER,
    #     BASE_CONFIGURATION_FILE_PATH,
    #     PARTIAL_SCENARIO_FILE_PATH,
    #     seed,
    #     NGEN,
    #     POPULATION_SIZE,
    #     MUTATION_RATE,
    #     CROSS_OVER_RATE,
    #     N_PROCESSES,
    #     INITIAL_SOLUTION_FOLDER
    # )
