from __future__ import annotations

from typing import Union, List, Dict

from pydantic import root_validator

from prodsys.data_structures.core_asset import CoreAsset


class MaterialData(CoreAsset):
    """
    Class that represents material data. 

    Args:
        ID (str): ID of the material. If not given, the material type is used. Gets overwritten to the instance material ID, when an instance is created during simulation. 
        description (str): Description of the material.
        material_type (str): Type of the material. If not given, the ID is used.
        processes (Union[List[str], List[List[str]], Dict[str, List[str]]]): Processes of the material. This can be a list of process IDs, a list of edges or an adjacency matrix.
        transport_process (str): Transport process of the material.

    Examples:
        Material with sequential process model:
        >>> from prodsys.data_structures import material_data
        >>> material_data.MaterialData(
        ...     ID="Material_1",
        ...     description="Material 1",
        ...     material_type="Material_1",
        ...     processes=["P1", "P2", "P3"],
        ...     transport_process="TP1",
        ... )

        Material with adjacency matrix process model:
        >>> from prodsys.data_structures import material_data
        >>> material_data.MaterialData(
        ...     ID="Material_1",
        ...     description="Material 1",
        ...     material_type="Material_1",
        ...     processes={
        ...         "P1": ["P2", "P3"],
        ...         "P2": ["P3"],
        ...         "P3": [],
        ...     },
        ...     transport_process="TP1",
        ... )

        Material with graph edges process model:
        >>> from prodsys.data_structures import material_data
        >>> material_data.MaterialData(
        ...     ID="Material_1",
        ...     description="Material 1",
        ...     material_type="Material_1",
        ...     processes=[
        ...         ["P1", "P2"],
        ...         ["P1", "P3"],
        ...         ["P2", "P4"],
        ...         ["P3", "P4"],
        ...     ],
        ...     transport_process="TP1",
        ... )
    """
    material_type: str
    processes: Union[List[str], List[List[str]], Dict[str, List[str]]]
    transport_process: str

    @root_validator(pre=True)
    def check_processes(cls, values):
        if "material_type" in values and values["material_type"]:
            values["ID"] = values["material_type"]
        else:
            values["material_type"] = values["ID"]
        return values

    class Config:
        schema_extra = {
            "examples": {
                "Material with sequential process model": {
                    "summary": "Normal Material Model with sequential processes",
                    "value": {
                    "ID": "Material_1",
                    "description": "Material 1",
                    "material_type": "Material_1",
                    "processes": ["P1", "P2", "P3"],
                    "transport_process": "TP1",
                    }
                },
                "Material with adjacency matrix process model": {
                    "summary": "Material Model with adjacency matrix",
                    "value": {
                    "ID": "Material_1",
                    "description": "Material 1",
                    "material_type": "Material_1",
                    "processes": {
                        "P1": ["P2", "P3"],
                        "P2": ["P3"],
                        "P3": [],
                    },
                    "transport_process": "TP1",
                    }
                },
                "Material with graph edges process model": {
                    "summary": "Material Model with edges",
                    "value": {
                    "ID": "Material_1",
                    "description": "Material 1",
                    "material_type": "Material_1",
                    "processes": [
                        ["P1", "P2"],
                        ["P1", "P3"],
                        ["P2", "P4"],
                        ["P3", "P4"],
                    ],
                    "transport_process": "TP1",
                    }
                },
            }
        }
