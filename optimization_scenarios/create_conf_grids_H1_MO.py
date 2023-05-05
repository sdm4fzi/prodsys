import yaml
import pandas as pd

SCENARIO = "H1"

def create_hyperparameter_conf_and_save(
    filename, number_of_solutions, optimization_time_portion, adjusted_number_of_transport_resources, save_model
):
    conf = {
        "algorithm": algorithm,
        "n_solutions": number_of_solutions,
        "optimization_time_portion": optimization_time_portion,
        "adjusted_number_of_transport_resources": adjusted_number_of_transport_resources,
        "save_model": save_model
    }
    with open("conf/optimization/" + SCENARIO + "_MO_" + filename + ".yaml", "w") as f:
        yaml.dump(conf, f)


def create_general_conf(filename):
    conf = {
        "mode": "optimization",
        "configuration_path": "base_configuration_" + SCENARIO + ".json",
        "scenario_path": "scenario_" + SCENARIO + ".json",
        "save_folder": "results/" + SCENARIO + "_MO_" + filename,
    }
    with open("conf/general/" + SCENARIO + "_MO_" + filename + ".yaml", "w") as f:
        yaml.dump(conf, f)


algorithm = "mathematical"
n_solutions = [1, 2, 3, 4]
optimization_time_portion = [0.1, 0.25, 0.5, 1]
adjusted_number_of_transport_resources = 2
save_model = True

configurations = []

df = pd.DataFrame(columns=["n_solutions", "optimization_time_portion", "filename"])


grid_runner_string = "ECHO Welcome to optimization of " + SCENARIO + "with MO\n"

for n_solution in n_solutions:
    for optimization_time in optimization_time_portion:
        hyper_param_name = "conf_{}_{}".format(
            n_solution,
            optimization_time,
        )
        create_hyperparameter_conf_and_save(
            hyper_param_name,
            n_solution,
            optimization_time,
            adjusted_number_of_transport_resources,
            save_model,
        )
        create_general_conf(hyper_param_name)
        df.loc[len(df)] = [
            n_solution,
            optimization_time,
            hyper_param_name,
        ]

        grid_runner_string += "CALL python hydra_app.py general=" + SCENARIO + "_MO_" + hyper_param_name + " optimization=" + SCENARIO + "_MO_" + hyper_param_name + "\n"
        grid_runner_string += "ECHO Finished optimization of " + hyper_param_name + "\n"
df.to_excel("hyper_parameter_grid_" +  SCENARIO + "_MO.xlsx")
with open("grid_runner_" + SCENARIO + "_MO.bat", "w") as f:
    f.write(grid_runner_string)
