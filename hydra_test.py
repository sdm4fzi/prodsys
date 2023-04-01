import hydra
from omegaconf import DictConfig, OmegaConf

import prodsim
from prodsim.simulation import resources

@hydra.main(version_base=None, config_path="conf", config_name="config")
def my_app(cfg: DictConfig) -> None:
    adapter_object = prodsim.adapters.JsonAdapter()
    adapter_object.read_data(cfg["simulation"]["configuration_file"])

    runner_object = prodsim.runner.Runner(adapter=adapter_object)
    runner_object.initialize_simulation()
    runner_object.run(cfg["simulation"]["run_length"])
    runner_object.print_results()
    # runner_object.plot_results()
    if cfg["simulation"]["save_results"]:
        runner_object.save_results_as_csv(cfg["simulation"]["save_folder"])
        # runner_object.save_results_as_json()

if __name__ == "__main__":
    my_app()