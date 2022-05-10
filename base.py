from uuid import UUID, uuid1
from dataclasses import dataclass, field

@dataclass
class IDEntity:
    description : str
    _id: UUID = field(default=uuid1(), init=False)

    


    @property
    def __id(self) -> UUID:
        return self._id
    
    def get_description(self):
        return self._description