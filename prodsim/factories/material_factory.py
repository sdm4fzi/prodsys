from __future__ import annotations

from typing import List, TYPE_CHECKING

from pydantic import BaseModel, Field


from prodsim import (logger, process, router, sim)
from prodsim.data_structures import material_data
from prodsim.factories import process_factory

# if TYPE_CHECKING:
#     from .. import material




class MaterialFactory(BaseModel):
    env: sim.Environment
    process_factory: process_factory.ProcessFactory
    materials: List[material.Material] = []
    data_collecter: logger.Datacollector = Field(default=False, init=False)
    material_counter = 0

    def create_material(self, material_data: material_data.MaterialData, router: router.SimpleRouter):
        process_model = self.create_process_model(material_data)
        transport_processes = self.process_factory.get_process(
            material_data.transport_process
        )
        if not transport_processes or isinstance(transport_processes, process.ProductionProcess):
            raise ValueError("Transport process not found.")
        material_object = material.Material(
            env=self.env,
            material_data=material_data,
            router=router,
            process_model=process_model,
            transport_process=transport_processes
        )
        if self.data_collecter:
            self.data_collecter.register_patch(
                material_object.material_info,
                attr=["log_create_material", "log_finish_material"],
                post=logger.post_monitor_material_info,
            )

        self.material_counter += 1
        self.materials.append(material_object)
        return material_object

    def create_process_model(self, material_data: material_data.MaterialData) -> process.ProcessModel:
        if isinstance(material_data.processes, list):
            process_list = self.process_factory.get_processes_in_order(
                material_data.processes
            )
            return process.ListProcessModel(process_list=process_list)
        if isinstance(material_data.processes, str):
            import pm4py

            net, initial_marking, final_marking = pm4py.read_pnml(material_data.processes)
            for transition in net.transitions:
                if not transition.label:
                    transition_process = material.SKIP_LABEL
                else:
                    transition_process = self.process_factory.get_process(
                        transition.label
                    )
                transition.properties["Process"] = transition_process
            return process.PetriNetProcessModel(net=net, initial_marking=initial_marking, final_marking=final_marking)
        else:
            raise ValueError("Process model not recognized.")

    def get_material(self, ID) -> material.Material:
        return [m for m in self.materials if m.material_data.ID == ID].pop()

    def get_queues(self, IDs: List[str]) -> List[material.Material]:
        return [m for m in self.materials if m.material_data.ID in IDs]
    
from prodsim import material
material.Material.update_forward_refs()

