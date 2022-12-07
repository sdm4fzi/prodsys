from pydantic import BaseModel

class CoreAsset(BaseModel):
    ID: str
    description: str
