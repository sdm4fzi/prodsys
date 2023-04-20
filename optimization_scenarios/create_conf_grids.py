import yaml

SCENARIO = "H1"

def create_hyperparameter_conf_and_save(
    filename, number_of_generation, number_of_individual, mutation_rate, crossover_rate
):
    conf = {
        "algorithm": algorithm,
        "seed": seed,
        "number_of_generations": number_of_generation,
        "number_of_individuals": number_of_individual,
        "mutation_rate": mutation_rate,
        "crossover_rate": crossover_rate,
        "number_of_processes": number_of_processes,
    }
    with open("optimizationonf/optimization/" + SCENARIO + "_" + filename + ".yaml", "w") as f:
        yaml.dump(conf, f)


def create_general_conf(filename):
    conf = {
        "mode": "optimization",
        "configuration_path": "base_configuration_" + SCENARIO + ".json",
        "scenario_path": "scenario_" + SCENARIO + ".json",
        "save_folder": "results/" + SCENARIO,
    }
    with open("conf/general/" + SCENARIO + "_" + filename + ".yaml", "w") as f:
        yaml.dump(conf, f)


algorithm = "evolutionary"
seed = 22
number_of_generations = [20, 30, 40, 50, 60]
number_of_individuals = [64, 128, 256, 512]
mutation_rates = [0.01, 0.05, 0.1, 0.2]
crossover_rates = [0.01, 0.05, 0.1, 0.2]
number_of_processes = 16

configurations = []

for number_of_generation in number_of_generations:
    for number_of_individual in number_of_individuals:
        for mutation_rate in mutation_rates:
            for crossover_rate in crossover_rates:
                hyper_param_name = "conf_{}_{}_{}_{}".format(
                    number_of_generation,
                    number_of_individual,
                    mutation_rate,
                    crossover_rate,
                )
                create_hyperparameter_conf_and_save(
                    hyper_param_name,
                    number_of_generation,
                    number_of_individual,
                    mutation_rate,
                    crossover_rate,
                )
                create_general_conf(hyper_param_name)
