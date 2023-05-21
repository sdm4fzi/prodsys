from abc import ABC, abstractmethod, abstractclassmethod
import uuid
from pydantic import validator, Field
import pydantic
from pydantic.dataclasses import dataclass

from prodsys.data_structures import core_asset

class ExpressObject(ABC):
    """
    Abstract base class to represents an express object.
    """

    @abstractmethod
    def to_data_object(self) -> core_asset.CoreAsset:
        """
        Converts the express object (prodsys.express) to a data object (prodsys.data_structures).

        Returns:
            core_asset.CoreAsset: An instance of the data object.
        """
        pass




@dataclass
class Identifier:
    """
    Class that represents an identifier.

    Returns:
        id: ID of the identifier. Default is a random UUID.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid1()))

    def __str__(self) -> str:
        return self.id
    
    def __repr__(self) -> str:
        return self.id
    
identifier_field = Field(default_factory=Identifier)

def check_identifier(identifier):
    if type(identifier) == str:
        return Identifier(id=identifier)
    return identifier

identifier_field_validator = validator('ID', allow_reuse=True)(check_identifier)