import hydra
from omegaconf import DictConfig, OmegaConf

import prodsim
from prodsim.util.evolutionary_algorithm import run_evolutionary_algorithm
from prodsim.util.math_opt import MathOptimizer
from prodsim.util.runner import run_simulation
import os


def prepare_save_folder(file_paths: str):
    isExist = os.path.exists(file_paths)
    if not isExist:
        os.makedirs(file_paths)

# TODO: add Anneal and tabu search to hydra functionality

@hydra.main(version_base=None, config_path="conf", config_name="config")
def my_app(cfg: DictConfig) -> None:
    if cfg.general.mode == "simulation":
        adapter_object = prodsim.adapters.JsonAdapter()
        adapter_object.read_data(cfg.general.configuration_path)
        runner_object = run_simulation(adapter_object, cfg.simulation.simulation_length)
        if cfg.simulation.print_results:
            runner_object.print_results()
        if cfg.simulation.plot_results:
            runner_object.plot_results()
        if cfg.simulation.save_results:
            prepare_save_folder(cfg.general.save_folder)
            runner_object.save_results_as_csv(cfg.general.save_folder)
    elif cfg.general.mode == "optimization":
        if cfg.optimization.algorithm == "evolutionary":
            cfg.general.save_folder += "/evolutionary"
            prepare_save_folder(cfg.general.save_folder)
            run_evolutionary_algorithm(
                cfg.general.save_folder,
                cfg.general.configuration_path,
                cfg.general.scenario_path,
                cfg.optimization.seed,
                cfg.optimization.number_of_generations,
                cfg.optimization.population_size,
                cfg.optimization.mutation_rate,
                cfg.optimization.crossover_rate,
                cfg.optimization.number_of_processes,
            )
        elif cfg.optimization.algorithm == "partial_evolutionary":
            cfg.general.save_folder += "/partial_evolutionary"
            prepare_save_folder(cfg.general.save_folder)
            run_evolutionary_algorithm(
                cfg.general.save_folder,
                cfg.general.configuration_path,
                cfg.general.scenario_path,
                cfg.optimization.seed,
                cfg.optimization.number_of_generations,
                cfg.optimization.population_size,
                cfg.optimization.mutation_rate,
                cfg.optimization.crossover_rate,
                cfg.optimization.number_of_processes,
                cfg.general.initial_solutions_folder
            )
        elif cfg.optimization.algorithm == "mathematical":
            cfg.general.save_folder += "/mathematical"
            prepare_save_folder(cfg.general.save_folder)
            adapter_object = prodsim.adapters.JsonAdapter()
            adapter_object.read_data(
                cfg.general.configuration_path, cfg.general.scenario_path
            )
            optimizer_object = MathOptimizer(
                adapter=adapter_object, optimization_time_portion=cfg.optimization.optimization_time_portion
            )
            optimizer_object.optimize(n_solutions=cfg.optimization.n_solutions)
            if cfg.optimization.save_model:
                optimizer_object.save_model(cfg.general.save_folder)
            optimizer_object.save_results(
                save_folder=cfg.general.save_folder,
                adjusted_number_of_transport_resources=cfg.optimization.adjusted_number_of_transport_resources,
            )


if __name__ == "__main__":
    my_app()
