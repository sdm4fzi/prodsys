from abc import ABC, abstractmethod
from dataclasses import Field, dataclass
from typing import List, Tuple
from hard_base import IDEntity
from uuid import UUID, uuid1


@dataclass
class Material(ABC, IDEntity):
    # position : Resource
    position : Tuple[float, float]
    quality : float
    due_time : float
    _id : UUID

@dataclass
class ConcreteMaterial(Material):
    due_time : float = None
