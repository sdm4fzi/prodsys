from prodsim.util.evolutionary_algorithm import run_evolutionary_algorithm

seed = 22
NGEN = 9
POPULATION_SIZE = 8
N_PROCESSES = 8

SAVE_FOLDER = "data/ea_results"
BASE_CONFIGURATION_FILE_PATH = "examples/optimization_example/base_scenario.json"
SCENARIO_FILE_PATH = "examples/optimization_example/scenario.json"



if __name__ == "__main__":
    run_evolutionary_algorithm(SAVE_FOLDER, BASE_CONFIGURATION_FILE_PATH, SCENARIO_FILE_PATH, seed, NGEN, POPULATION_SIZE, N_PROCESSES)