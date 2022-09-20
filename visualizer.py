from abc import ABC, abstractmethod

import env
import logger


class Visualizer(ABC):

    @abstractmethod
    def display_simulation_results(self, logger: logger.Datacollector) -> None:
        pass

    @abstractmethod
    def display_simulation_progress(env, logger: logger.Datacollector)