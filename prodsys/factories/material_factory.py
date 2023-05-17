from __future__ import annotations

from typing import List, Dict

from pydantic import BaseModel, Field


from prodsys.simulation import router, sim
from prodsys.data_structures import material_data
from prodsys.factories import process_factory
from prodsys.simulation import logger, proces_models, process


class MaterialFactory(BaseModel):
    env: sim.Environment
    process_factory: process_factory.ProcessFactory
    materials: List[material.Material] = []
    finished_materials: List[material.Material] = []
    event_logger: logger.EventLogger = Field(default=False, init=False)
    material_counter = 0

    class Config:
        arbitrary_types_allowed = True

    def create_material(
        self, material_data: material_data.MaterialData, router: router.Router
    ):
        material_data = material_data.copy()
        material_data.ID = (
            str(material_data.material_type) + "_" + str(self.material_counter)
        )
        process_model = self.create_process_model(material_data)
        transport_processes = self.process_factory.get_process(
            material_data.transport_process
        )
        if not transport_processes or isinstance(
            transport_processes, process.ProductionProcess
        ):
            raise ValueError("Transport process not found.")
        material_object = material.Material(
            env=self.env,
            material_data=material_data,
            material_router=router,
            process_model=process_model,
            transport_process=transport_processes,
        )
        if self.event_logger:
            self.event_logger.observe_terminal_material_states(material_object)

        self.material_counter += 1
        self.materials.append(material_object)
        return material_object
    
    
    def get_precendece_graph_from_id_adjacency_matrix(self, id_adjacency_matrix: Dict[str, List[str]]) -> proces_models.PrecedenceGraphProcessModel:
        precedence_graph = proces_models.PrecedenceGraphProcessModel()
        id_predecessor_adjacency_matrix = proces_models.get_predecessors_adjacency_matrix(id_adjacency_matrix)
        print(id_predecessor_adjacency_matrix)
        for key in id_adjacency_matrix.keys():
            sucessor_ids = id_adjacency_matrix[key]
            predecessor_ids = id_predecessor_adjacency_matrix[key]
            print(key, sucessor_ids, predecessor_ids)
            process = self.process_factory.get_process(key)
            successors = [self.process_factory.get_process(successor_id) for successor_id in sucessor_ids]
            predecessors = [self.process_factory.get_process(predecessor_id) for predecessor_id in predecessor_ids]
            precedence_graph.add_node(process, successors, predecessors)
        return precedence_graph

    def create_process_model(
        self, material_data: material_data.MaterialData
    ) -> proces_models.ProcessModel:
        if isinstance(material_data.processes, list) and isinstance(material_data.processes[0], str):
            process_list = self.process_factory.get_processes_in_order(
                material_data.processes
            )
            return proces_models.ListProcessModel(process_list=process_list)
        elif isinstance(material_data.processes, dict):
            print(material_data.processes)
            return self.get_precendece_graph_from_id_adjacency_matrix(material_data.processes)
        elif isinstance(material_data.processes, list) and isinstance(material_data.processes[0], list):
            id_adjacency_matrix = proces_models.get_adjacency_matrix_from_edges(
                material_data.processes
            )
            return self.get_precendece_graph_from_id_adjacency_matrix(id_adjacency_matrix)
        else:
            raise ValueError("Process model not recognized.")

    def get_material(self, ID: str) -> material.Material:
        return [m for m in self.materials if m.material_data.ID == ID].pop()
    
    def remove_material(self, material: material.Material):
        self.materials = [m for m in self.materials if m.material_data.ID != material.material_data.ID]

    def register_finished_material(self, material: material.Material):
        self.finished_materials.append(material)
        self.remove_material(material)


from prodsys.simulation import material

material.Material.update_forward_refs()
