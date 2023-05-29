from abc import ABC, abstractmethod, abstractclassmethod
import uuid
from pydantic import validator, Field
import pydantic
from pydantic.dataclasses import dataclass

from prodsys.models import core_asset

class ExpressObject(ABC):
    """
    Abstract base class to represents an express object.
    """

    @abstractmethod
    def to_data_object(self) -> core_asset.CoreAsset:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            core_asset.CoreAsset: An instance of the data object.
        """
        pass
