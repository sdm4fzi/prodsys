from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from prodsys.simulation import locatable
from prodsys.simulation.dependency import DependedEntity
from typing import Optional, List, Union
from prodsys.simulation.dependency import Dependency
from prodsys.simulation import resources

class Entity(ABC):
    """
    Base class for all entities that flow through the production system.
    
    Entities:
    - Occupy locations (resources, queues, nodes)
    - Can be transported between locations
    - Occupy capacity in resources and queues
    - Can be routed through the system
    """

    @property
    def current_locatable(self) -> locatable.Locatable:
        if self.current_dependant:
            return self.current_dependant.current_locatable
        return self._current_locatable


    @property
    @abstractmethod
    def type(self) -> EntityType:
        """Type of the entity"""
        pass
    
    @property
    @abstractmethod
    def size(self) -> int:
        """Capacity units this entity requires"""
        pass
    
    @abstractmethod
    def update_location(self, locatable: locatable.Locatable) -> None:
        """Update current location"""
        pass

class EntityType(str, Enum):
    PRODUCT = "product"
    PRIMITIVE = "primitive"
    LOT = "lot"