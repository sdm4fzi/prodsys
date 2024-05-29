from abc import ABC, abstractmethod

from prodsys.models import core_asset

class ExpressObject(ABC):
    """
    Abstract base class to represents an express object.
    """

    @abstractmethod
    def to_model(self) -> core_asset.CoreAsset:
        """
        Converts the `prodsys.express` object to a data object from `prodsys.models`.

        Returns:
            core_asset.CoreAsset: An instance of the data object.
        """
        pass
