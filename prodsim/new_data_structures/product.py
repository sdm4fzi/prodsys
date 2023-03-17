from __future__ import annotations

from typing import Literal, Union, List, Tuple, Optional

from pydantic import root_validator, BaseModel

from prodsim.data_structures.core_asset import CoreAsset

class AAS(BaseModel):
    type: str = "AssetAdministrationShell"

class Submodel(BaseModel):
    type: str = "Submodel"


class Product(CoreAsset, AAS):
    bom: BOM


class BOM(CoreAsset, Submodel):
    subProductCount: int