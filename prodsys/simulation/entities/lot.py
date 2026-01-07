from typing import List

from prodsys.simulation.entities.entity import Entity, EntityType
from prodsys.simulation.locatable import Locatable
from prodsys.simulation.dependency import DependedEntity
from typing import Optional, List
from prodsys.simulation.dependency import Dependency
from prodsys.models.dependency_data import DependencyType
from prodsys.models.core_asset import CoreAsset
import simpy

class Lot(Entity):
    """
    Composite entity containing multiple entities processed together.
    
    A Lot is an Entity that can flow through the system
    like a Product. It implements the same interface.
    """
    def __init__(self, entities: List[Entity], all_completed_events: List[simpy.Event], resolved_dependency: Dependency, required_dependencies: Optional[List[Dependency]] = None):
        self.data = CoreAsset(ID="Lot_" + entities[0].data.ID, description="Lot of " + entities[0].data.ID)
        self.entities = entities  # Can contain Products, Primitives, or other Lots!
        self.all_completed_events = all_completed_events
        self.env = entities[0].env
        self.data = entities[0].data
        self._current_locatable = entities[0].current_locatable
        self.router = entities[0].router
        self.no_transport_to_sink = False
        # Initialize depended_entities with custom list that handles lot's own + constituent entities
        
        self.dependencies: Optional[List[Dependency]] = self._get_relevant_dependencies(required_dependencies)
        self.depended_entities: List[DependedEntity] = []
        self.current_dependant = None

        for entity in self.entities:
            entity.bind(self, resolved_dependency)
        
        # Lot can have its own process model
        if entities[0].type == EntityType.PRODUCT:
            self.process_model = entities[0].process_model
        else:
            self.process_model = None

    def _get_relevant_dependencies(self, required_dependencies: Optional[List[Dependency]] = None) -> List[Dependency]:
        """Get the relevant dependencies for the lot"""
        relevant_dependencies = {dependency.data.ID: dependency for dependency in required_dependencies}
        dependency_ids_per_instance: dict[str, int] = {}
        for entity in self.entities:
            # only consider tool dependencies with per_lot = True only once. 
            # Same goes for resource or process dependencies.
            if entity.dependencies is None:
                continue
            for dependency in entity.dependencies:
                if dependency.data.ID in relevant_dependencies:
                    relevant_dependencies[dependency.data.ID] = dependency

                if dependency.data.dependency_type == DependencyType.TOOL and dependency.data.per_lot and dependency.data.ID in dependency_ids_per_instance:
                    continue
                elif (dependency.data.dependency_type == DependencyType.RESOURCE or dependency.data.dependency_type == DependencyType.PROCESS) and dependency.data.ID in dependency_ids_per_instance:
                    continue
                
                if dependency.data.ID not in dependency_ids_per_instance:
                    dependency_ids_per_instance[dependency.data.ID] = 0
                dependency_ids_per_instance[dependency.data.ID] += 1
        required_dependencies = []
        for dependency_id, count in dependency_ids_per_instance.items():
            required_dependencies.extend([relevant_dependencies[dependency_id]] * count)
        return required_dependencies
    
    @property
    def type(self) -> EntityType:
        return EntityType.LOT

    def clear(self) -> None:
        """Clear the lot and all contained entities"""
        for entity in self.entities:
            entity.release()

    @property
    def size(self) -> int:
        """Total size is sum of contained entity sizes (handles nesting)"""
        return sum(entity.size for entity in self.entities)
    
    def update_location(self, locatable: Locatable) -> None:
        """Update location for lot and all contained entities"""
        self._current_locatable = locatable
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