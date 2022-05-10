from abc import ABC, abstractmethod
from cmd import IDENTCHARS
from dataclasses import dataclass, field
from base import IDEntity
from resource import Resource
from typing import List
import simpy

@dataclass
class Material(ABC, IDEntity):
    position : Resource
    quality : float

@dataclass
class ConcreteMaterial(Material):
    due_time : float = None

@dataclass
class order(ABC, IDEntity):
    env : 
    target_materials : List[Material]
    release_time : float
    due_time : float
    current_materials : List[Material] = field(default=[], init=False)

    def add_current_material(self):
        self.current_materials.append(Material)
        if self.current_materials and target_
    
    def remove_current_material(self, material : Material):
        self.current_materials.remove(material)

