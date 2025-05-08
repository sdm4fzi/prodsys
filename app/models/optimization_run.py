from typing import List, Union
from pydantic import BaseModel

import prodsys
from prodsys.optimization import (
    evolutionary_algorithm,
    simulated_annealing,
    tabu_search,
    math_opt,
)


class OptimizationRun(BaseModel):
    """
    An optimization run holds all meta information for a optimization.

    Args:
        prodsys.adaptersel (_typadapterscription_
    """

    project_id: str
    base_adapter_id: str
    hyper_parameters: Union[
        evolutionary_algorithm.EvolutionaryAlgorithmHyperparameters,
        simulated_annealing.SimulatedAnnealingHyperparameters,
        tabu_search.TabuSearchHyperparameters,
        math_opt.MathOptHyperparameters,
    ]
    found_adapters: List[adapter.ProductionSystemData] = []
    optimization_results: str
    # TODO: create a Pydantic Type for Optmization results to be more transparent...
    # TODO: add this optimization run to the prodsys project and make it available through the backend
    # TODO: change how optimizations are performed in prodsys by creating an OptimizationRunner. This class should work similar to the Simulation Runner
    # and make it easy to access the progress of simulations, the results and so on
    # Also the optimization runner should have options, whether to save the data in the file systems (during optimization) or as attributes in the runner.
    # prodsys API extends this runner to save the data in the backend.
