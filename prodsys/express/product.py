from typing import List, Optional, Union
from uuid import uuid1

from pydantic import Field
from pydantic.dataclasses import dataclass

from prodsys.models import product_data

from prodsys.express import process, core

@dataclass
class Product(core.ExpressObject):
    """
    Class that represents a product.

    Args:
        processes (List[Union[process.ProductionProcess, process.CapabilityProcess]]): Processes of the product required for its production. These processes are executed sequentially. To have more degree of freedom with precedence graph process models, use the prodsys.datastructures API of product.
        transport_process (process.TransportProcess): Transport process of the product.
        ID (str): ID of the product.

    Examples:
        Product with 2 sequential processes and a transport process:
        ```py
        import prodsys.express as psx
        welding_time_model = psx.time_model_data.FunctionTimeModel(
            distribution_function="normal",
            location=20.0,
            scale=5.0,
         )
        welding_process_1 = psx.process.ProductionProcess(
            time_model=welding_time_model,
        )
        welding_process_2 = psx.process.ProductionProcess(
            time_model=welding_time_model,
        )
        transport_time_model = psx.time_model_data.ManhattenDistanceTimeModel(
            speed=10,
            reaction_time= 0.3
        )
        transport_process = psx.process.TransportProcess(
            time_model=transport_time_model,
        )
        psx.Product(
            processes=[welding_process_1, welding_process_2],
            transport_process=transport_process
        )
        ```
    """
    processes: List[Union[process.ProductionProcess, process.CapabilityProcess]]
    transport_process: process.TransportProcess
    ID: Optional[str] = Field(default_factory=lambda: str(uuid1()))

    def to_model(self) -> product_data.ProductData:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            product_data.ProductData: An instance of the data object.
        """
        return product_data.ProductData(
            ID=self.ID,
            description="",
            processes=[process.ID for process in self.processes],
            transport_process=self.transport_process.ID,
        )
    
#TODO: Add an PalletProduct Class with an additional attribute called pallets.
