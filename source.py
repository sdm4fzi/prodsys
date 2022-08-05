from typing import List
from dataclasses import dataclass, field

import base
import env
import material
import time_model
import router



@dataclass
class Source(base.IDEntity):
    env: env.Environment
    material_factory: material.MaterialFactory
    location: List[int]
    material_type: str
    time_model: time_model.TimeModel
    router: router.SimpleRouter

    def start_source(self):
        self.env.process(self.create_material())

    def create_material(self):
        while True:
            yield self.env.timeout(self.time_model.get_next_time())
            __material = self.material_factory.create_material(type=self.material_type, router=self.router)
            __material.process = self.env.process(__material.process_material())

    def get_location(self) -> List[int]:
        return self.location


@dataclass
class SourceFactory:
    data: dict
    env: env.Environment
    material_factory: material.MaterialFactory
    time_model_factory: time_model.TimeModelFactory
    routers: dict

    sources: List[Source] = field(default_factory=list, init=False)

    def create_sources(self):
        sources = self.data['sources']
        for values in sources.values():
            self.add_source(values)

    def get_router(self, router: str):
        return self.routers[router]

    def add_source(self, values: dict):
        router = self.get_router(values['router'])
        time_model = self.time_model_factory.get_time_model(values['time_model_id'])
        source = Source(ID=values['ID'], description=values['description'], location=values["location"],
                        env=self.env, material_factory=self.material_factory,
                        material_type=values['material_type'],
                        time_model=time_model,
                        router=router
                        )
        self.sources.append(source)

    def start_sources(self):
        for _source in self.sources:
            _source.start_source()

    def get_source(self, ID) -> Source:
        return [s for s in self.sources if s.ID == ID].pop()

    def get_sources(self, IDs: List[str]) -> List[Source]:
        return [s for s in self.sources if s.ID in IDs]

    def get_sources_with_material_type(self, __material_type: str):
        return [s for s in self.sources if __material_type == s.material_type]