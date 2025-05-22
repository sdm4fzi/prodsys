from hashlib import md5
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, conlist, model_validator

from prodsys.models.positions_data import InteractionPoint, Pose


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


# make a validator that assures that location or pose are entered


class Locatable(CoreAsset):
    """
    Class that represents a locatable entity, consisting of an ID, a description and a location.

    Args:
        location (list[float]): The location of the locatable asset. It has to be a list of length 2.
    """
    pose: Pose

    def hash(self) -> str:
        """
        Returns a unique hash for the locatable asset considering its location, input location and output location.

        Returns:
            str: Hash of the locatable asset.
        """
        return md5((self.pose.hash()).encode("utf-8")).hexdigest()


class Interactable(Locatable):
    """
    Class that represents a locatable entity with an input location. The location parameter is the center point of the asset. It needs to be defined. The input location parameter specifies where products are added to the asset. If not specified, the location is set as input location.

    Args:
        location (list[float]): The location of the locatable asset. It has to be a list of length 2.
        input_location (list[float], optional): The input location of the locatable asset. It has to be a list of length 2. Defaults to None.
    """
    interaction_points: list[InteractionPoint]

    def hash(self) -> str:
        """
        Returns a unique hash for the locatable asset considering its location and input location.

        Returns:
            str: Hash of the locatable asset.
        """
        base_class_hash = Locatable.hash(self)
        interaction_points_hash = "".join(
            [interaction_point.hash() for interaction_point in self.interaction_points]
        )
        return md5((base_class_hash + interaction_points_hash).encode("utf-8")).hexdigest()