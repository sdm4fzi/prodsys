from uuid import UUID, uuid1
from dataclasses import dataclass

@dataclass
class IDEntity:
    description : str
    _id : UUID

    def get_id(self) -> UUID:
        return self._id

    def get_description(self):
        return self._description