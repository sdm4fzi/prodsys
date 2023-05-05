import yaml
import pandas as pd

SCENARIO = "H1"

def create_hyperparameter_conf_and_save(
    filename, max_temp, min_temp, steps, updates
):
    conf = {
        "algorithm": algorithm,
        "seed": seed,
        "Tmax": max_temp,
        "Tmin": min_temp,
        "steps": steps,
        "updates": updates
    }
    with open("conf/optimization/" + SCENARIO + "_SA_" + filename + ".yaml", "w") as f:
        yaml.dump(conf, f)


def create_general_conf(filename):
    conf = {
        "mode": "optimization",
        "configuration_path": "base_configuration_" + SCENARIO + ".json",
        "scenario_path": "scenario_" + SCENARIO + ".json",
        "save_folder": "results/" + SCENARIO + "_SA_" + filename,
    }
    with open("conf/general/" + SCENARIO + "_SA_" + filename + ".yaml", "w") as f:
        yaml.dump(conf, f)


algorithm = "simulated_annealing"
seed = 22
max_temp = 10000
min_temp = 1
steps = [500, 1000, 2000, 4000, 8000]
updates = [50, 100, 200]

configurations = []

df = pd.DataFrame(columns=["Tmax", "Tmin", "steps", "updates", "filename"])


grid_runner_string = "ECHO Welcome to optimization of " + SCENARIO + "with SA\n"

for step_num in steps:
    for update_num in updates:
        hyper_param_name = "conf_{}_{}_{}_{}".format(
            max_temp, min_temp, step_num, update_num
        )
        create_hyperparameter_conf_and_save(
            hyper_param_name,
            max_temp,
            min_temp,
            step_num,
            update_num,
        )
        create_general_conf(hyper_param_name)
        df.loc[len(df)] = [
            max_temp,
            min_temp,
            step_num,
            update_num,
            hyper_param_name,
        ]

        grid_runner_string += "CALL python hydra_app.py general=" + SCENARIO + "_SA_" + hyper_param_name + " optimization=" + SCENARIO + "_SA_" + hyper_param_name + "\n"
        grid_runner_string += "ECHO Finished optimization of " + hyper_param_name + "\n"
df.to_excel("hyper_parameter_grid_" +  SCENARIO + "_SA.xlsx")
with open("grid_runner_" + SCENARIO + "_SA.bat", "w") as f:
    f.write(grid_runner_string)
