from __future__ import annotations

from typing import TYPE_CHECKING, List, Dict

from prodsys.models.product_data import ProductData
from prodsys.models.source_data import RoutingHeuristic
from prodsys.simulation import process_models
from prodsys.simulation import process
from prodsys.simulation import router as router_module

if TYPE_CHECKING:
    from prodsys.factories import process_factory
    from prodsys.simulation import sim, product


class ProductFactory:
    """
    Factory class that creates and stores `prodsys.simulation` product objects from `prodsys.models` product objects.

    Args:
        env (sim.Environment): prodsys simulation environment.
        process_factory (process_factory.ProcessFactory): Factory that creates process objects.
    """

    def __init__(
        self, env: sim.Environment, process_factory: process_factory.ProcessFactory
    ):
        self.env = env
        self.process_factory = process_factory
        self.products: Dict[str, product.Product] = {}
        self.finished_products = []
        self.event_logger = False
        self.product_counter = 0
        self.router: router_module.Router = None

    def create_product(
        self, product_data: ProductData, routing_heuristic: RoutingHeuristic
    ) -> product.Product:
        """
        Creates a product object based on the given product data and router.

        Args:
            product_data (ProductData): Product data that is used to create the product object.
            router (router.Router): Router that is used to route the product object.

        Raises:
            ValueError: If the transport process is not found.

        Returns:
            product.Product: Created product object.
        """
        product_data = product_data.model_copy()
        product_data.ID = (
            str(product_data.product_type) + "_" + str(self.product_counter)
        )
        process_model = self.create_process_model(product_data)
        transport_processes = self.process_factory.get_process(
            product_data.transport_process
        )
        if not transport_processes or isinstance(
            transport_processes, process.ProductionProcess
        ):
            raise ValueError("Transport process not found.")
        routing_heuristic_callable = router_module.ROUTING_HEURISTIC.get(
            routing_heuristic, None
        )
        if routing_heuristic_callable is None:
            raise ValueError(f"Routing heuristic {routing_heuristic} not found.")

        product_object = product.Product(
            env=self.env,
            product_data=product_data,
            product_router=self.router,
            routing_heuristic=routing_heuristic_callable,
            process_model=process_model,
            transport_process=transport_processes,
            has_auxiliaries=(
                True if product_data.auxiliaries and product_data is not None else False
            ),
        )
        if self.event_logger:
            self.event_logger.observe_terminal_product_states(product_object)

        self.product_counter += 1
        self.products[product_data.ID] = product_object
        return product_object

    def get_precendece_graph_from_id_adjacency_matrix(
        self, id_adjacency_matrix: Dict[str, List[str]]
    ) -> process_models.PrecedenceGraphProcessModel:
        precedence_graph = process_models.PrecedenceGraphProcessModel()
        id_predecessor_adjacency_matrix = (
            process_models.get_predecessors_adjacency_matrix(id_adjacency_matrix)
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
        self, product_data: ProductData
    ) -> process_models.ProcessModel:
        """
        Creates a process model based on the given product data.

        Args:
            product_data (ProductData): Product data that is used to create the process model.

        Raises:
            ValueError: If the process model is not recognized.

        Returns:
            proces_models.ProcessModel: Created process model.
        """
        if isinstance(product_data.processes, list) and isinstance(
            product_data.processes[0], str
        ):
            process_list = self.process_factory.get_processes_in_order(
                product_data.processes
            )
            return process_models.ListProcessModel(process_list=process_list)
        elif isinstance(product_data.processes, dict):
            return self.get_precendece_graph_from_id_adjacency_matrix(
                product_data.processes
            )
        elif isinstance(product_data.processes, list) and isinstance(
            product_data.processes[0], list
        ):
            id_adjacency_matrix = process_models.get_adjacency_matrix_from_edges(
                product_data.processes
            )
            return self.get_precendece_graph_from_id_adjacency_matrix(
                id_adjacency_matrix
            )
        else:
            raise ValueError("Process model not recognized.")

    def get_product(self, ID: str) -> product.Product:
        """
        Returns the product object with the given ID.

        Args:
            ID (str): ID of the product object.

        Returns:
            product.Product: Product object with the given ID.
        """
        if ID in self.products:
            return self.products[ID]
        raise ValueError(f"Product with ID {ID} not found.")

    def remove_product(self, product: product.Product):
        """
        Removes the given product object from the product factory list of current product objects.

        Args:
            product (product.Product): Product object that is removed.
        """
        if product.product_data.ID in self.products:
            del self.products[product.product_data.ID]
        else:
            raise ValueError(f"Product with ID {product.product_data.ID} not found.")

    def register_finished_product(self, product: product.Product):
        """
        Registers the given product object as a finished product object.

        Args:
            product (product.Product): Product object that is registered as a finished product object.
        """
        self.finished_products.append(product)
        self.remove_product(product)


from prodsys.simulation import product
