from hashlib import md5
from typing import Annotated, Any, Optional
from pydantic import BaseModel, ConfigDict, Field, conlist, model_validator


class CoreAsset(BaseModel):
    """
    Class that represents a the core asset, consisting of an ID and a description.

    Args:
        ID (str): The unique ID of the core asset.
        description (str): The description of the core asset.
    """

    ID: str
    description: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ID": "Example Core Asset",
                "description": "Asset data for Example Core Asset",
            }
        }
    )

Location2D = Annotated[
    list[float],
    Field(
        ..., min_length=2, max_length=2, description="Location of an asset in 2D space with x and y coordinates."
    ),
]

class Locatable(BaseModel):
    """
    Class that represents a locatable entity, consisting of an ID, a description and a location.

    Args:
        location (list[float]): The location of the locatable asset. It has to be a list of length 2.
    """

    location: Location2D = Field(...)

    def hash(self) -> str:
        """
        Returns a unique hash for the locatable asset considering its location, input location and output location.

        Returns:
            str: Hash of the locatable asset.
        """
        return md5((str(self.location)).encode("utf-8")).hexdigest()