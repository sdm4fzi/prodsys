from __future__ import annotations


from re import S
from typing import Optional
from prodsys.models.core_asset import Interactable, Locatable
from prodsys.models.positions_data import InteractionPoint
from prodsys.simulation.router import Router


def get_interaction_point_key(
    interactable_id: str,
    interaction_type: str,
    product_id: Optional[str] = None,
    dependency_id: Optional[str] = None,
) -> str:
    """
    Returns a unique key for the interaction point based on its ID and types.

    Args:
        interaction_point (dict[str, str]): The interaction point.

    Returns:
        str: The unique key for the interaction point.
    """
    return f"{interactable_id}_{interaction_type}_{product_id}_{dependency_id}"


def transform_pose(
    pose: SimulationPose,
    reference_pose: SimulationPose,
) -> SimulationPose:
    """
    Transforms a pose based on a reference pose.

    Args:
        pose (SimulationPose): The pose to be transformed.
        reference_pose (SimulationPose): The reference pose.

    Returns:
        SimulationPose: The transformed pose.
    """
    return SimulationPose(
        x=pose.x + reference_pose.x,
        y=pose.y + reference_pose.y,
        z=pose.z + reference_pose.z,
        yaw=pose.yaw + reference_pose.yaw,
        pitch=pose.pitch + reference_pose.pitch,
        roll=pose.roll + reference_pose.roll,
    )

class SimulationPose:
    def __init__(self, x: float, y: float, z: float = 0.0, 
                 yaw: float = 0.0, pitch: float = 0.0, roll: float = 0.0,
                 reference_pose: Optional[SimulationPose] = None):
        self.x = x
        self.y = y
        self.z = z
        self.yaw = yaw
        self.pitch = pitch
        self.roll = roll
        self.reference_pose = reference_pose


    def get_abs_pose(self) -> SimulationPose:
        """
        Returns the absolute pose of the object.

        Returns:
            SimulationPose: The absolute pose of the object.
        """
        if self.reference_pose is None:
            return self
        return transform_pose(self, self.reference_pose.get_abs_pose())
        
# TODO: for better modularization, add a 3D advanced position manager and a simple one in 2D without interaction points
# TODO: same for the path finding -> one is A* with 3D objects and collosion detection, the other is a simple 2D manhattan distance one


class PositionsManager:
    """
    Manages the positions of the agents in the simulation.
    """

    # TODO: implement a class method to instantiate from sources, resources, ...

    def __init__(self, locatable_positions: dict[str, SimulationPose], interaction_points: dict[str, SimulationPose]):
        """
        Initializes the PositionsManager with a router.

        Args:
            router (Router): The router to be used for managing positions.
        """
        self.locatable_positions: dict[str, SimulationPose] = locatable_positions
        self.interaction_points: dict[str, SimulationPose] = interaction_points


    def add_locatable(self, locatable: Locatable):
        """
        Adds a locatable asset to the positions manager.

        Args:
            locatable (Locatable): The locatable asset to be added.
        """
        self.locatable_positions[locatable.ID] = locatable.pose
        if isinstance(locatable, Interactable):
            for interaction_point in locatable.interaction_points:
                key = get_interaction_point_key(
                    locatable.ID,
                    interaction_point.types[0],
                    interaction_point.product_ids,
                    interaction_point.dependency_ids,
                )
                self.interaction_points[key] = interaction_point.pose

    def update_locatable(self, locatable: Locatable, pose: SimulationPose):
        """
        Updates the position of a locatable asset.

        Args:
            locatable (Locatable): The locatable asset to be updated.
            pose (SimulationPose): The new pose of the locatable asset.
        """
        self.locatable_positions[locatable.ID] = pose
        if isinstance(locatable, Interactable):
            for interaction_point in locatable.interaction_points:
                key = get_interaction_point_key(
                    locatable.ID,
                    interaction_point.types[0],
                    interaction_point.product_ids,
                    interaction_point.dependency_ids,
                )
                self.interaction_points[key] = interaction_point.pose
    
    def get_position(self, locatable_id: str, interaction_type: Optional[str] = None, product_id: Optional[str] = None, dependency_id: Optional[str] = None) -> SimulationPose:
        """
        Returns the position of a locatable asset.

        Args:
            locatable_id (str): The ID of the locatable asset.
            interaction_type (str, optional): The type of interaction point. Defaults to None.

        Returns:
            InteractionPoint: The position of the locatable asset.
        """
        if interaction_type is not None:
            key = get_interaction_point_key(locatable_id, interaction_type)
            return self.interaction_points.get(key)
        return self.locatable_positions.get(locatable_id)
    
    def get_path_to(self, locatable_id: str, target_id: str, interaction_type: Optional[str] = None, product_id: Optional[str] = None, dependency_id: Optional[str] = None) -> list[SimulationPose]:
        """
        Returns the path to a target locatable asset.

        Args:
            locatable_id (str): The ID of the locatable asset.
            target_id (str): The ID of the target locatable asset.
            interaction_type (str, optional): The type of interaction point. Defaults to None.

        Returns:
            list[SimulationPose]: The path to the target locatable asset.
        """
        # TODO: cache paths!
        if interaction_type is not None:
            key = get_interaction_point_key(target_id, interaction_type)
            return self.router.get_path(self.locatable_positions[locatable_id], self.interaction_points[key])
        return self.router.get_path(self.locatable_positions[locatable_id], self.locatable_positions[target_id])