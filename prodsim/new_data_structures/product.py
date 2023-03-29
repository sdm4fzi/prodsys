from __future__ import annotations

from typing import Literal, Union, List, Tuple, Optional

from pydantic import root_validator, BaseModel

from prodsim.data_structures.core_asset import CoreAsset

class AAS(CoreAsset):
    type: str = "AssetAdministrationShell"
    ID: str
    description: str


class Submodel(CoreAsset):
    type: str = "Submodel"
    ID: str
    description: str

    
class SubmodelElementCollection(CoreAsset):
    type: str = "SubmodelElementCollection"
    ID: str
    description: str





class BOM(Submodel):
    ID: str
    description: str
    assembly: str
    subProductCount: Optional[str]
    subProduct: SubmodelElementCollection
    
    
class subProduct(SubmodelElementCollection):
    subProbductType: str
    subProductAAS: str
    status: str
    quantity: str
    subProductAttributes: SubmodelElementCollection
    
    
class subProductAttributes(SubmodelElementCollection):
    attribute: str 

class Product(AAS):
    ID: str
    description: str
    bom: BOM