from dataclasses import dataclass
from pydantic import BaseModel


@dataclass
class IDEntity:
    ID: str
    description: str


class BaseAsset(BaseModel):
    ID: str
    description: str
