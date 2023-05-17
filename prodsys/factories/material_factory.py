from __future__ import annotations

from typing import List, Dict

from pydantic import BaseModel, Field


from prodsys.simulation import router, sim
from prodsys.data_structures import material_data
from prodsys.factories import process_factory
from prodsys.simulation import logger, proces_models, process


class MaterialFactory(BaseModel):
    """
    Factory class that creates material objects.

    Args:
        env (sim.Environment): prodsys simulation environment.
        process_factory (process_factory.ProcessFactory): Factory that creates process objects.
    """

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
    ) -> material.Material:
        """
        Creates a material object based on the given material data and router.

        Args:
            material_data (material_data.MaterialData): Material data that is used to create the material object.
            router (router.Router): Router that is used to route the material object.

        Raises:
            ValueError: If the transport process is not found.

        Returns:
            material.Material: Created material object.
        """
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

    def get_precendece_graph_from_id_adjacency_matrix(
        self, id_adjacency_matrix: Dict[str, List[str]]
    ) -> proces_models.PrecedenceGraphProcessModel:
        precedence_graph = proces_models.PrecedenceGraphProcessModel()
        id_predecessor_adjacency_matrix = (
            proces_models.get_predecessors_adjacency_matrix(id_adjacency_matrix)
        )
        for key in id_adjacency_matrix.keys():
            sucessor_ids = id_adjacency_matrix[key]
            predecessor_ids = id_predecessor_adjacency_matrix[key]
            process = self.process_factory.get_process(key)
            successors = [
                self.process_factory.get_process(successor_id)
                for successor_id in sucessor_ids
            ]
            predecessors = [
                self.process_factory.get_process(predecessor_id)
                for predecessor_id in predecessor_ids
            ]
            precedence_graph.add_node(process, successors, predecessors)
        return precedence_graph

    def create_process_model(
        self, material_data: material_data.MaterialData
    ) -> proces_models.ProcessModel:
        """
        Creates a process model based on the given material data.

        Args:
            material_data (material_data.MaterialData): Material data that is used to create the process model.

        Raises:
            ValueError: If the process model is not recognized.

        Returns:
            proces_models.ProcessModel: Created process model.
        """
        if isinstance(material_data.processes, list) and isinstance(
            material_data.processes[0], str
        ):
            process_list = self.process_factory.get_processes_in_order(
                material_data.processes
            )
            return proces_models.ListProcessModel(process_list=process_list)
        elif isinstance(material_data.processes, dict):
            return self.get_precendece_graph_from_id_adjacency_matrix(
                material_data.processes
            )
        elif isinstance(material_data.processes, list) and isinstance(
            material_data.processes[0], list
        ):
            id_adjacency_matrix = proces_models.get_adjacency_matrix_from_edges(
                material_data.processes
            )
            return self.get_precendece_graph_from_id_adjacency_matrix(
                id_adjacency_matrix
            )
        else:
            raise ValueError("Process model not recognized.")

    def get_material(self, ID: str) -> material.Material:
        """
        Returns the material object with the given ID.

        Args:
            ID (str): ID of the material object.

        Returns:
            material.Material: Material object with the given ID.
        """
        return [m for m in self.materials if m.material_data.ID == ID].pop()

    def remove_material(self, material: material.Material):
        """
        Removes the given material object from the material factory list of current material objects.

        Args:
            material (material.Material): Material object that is removed.
        """
        self.materials = [
            m for m in self.materials if m.material_data.ID != material.material_data.ID
        ]

    def register_finished_material(self, material: material.Material):
        """
        Registers the given material object as a finished material object.

        Args:
            material (material.Material): Material object that is registered as a finished material object.
        """
        self.finished_materials.append(material)
        self.remove_material(material)


from prodsys.simulation import material

material.Material.update_forward_refs()
