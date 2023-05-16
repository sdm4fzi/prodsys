from pydantic import BaseModel

class CoreAsset(BaseModel):
    ID: str
    description: str

    class Config:
        schema_extra = {
            "example": {
                "ID": "Example Core Asset",
                "description": "Asset data for Example Core Asset",
            }
        }
