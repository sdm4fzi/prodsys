from __future__ import annotations

import simpy
from dataclasses import dataclass, field
from typing import List
from abc import ABC, abstractmethod
import logging
import json


@dataclass
class Loader(ABC):
    seed: int = field(init=False)
    time_model_data: dict = field(init=False)
    state_data: dict = field(init=False)
    process_data: dict = field(init=False)
    resource_data: dict = field(init=False)
    queue_data: dict = field(init=False)
    source_data: dict = field(init=False)
    sink_data: dict = field(init=False)
    material_data: dict = field(init=False)

    @abstractmethod
    def read_data(file_path: str):
        pass

@dataclass
class JsonLoader(Loader):
    def read_data(self, file_path: str):
        with open(file_path, 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
        logging.info("data loaded")
        self.seed = data['seed']
        self.time_model_data = data['time_models']
        self.state_data = data['states']
        self.process_data = data['processes']
        self.queue_data = data['queues']
        self.resource_data = data['resources']
        self.material_data = data['materials']
        self.sink_data = data['sinks']
        self.source_data = data['sources']

