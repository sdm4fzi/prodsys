import hydra
from omegaconf import DictConfig, OmegaConf

import prodsys
from prodsys.optimization.evolutionary_algorithm import run_evolutionary_algorithm
from prodsys.optimization.math_opt import MathOptimizer
from prodsys.optimization.simulated_annealing import run_simulated_annealing
from prodsys.optimization.tabu_search import run_tabu_search
from prodsys.simulation.runner import run_simulation
from prodsys.util.util import get_initial_solution_file_pth, prepare_save_folder


@hydra.main(version_base=None, config_path="conf", config_name="config")
def my_app(cfg: DictConfig) -> None:
    if cfg.general.mode == "simulation":
        adapter_object = prodsys.adapters.JsonProductionSystemAdapter()
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
            if (
                not "initial_solutions_folder" in cfg.general.keys()
                or not cfg.general.initial_solutions_folder
            ):
                cfg.general.save_folder += "/evolutionary"
                initial_solutions_folder = ""
            else:
                initial_solutions_folder = cfg.general.initial_solutions_folder
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
                initial_solutions_folder
            )
        elif cfg.optimization.algorithm == "simulated_annealing":
            if (
                not "initial_solutions_folder" in cfg.general.keys()
                or cfg.general.initial_solutions_folder == ""
            ):
                cfg.general.save_folder += "/simulated_annealing"
                initial_solution_file_path = ""
            else:
                cfg.general.save_folder += "/partial_simulated_annealing"
                initial_solution_file_path = get_initial_solution_file_pth(
                    cfg.general.initial_solutions_folder
                )
            prepare_save_folder(cfg.general.save_folder)
            run_simulated_annealing(
                cfg.general.save_folder,
                cfg.general.configuration_path,
                cfg.general.scenario_path,
                cfg.optimization.seed,
                cfg.optimization.Tmax,
                cfg.optimization.Tmin,
                cfg.optimization.steps,
                cfg.optimization.updates,
                initial_solution_file_path
            )

        elif cfg.optimization.algorithm == "tabu_search":
            if (
                not "initial_solutions_folder" in cfg.general.keys()
                or not cfg.general.initial_solutions_folder
            ):
                cfg.general.save_folder += "/tabu_search"
                initial_solution_file_path = ""
            else:
                cfg.general.save_folder += "/partial_tabu_search"
                initial_solution_file_path = get_initial_solution_file_pth(
                    cfg.general.initial_solutions_folder
                )
            prepare_save_folder(cfg.general.save_folder)
            run_tabu_search(
                cfg.general.save_folder,
                cfg.general.configuration_path,
                cfg.general.scenario_path,
                cfg.optimization.seed,
                cfg.optimization.tabu_size,
                cfg.optimization.max_steps,
                cfg.optimization.max_score,
                initial_solution_file_path
            )
        elif cfg.optimization.algorithm == "mathematical":
            cfg.general.save_folder += "/mathematical"
            prepare_save_folder(cfg.general.save_folder)
            adapter_object = prodsys.adapters.JsonProductionSystemAdapter()
            adapter_object.read_data(
                cfg.general.configuration_path, cfg.general.scenario_path
            )
            optimizer_object = MathOptimizer(
                adapter=adapter_object,
                optimization_time_portion=cfg.optimization.optimization_time_portion,
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
