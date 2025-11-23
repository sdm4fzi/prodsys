from typing import List

from prodsys.simulation.entities.entity import Entity, EntityType
from prodsys.simulation.locatable import Locatable
import simpy


class Lot(Entity):
    """
    Composite entity containing multiple entities processed together.
    
    A Lot is an Entity that can flow through the system
    like a Product. It implements the same interface.
    """
    def __init__(self, entities: List[Entity], all_completed_events: List[simpy.Event]):
        self.entities = entities  # Can contain Products, Primitives, or other Lots!
        self.all_completed_events = all_completed_events
        self.env = entities[0].env
        self.data = entities[0].data
        self.current_locatable = None
        self.router = entities[0].router
        self.no_transport_to_sink = False
        # Lot can have its own process model
        if entities[0].type == EntityType.PRODUCT:
            self.process_model = entities[0].process_model
        else:
            self.process_model = None
    
    @property
    def type(self) -> EntityType:
        return EntityType.LOT

    @property
    def size(self) -> int:
        """Total size is sum of contained entity sizes (handles nesting)"""
        return sum(entity.size for entity in self.entities)
    
    def update_location(self, locatable: Locatable) -> None:
        """Update location for lot and all contained entities"""
        self.current_locatable = locatable
        for entity in self.entities:
            entity.update_location(locatable)
    
    def get_atomic_entities(self) -> List[Entity]:
        """Flatten nested lots to get all atomic entities"""
        atomic = []
        for entity in self.entities:
            if isinstance(entity, Lot):
                atomic.extend(entity.get_atomic_entities())
            else:
                atomic.append(entity)
        return atomic

    def get_primary_entity(self) -> Entity:
        """Get the primary entity of the lot"""
        return self.entities[0]