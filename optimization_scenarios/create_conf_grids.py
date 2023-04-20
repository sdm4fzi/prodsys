import yaml
import pandas as pd

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
    with open("optimization_scenarios/conf/optimization/" + SCENARIO + "_" + filename + ".yaml", "w") as f:
        yaml.dump(conf, f)


def create_general_conf(filename):
    conf = {
        "mode": "optimization",
        "configuration_path": "base_configuration_" + SCENARIO + ".json",
        "scenario_path": "scenario_" + SCENARIO + ".json",
        "save_folder": "results/" + SCENARIO + "_" + filename,
    }
    with open("optimization_scenarios/conf/general/" + SCENARIO + "_" + filename + ".yaml", "w") as f:
        yaml.dump(conf, f)


algorithm = "evolutionary"
seed = 22
number_of_generations = [20, 40, 60]
number_of_individuals = [64, 128, 256, 512]
mutation_rates = [0.05, 0.15]
crossover_rates = [0.05, 0.15]
number_of_processes = 16

configurations = []

df = pd.DataFrame(columns=["number_of_generation", "number_of_individual", "mutation_rate", "crossover_rate", "filename"])


grid_runner_string = "ECHO Welcome to optimization of " + SCENARIO + "\n"

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
                df.loc[len(df)] = [
                    number_of_generation,
                    number_of_individual,
                    mutation_rate,
                    crossover_rate,
                    hyper_param_name,
                ]

                grid_runner_string += "CALL python hydra_app.py general=" + SCENARIO + "_" + hyper_param_name + " optimization=" + SCENARIO + "_" + hyper_param_name + "\n"
                grid_runner_string += "ECHO Finished optimization of " + hyper_param_name + "\n"
df.to_excel("hyper_parameter_grid_" +  SCENARIO + ".xlsx")
with open("optimization_scenarios/grid_runner_" + SCENARIO + ".bat", "w") as f:
    f.write(grid_runner_string)
