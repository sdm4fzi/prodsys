
from typing import TYPE_CHECKING, List
from pydantic import BaseModel, parse_obj_as
from prodsys.adapters import adapter
from prodsys.factories import process_factory, queue_factory

from prodsys.simulation import sim
from prodsys.simulation import auxiliary


class AuxiliaryFactory(BaseModel):

        env: sim.Environment
        auxiliaries: List[auxiliary.Auxiliary] = []

        class Config:
                arbitrary_types_allowed = True

        def create_auxiliary(self, adapter: adapter.ProductionSystemAdapter):
                for auxiliary_data in adapter.auxiliary_data:
                        self.add_auxiliary(auxiliary_data)


        def add_auxiliary(self, auxiliary_data: auxiliary.Auxiliary):
                values = {}
                values.update({"env": self.env, "auxiliary_data": auxiliary_data})
                auxiliary_object = parse_obj_as(auxiliary.Auxiliary, values)
                self.auxiliaries.append(auxiliary_object)
