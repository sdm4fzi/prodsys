from __future__ import annotations

from typing import Literal, Union, List, Tuple, Optional

from pydantic import root_validator, BaseModel

from prodsim.data_structures.core_asset import CoreAsset

class AAS(CoreAsset):
    type: str = "AssetAdministrationShell"

class Submodel(CoreAsset):
    type: str = "Submodel"
    
class SubmodelElementCollection(CoreAsset):
    type: str = "SubmodelElementCollection"
   




class Product(AAS):
    bom: BOM


class BOM(Submodel):
    assembly: file
    subProductCount: str
    subProduct: SubmodelElementCollection
    
    
class subProduct(SubmodelElementCollection):
    subProbductType: str
    subProductAAS: Reference
    status: str
    quantity: str
    subProductAttributes: SubmodelElementCollection
    
    
class subProductAttributes(SubmodelElementCollection):
    attribute: DataElement 