from __future__ import annotations

from typing import Literal, Union, List, Tuple, Optional

from pydantic import root_validator, BaseModel

from prodsim.data_structures.core_asset import CoreAsset

class AAS(BaseModel):
    type: str = "AssetAdministrationShell"

class Submodel(BaseModel):
    type: str = "Submodel"
    
class SubmodelElementCollection(BaseModel):
    type: str = "SubmodelElementCollection"
   
class Property(BaseModel):
    type: str = "Property"
    
class Reference(BaseModel):
    type: str = "Reference"




class Product(CoreAsset, AAS):
    bom: BOM


class BOM(CoreAsset, Submodel):
    assembly: file
    subProductCount: str
    subProduct: SubmodelElementCollection
    
    
    
class subProduct(CoreAsset, SubmodelElementCollection):
    subProbductType: str
    subProductAAS: Reference
    status: str
    quantity: str
    subProductAttributes: SubmodelElementCollection
    
class subProductAttributes(CoreAsset,SubmodelElementCollection):
    attribute: DataElement 