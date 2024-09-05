from __future__ import annotations
from hashlib import md5
from typing import Optional, Union, List, Dict, TYPE_CHECKING
from pydantic import ConfigDict, model_validator
from prodsys.models.core_asset import CoreAsset

if TYPE_CHECKING:
    from prodsys.adapters.adapter import ProductionSystemAdapter

class ProductData(CoreAsset):
    """
    Class that represents product data, specifically the required processes and the allows tranport process.

    The processes describe thereby the process model that needs to be completed for the product to be finished. There are three different ways to describe the process model:

    - Sequential process model: The processes are given as a list of process IDs. The processes are executed sequentially.
    - Adjacency matrix process model: The processes are given as an adjacency matrix that describes the precedence graph of the product.
    - Edges process model: The processes are given as a list of edges. The edges describe the precedence graph of the product.

    See the examples for more insights.

    Args:
        ID (str): ID of the product. If not given, the product type is used. Gets overwritten to the instance product ID, when an instance is created during simulation.
        description (str): Description of the product.
        product_type (str): Type of the product. If not given, the ID is used.
        processes (Union[List[str], List[List[str]], Dict[str, List[str]]]): Processes of the product. This can be a list of process IDs, a list of edges or an adjacency matrix.
        transport_process (str): Transport process of the product.
        aauxiliaries (List[str], optional): List of auxiliary components required to process or transport the product. Defaults to [].

    Examples:
        Product with sequential process model:
        ``` py
        import prodsys
        prodsys.product_data.ProductData(
            ID="Product_1",
            description="product 1",
            product_type="Product_1",
            processes=["P1", "P2", "P3"],
            transport_process="TP1",
        )
        ```

        Product with adjacency matrix process model:
        ``` py
        import prodsys
        prodsys.product_data.ProductData(
            ID="Product_1",
            description="Product 1",
            product_type="Product_1",
            processes={
                "P1": ["P2", "P3"],
                "P2": ["P3"],
                "P3": [],
            },
            transport_process="TP1",
        )
        ```

        Product with graph edges process model:
        ``` py
        import prodsys
        prodsys.product_data.ProductData(
            ID="Product_1",
            description="Product 1",
            product_type="Product_1",
            processes=[
                ["P1", "P2"],
                ["P1", "P3"],
                ["P2", "P4"],
                ["P3", "P4"],
            ],
            transport_process="TP1",
        )
        ```
    """

    product_type: str
    processes: Union[List[str], List[List[str]], Dict[str, List[str]]]
    transport_process: str
    auxiliaries: Optional[List[str]]

    def hash(self, adapter: ProductionSystemAdapter) -> str:
        """
        Returns a unique hash of the product considering the processes and the transport process. Can be used to compare products for equal functionality.

        Args:
            adapter (ProductionSystemAdapter): Adapter that contains the process data.

        Raises:
            ValueError: If the process or transport process is not found in the adapter.

        Returns:
            str: Hash of the product.
        """
        processes_hashes = []
        transport_process_hash = ""

        if not isinstance(self.processes, list) or isinstance(self.processes[0], list):
            # TODO: Implement hash for adjacency matrix and edges process models
            raise NotImplementedError("Only list of processes is supported for hashing. Complex process models are not supported yet.")
        
        for process_id in self.processes:
            for process in adapter.process_data:
                if process.ID == process_id:
                    processes_hashes.append(process.hash(adapter))
                    break
            else:
                raise ValueError(f"Process with ID {self.processes} not found for product {self.ID}.")
            
        # TODO: add hashing for auxiliaries!
        
        for transport_process in adapter.process_data:
            if transport_process.ID == self.transport_process:
                transport_process_hash = transport_process.hash(adapter)
                break
        else:
            raise ValueError(f"Transport process with ID {self.transport_process} not found for product {self.ID}.")
        
        return md5("".join([*processes_hashes, transport_process_hash]).encode("utf-8")).hexdigest()
                   
    @model_validator(mode="before")
    def check_processes(cls, values):
        if "product_type" in values and values["product_type"]:
            values["ID"] = values["product_type"]
        else:
            values["product_type"] = values["ID"]
        return values
    
    model_config=ConfigDict(json_schema_extra={
        "examples": [
            {
                "ID": "Product_1",
                "description": "Product with sequential process",
                "product_type": "Product_1",
                "processes": ["P1", "P2", "P3"],
                "transport_process": "TP1",
                "auxiliaries": ["Pallette"]
            },
            {
                "ID": "Product_1",
                "description": "Process with adjacency matrix process",
                "product_type": "Product_1",
                "processes": {
                    "P1": ["P2", "P3"],
                    "P2": ["P3"],
                    "P3": [],
                },
                "transport_process": "TP1",
            },
            {
                "ID": "Product_1",
                "description": "Process with graph edges process",
                "product_type": "Product_1",
                "processes": [
                    ["P1", "P2"],
                    ["P1", "P3"],
                    ["P2", "P4"],
                    ["P3", "P4"],
                ],
                "transport_process": "TP1",
            },
        ]
    })