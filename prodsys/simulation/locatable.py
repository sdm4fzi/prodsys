from typing import Protocol

from prodsys.models import core_asset

class Locatable(Protocol):
    """
    Protocol that defines the interface for a locatable entity.
    """

    @property
    def data(self) -> core_asset.Locatable: # TODO: maybe make type hints more clear here...
        """
        Returns the data of the locatable.
        """
        pass

    def get_location(self) -> list[float]:
        """
        Returns the location of the locatable.
        """
        pass

    def update_location(self, location: list[float]) -> None:
        """
        Updates the location of the locatable.
        """
        pass