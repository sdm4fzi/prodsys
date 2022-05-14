from abc import ABC
from dataclasses import dataclass, field
from typing import List

from base import IDEntity
from env import Environment


@dataclass
class Material(ABC, IDEntity):
    quality: float


@dataclass
class ConcreteMaterial(Material):
    due_time: float = None


@dataclass
class Order(ABC, IDEntity):
    env: Environment
    target_materials: List[Material]
    release_time: float
    due_time: float
    current_materials: List[Material] = field(default_factory=lambda: [], init=False)

    def add_current_material(self, material: Material):
        self.current_materials.append(material)

    def remove_current_material(self, material: Material):
        self.current_materials.remove(material)
