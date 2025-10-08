from __future__ import annotations

from typing import List, Optional, Union, Any
from uuid import uuid1

from pydantic import Field, field_validator
from pydantic.dataclasses import dataclass

from prodsys.models import product_data

from prodsys.express import core, process
from prodsys.express.dependency import Dependency


@dataclass
class Product(core.ExpressObject):
    """
    Class that represents a product.

    Args:
        process (Union[process.ProcessModel, process.SequentialProcess, List[process.ProductionProcess]]): Process model of the product required for its production. This can be a process model (DAG), sequential process, or list of production processes (for backward compatibility).
        transport_process (process.TransportProcess): Transport process of the product.
        ID (str): ID of the product.

    Attributes:
        process (Union[process.ProcessModel, process.SequentialProcess]): Process model of the product required for its production.
        transport_process (process.TransportProcess): Transport process of the product.
        ID (Optional[str]): ID of the product.
        dependencies (Optional[List[Dependency]]): Dependencies of the product.


    Examples:
        Product with process model and transport process:
        ```py
        import prodsys.express as psx
        
        # Create individual processes
        welding_time_model = psx.FunctionTimeModel("normal", 20.0, 5.0)
        welding_process = psx.ProductionProcess(time_model=welding_time_model, ID="WELD")
        
        assembly_time_model = psx.FunctionTimeModel("normal", 15.0, 3.0)
        assembly_process = psx.ProductionProcess(time_model=assembly_time_model, ID="ASSEMBLY")
        
        # Create a process model (DAG)
        process_model = psx.ProcessModel(
            time_model=psx.FunctionTimeModel("constant", 0.0),
            process_ids=["WELD", "ASSEMBLY"],
            adjacency_matrix={"WELD": ["ASSEMBLY"], "ASSEMBLY": []},
            ID="PROCESS_MODEL_1"
        )
        
        # Create transport process
        transport_time_model = psx.ManhattenDistanceTimeModel(speed=10, reaction_time=0.3)
        transport_process = psx.TransportProcess(time_model=transport_time_model)
        
        # Create product with process model
        psx.Product(
            process=process_model,
            transport_process=transport_process
        )
        ```

    """

    process: Union[process.ProcessModel]
    transport_process: Union[
        process.TransportProcess, process.RequiredCapabilityProcess
    ]
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))
    dependencies: Optional[List[Dependency]] = Field(default_factory=list)


    @field_validator('process', mode='before')
    @classmethod
    def validate_process(cls, v):
        """Convert list of processes to SequentialProcess for backward compatibility."""
        if isinstance(v, list):
            if len(v) == 0:
                raise ValueError("Process list cannot be empty")
            # Extract process IDs
            process_ids = [p.ID for p in v]
            
            # Create SequentialProcess with a dummy time model
            from prodsys.express import time_model
            dummy_time_model = time_model.FunctionTimeModel("constant", 0.0, ID="dummy_time_model")
            sequential_process = process.SequentialProcess(
                time_model=dummy_time_model,
                process_ids=process_ids,
                ID="sequential_process"
            )
            
            return sequential_process
        return v

    def to_model(self) -> product_data.ProductData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            product_data.ProductData: An instance of the data object.
        """
        return product_data.ProductData(
            ID=self.ID,
            type=self.ID,
            description="",
            processes=self.process.adjacency_matrix,
            transport_process=self.transport_process.ID,
            dependency_ids=[dependency.ID for dependency in self.dependencies],
        )


def create_product(*args, **kwargs):
    """
    Factory function to create Product instances with backward compatibility.
    
    Supports both old and new API patterns:
    - Old: create_product([processes], transport_process, ID)
    - Old: create_product(processes=[...], transport_process=..., ID=...)
    - New: create_product(process=..., transport_process=..., ID=...)
    """
    # 1) Map positional args regardless of kwargs presence
    if args:
        if len(args) >= 2:
            processes_arg = args[0]
            transport_process_arg = args[1]
            id_arg = args[2] if len(args) > 2 else None

            # Only set if not already provided explicitly via kwargs
            if 'process' not in kwargs and 'processes' not in kwargs:
                # Accept list (handled by validator) or a single process model
                kwargs['process'] = processes_arg
            if 'transport_process' not in kwargs:
                kwargs['transport_process'] = transport_process_arg
            if id_arg is not None and 'ID' not in kwargs:
                kwargs['ID'] = id_arg
        elif len(args) == 1:
            # Allow pattern: Product(process, transport_process=..., ID=..., ...)
            if 'process' not in kwargs and 'processes' not in kwargs:
                kwargs['process'] = args[0]
        else:
            raise ValueError("Product requires at least process and transport_process arguments")

    # 2) Backward-compat keyword: processes -> process
    if 'processes' in kwargs and 'process' not in kwargs:
        kwargs['process'] = kwargs.pop('processes')

    return Product(**kwargs)

