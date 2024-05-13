"""
The `state_data` module contains the `prodsys.models` classes to represent the states that resources 
can be in during a simulation.

The following states are possible:

- `BreakDownStateData`: A state that makes a resource unavailable for a certain time.
- `ProcessBreakDownStateData`: A state that makes a process unavailable for a certain time but other processes can still be performed.
- `SetupStateData`: A state that represents the time needed to change the process of a resource.
- `ProductionStateData`: A state that represents the time needed to process a product.
- `TransportStateData`: A state that represents the time needed to transport a product.	    
"""

from __future__ import annotations
from hashlib import md5
from enum import Enum
from typing import Literal, Union, TYPE_CHECKING, Optional

from prodsys.models.core_asset import CoreAsset

if TYPE_CHECKING:
    from prodsys.adapters.adapter import ProductionSystemAdapter



class StateTypeEnum(str, Enum):
    """
    Enum that represents the different kind of states.

    - BreakDownState: A state that makes a resource unavailable for a certain time.
    - ProductionState: A state that represents the time needed to process a product.
    - TransportState: A state that represents the time needed to transport a product.
    - SetupState: A state that represents the time needed to change the process of a resource.
    - ProcessBreakDownState: A state that makes a process unavailable for a certain time but other processes can still be performed.
    """

    BreakDownState = "BreakDownState"
    ProductionState = "ProductionState"
    TransportState = "TransportState"
    SetupState = "SetupState"
    ProcessBreakDownState = "ProcessBreakDownState"


class StateData(CoreAsset):
    """
    Class that represents a state.

    Args:
        ID (str): ID of the state.
        description (str): Description of the state.
        time_model_id (str): Time model ID of the state.
        type (StateTypeEnum): Type of the state.
    """

    time_model_id: str
    type: Literal[
        StateTypeEnum.BreakDownState,
        StateTypeEnum.ProductionState,
        StateTypeEnum.TransportState,
        StateTypeEnum.SetupState,
    ]

    def hash(self, adapter: ProductionSystemAdapter) -> str:
        """
        Returns a unique hash of the state considering the time model and the type of the state. Can be used to compare states for equal functionality.

        Args:
            adapter (ProductionSystemAdapter): Adapter to access the data of the state.

        Raises:
            ValueError: if the time model is not found in the adapter.

        Returns:
            str: hash of the state.
        """
        time_model_hash = ""
        for time_model in adapter.time_model_data:
            if time_model.ID == self.time_model_id:
                time_model_hash = time_model.hash()
                break
        else:
            raise ValueError(f"Time model with ID {self.time_model_id} not found for state {self.ID}.")
        return md5(("".join([self.type, time_model_hash])).encode("utf-8")).hexdigest()

    class Config:
        schema_extra = {
            "example": {
                "summary": "State",
                "value": {
                    "ID": "state_1",
                    "description": "State data for state_1",
                    "time_model_id": "time_model_1",
                    "type": "ProductionState",
                },
            }
        }


class BreakDownStateData(StateData):
    """
    Class that represents a breakdown state.

    Args:
        ID (str): ID of the state.
        description (str): Description of the state.
        time_model_id (str): Time model ID of the state. Specifies the time interval between breakdowns.
        type (StateTypeEnum): Type of the state.
        repair_time_model_id (str): Time model ID of the repair time.

    Examples:
        Breakdown state with a function time model:
        ``` py  
        import prodsys
        prodsys.state_data.BreakDownStateData(
            ID="Breakdownstate_1",
            description="Breakdown state machine 1",
            time_model_id="function_time_model_5",
            repair_time_model_id="function_time_model_8",
        )
        ```
    """

    type: Literal[StateTypeEnum.BreakDownState]
    repair_time_model_id: str

    def hash(self, adapter: ProductionSystemAdapter) -> str:
        """
        Returns a unique hash of the state considering the time model and the repair time model. Can be used to compare states for equal functionality.

        Args:
            adapter (ProductionSystemAdapter): Adapter to access the data of the state.

        Raises:
            ValueError: if the repair time model is not found.

        Returns:
            str: hash of the state.
        """
        base_class_hash = super().hash(adapter)
        repair_time_model_hash = ""

        for repair_time_model in adapter.time_model_data:
            if repair_time_model.ID == self.repair_time_model_id:
                repair_time_model_hash = repair_time_model.hash()
                break
        else:
            raise ValueError(f"Repair time model with ID {self.repair_time_model_id} not found for state {self.ID}.")

        return md5(("".join([base_class_hash, repair_time_model_hash])).encode("utf-8")).hexdigest()  
    
    class Config:
        schema_extra = {
            "example": {
                "summary": "Breakdown state",
                "value": {
                    "ID": "Breakdownstate_1",
                    "description": "Breakdown state machine 1",
                    "time_model_id": "function_time_model_5",
                    "type": "BreakDownState",
                    "repair_time_model_id": "function_time_model_8",
                },
            }
        }


class ProcessBreakDownStateData(StateData):
    """
    Class that represents a process breakdown state. It is a breakdown state that is connected to a process. Other processes can still be executed while the process breakdown state is activen.

    Args:
        ID (str): ID of the state.
        description (str): Description of the state.
        time_model_id (str): Time model ID of the state.
        type (StateTypeEnum): Type of the state.
        repair_time_model_id (str): Time model ID of the repair time.
        process_id (str): ID of the process that is broken down.

    Examples:
        Process breakdown state with a function time model:
        ``` py
        import prodsys
        prodsys.state_data.ProcessBreakDownStateData(
            ID="ProcessBreakDownState_1",
            description="Process Breakdown state machine 1",
            time_model_id="function_time_model_7",
            repair_time_model_id="function_time_model_8",
            process_id="P1",
        )
        ```
    """

    type: Literal[StateTypeEnum.ProcessBreakDownState]
    repair_time_model_id: str
    process_id: str

    def hash(self, adapter: ProductionSystemAdapter) -> str:
        """
        Returns a unique hash of the state considering the time model, process and repair time model. Can be used to compare states for equal functionality.

        Args:
            adapter (ProductionSystemAdapter): Adapter to access the data of the state.

        Raises:
            ValueError: if the process or repair time model is not found.

        Returns:
            str: hash of the state.
        """
        base_class_hash = super().hash(adapter)
        process_hash = ""
        repair_time_model_hash = ""

        for process in adapter.process_data:
            if process.ID == self.process_id:
                process_hash = process.hash(adapter)
                break
        else:
            raise ValueError(f"Process with ID {self.process_id} not found for process breakdown state {self.ID}.")

        for repair_time_model in adapter.time_model_data:
            if repair_time_model.ID == self.repair_time_model_id:
                repair_time_model_hash = repair_time_model.hash()
                break
        else:
            raise ValueError(f"Repair time model with ID {self.repair_time_model_id} not found for process breakdown state {self.ID}.")
        

        return md5(("".join([base_class_hash, process_hash, repair_time_model_hash])).encode("utf-8")).hexdigest()

    class Config:
        schema_extra = {
            "example": {
                "summary": "Process breakdown state",
                "value": {
                    "ID": "ProcessBreakDownState_1",
                    "description": "Process Breakdown state machine 1",
                    "time_model_id": "function_time_model_7",
                    "type": "ProcessBreakDownState",
                    "process_id": "P1",
                    "repair_time_model_id": "function_time_model_8",
                },
            }
        }


class ProductionStateData(StateData):
    """
    Class that represents a production state. By undergoing a production state, the product is processed and continues its process model. Production states don't have to be initialized because they are automatically created when a process is added to a resource.

    Args:
        ID (str): ID of the state.
        description (str): Description of the state.
        time_model_id (str): Time model ID of the state.
        type (StateTypeEnum): Type of the state.

    """

    type: Literal[StateTypeEnum.ProductionState]

    class Config:
        schema_extra = {
            "example": {
                "summary": "Production state",
                "value": {
                    "ID": "ProductionState_1",
                    "description": "Production state machine 1",
                    "time_model_id": "function_time_model_1",
                    "type": "ProductionState",
                },
            }
        }


class TransportStateData(StateData):
    """
    Class that represents a transport state. By undergoing a transport state, the product is transported and its position is changed. Transport states don't have to be initialized because they are automatically created when a transport process is added to a resource.

    Args:
        ID (str): ID of the state.
        description (str): Description of the state.
        time_model_id (str): Time model ID of the state.
        type (StateTypeEnum): Type of the state.
    """

    type: Literal[StateTypeEnum.TransportState]
    handling_time_model: Optional[str] = None
    if handling_time_model is not None:
        setattr('handling_time_model', handling_time_model)

    class Config:
        schema_extra = {
            "example": {
                "summary": "Transport state",
                "value": {
                    "ID": "TransportState_1",
                    "description": "Transport state machine 1",
                    "time_model_id": "function_time_model_3",
                    "type": "TransportState",
                },
            }
        }


class SetupStateData(StateData):
    """
    Class that represents a setup state. By undergoing a setup state, the process is setup.

    Args:
        ID (str): ID of the state.
        description (str): Description of the state.
        time_model_id (str): Time model ID of the state.
        type (StateTypeEnum): Type of the state.
        origin_setup (str): ID of the origin process for the setup.
        target_setup (str): ID of the target process for the setup.

    Examples:
        Setup state with a function time model:
        ``` py
        import prodsys
        prodsys.state_data.SetupStateData(
            ID="Setup_State_2",
            description="Setup state machine 2",
            time_model_id="function_time_model_2",
            origin_setup="P2",
            target_setup="P1",
        )
        ```
    """

    type: Literal[StateTypeEnum.SetupState]
    origin_setup: str
    target_setup: str

    def hash(self, adapter: ProductionSystemAdapter) -> str:
        """
        Returns a unique hash of the state considering the time model, origin and target setup process. Can be used to compare states for equal functionality.

        Args:
            adapter (ProductionSystemAdapter): Adapter to access the data of the state.

        Raises:
            ValueError: if the origin or target setup process is not found.

        Returns:
            str: hash of the state.
        """
        base_class_hash = super().hash(adapter)
        setup_process_hashes = []

        for process_id in [self.origin_setup, self.target_setup]:
            for process in adapter.process_data:
                if process.ID == process_id:
                    setup_process_hashes.append(process.hash(adapter))
                break
            else:
                raise ValueError(f"Process with ID {process_id} not found for setup state {self.ID}.")

        return md5(("".join([base_class_hash] + setup_process_hashes)).encode("utf-8")).hexdigest()

    class Config:
        schema_extra = {
            "example": {
                "summary": "Setup state",
                "value": {
                    "ID": "Setup_State_2",
                    "description": "Setup state machine 2",
                    "time_model_id": "function_time_model_2",
                    "type": "SetupState",
                    "origin_setup": "P2",
                    "target_setup": "P1",
                },
            }
        }


STATE_DATA_UNION = Union[
    BreakDownStateData,
    ProductionStateData,
    TransportStateData,
    SetupStateData,
    ProcessBreakDownStateData,
]
