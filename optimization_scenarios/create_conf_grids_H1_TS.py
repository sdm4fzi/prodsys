import yaml
import pandas as pd

SCENARIO = "H1"

def create_hyperparameter_conf_and_save(
    filename, tabu_size, max_steps, max_score
):
    conf = {
        "algorithm": algorithm,
        "seed": seed,
        "tabu_size": tabu_size,
        "max_steps": max_steps,
        "max_score": max_score,
    }
    with open("conf/optimization/" + SCENARIO + "_TS_" + filename + ".yaml", "w") as f:
        yaml.dump(conf, f)


def create_general_conf(filename):
    conf = {
        "mode": "optimization",
        "configuration_path": "base_configuration_" + SCENARIO + ".json",
        "scenario_path": "scenario_" + SCENARIO + ".json",
        "save_folder": "results/" + SCENARIO + "_TS_" + filename,
    }
    with open("conf/general/" + SCENARIO + "_TS_" + filename + ".yaml", "w") as f:
        yaml.dump(conf, f)


algorithm = "tabu_search"
seed = 22
tabu_size = [5, 10, 20]
max_steps = [500, 1000, 2000, 4000]
max_score = 500

configurations = []

df = pd.DataFrame(columns=["tabu_size", "max_steps", "max_score", "filename"])


grid_runner_string = "ECHO Welcome to optimization of " + SCENARIO + "with TS\n"

for ts in tabu_size:
    for max_step in max_steps:
        hyper_param_name = "conf_{}_{}".format(
            ts, max_step
        )
        create_hyperparameter_conf_and_save(
            hyper_param_name,
            ts,
            max_step,
            max_score,
        )
        create_general_conf(hyper_param_name)
        df.loc[len(df)] = [
            ts,
            max_step,
            max_score,
            hyper_param_name,
        ]

        grid_runner_string += "CALL python hydra_app.py general=" + SCENARIO + "_TS_" + hyper_param_name + " optimization=" + SCENARIO + "_TS_" + hyper_param_name + "\n"
        grid_runner_string += "ECHO Finished optimization of " + hyper_param_name + "\n"
df.to_excel("hyper_parameter_grid_" +  SCENARIO + "_TS.xlsx")
with open("grid_runner_" + SCENARIO + "_TS.bat", "w") as f:
    f.write(grid_runner_string)
