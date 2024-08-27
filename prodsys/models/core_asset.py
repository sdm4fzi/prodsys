from pydantic import BaseModel, ConfigDict


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