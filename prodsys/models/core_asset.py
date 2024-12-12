from hashlib import md5
from typing import Any, Optional
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


class Locatable(BaseModel):
    """
    Class that represents a locatable entity, consisting of an ID, a description and a location.

    Args:
        location (list[float]): The location of the locatable asset. It has to be a list of length 2.
    """

    location: list[float] = Field(..., min_length=2, max_length=2)

    def hash(self) -> str:
        """
        Returns a unique hash for the locatable asset considering its location, input location and output location.

        Returns:
            str: Hash of the locatable asset.
        """
        return md5((str(self.location)).encode("utf-8")).hexdigest()


class InLocatable(Locatable):
    """
    Class that represents a locatable entity with an input location. The location parameter is the center point of the asset. It needs to be defined. The input location parameter specifies where products are added to the asset. If not specified, the location is set as input location.

    Args:
        location (list[float]): The location of the locatable asset. It has to be a list of length 2.
        input_location (list[float], optional): The input location of the locatable asset. It has to be a list of length 2. Defaults to None.
    """

    input_location: Optional[list[float]] = Field(None, min_length=2, max_length=2)

    @model_validator(mode="before")
    @classmethod
    def check_locations(cls, data: Any) -> Any:
        assert "location" in data, "location has to be defined."
        if not "input_location" in data or not data["input_location"]:
            data["input_location"] = data["location"]
        return data

    def hash(self) -> str:
        """
        Returns a unique hash for the locatable asset considering its location and input location.

        Returns:
            str: Hash of the locatable asset.
        """
        return md5(
            (str(self.location) + str(self.input_location)).encode("utf-8")
        ).hexdigest()


class OutLocatable(Locatable):
    """
    Class that represents a locatable entity with an output location. The location parameter is the center point of the asset. It needs to be defined. The output location parameter specifies where products are removed from the asset. If not specified, the location is set as output location.

    Args:
        location (list[float]): The location of the locatable asset. It has to be a list of length 2.
        output_location (list[float], optional): The output location of the locatable asset. It has to be a list of length 2. Defaults to None.
    """

    output_location: Optional[list[float]] = Field(None, min_length=2, max_length=2)

    @model_validator(mode="before")
    @classmethod
    def check_locations(cls, data: Any) -> Any:
        assert "location" in data, "location has to be defined."
        if not "output_location" in data or not data["output_location"]:
            data["output_location"] = data["location"]
        return data

    def hash(self) -> str:
        """
        Returns a unique hash for the locatable asset considering its location and output location.

        Returns:
            str: Hash of the locatable asset.
        """
        return md5(
            (str(self.location) + str(self.output_location)).encode("utf-8")
        ).hexdigest()


class InOutLocatable(InLocatable, OutLocatable):
    """
    Class that represents a locatable entity with an input location and an output location. The location parameter is the center point of the asset. It needs to be defined. The input location parameter specifies where products are added to the asset. If not specified, the location is set as input location. The output location parameter specifies where products are removed from the asset. If not specified, the location is set as output location.

    Args:
        location (list[float]): The location of the locatable asset. It has to be a list of length 2.
        input_location (list[float], optional): The input location of the locatable asset. It has to be a list of length 2. Defaults to None.
        output_location (list[float], optional): The output location of the locatable asset. It has to be a list of length 2. Defaults to None.
    """

    @model_validator(mode="before")
    @classmethod
    def check_locations(cls, data: Any) -> Any:
        data = InLocatable.check_locations(data)
        data = OutLocatable.check_locations(data)
        return data

    def hash(self) -> str:
        """
        Returns a unique hash for the locatable asset considering its location, input location and output location.

        Returns:
            str: Hash of the locatable asset.
        """
        return md5(
            (
                str(self.location)
                + str(self.input_location)
                + str(self.output_location)
            ).encode("utf-8")
        ).hexdigest()
