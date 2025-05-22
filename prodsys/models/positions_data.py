from hashlib import md5
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

from prodsys.models.core_asset import CoreAsset

class Pose(BaseModel):
    """
    Class that represents a transformation in 3D space, which is a pose of an entity relative to a reference frame.

    Args:
        x (float): X coordinate.
        y (float): Y coordinate.
        z (float, optional): Z coordinate. Defaults to 0.0.
        yaw (float, optional): Rotation around vertical axis (heading). Defaults to 0.0.
        pitch (float, optional): Rotation around lateral axis. Defaults to 0.0.
        roll (float, optional): Rotation around longitudinal axis. Defaults to 0.0.
        reference_frame_id (str, optional): ID of the reference frame. Defaults to None.
    """
    x: float
    y: float
    z: float = 0.0
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    reference_frame_id: Optional[str] = None

    def hash(self) -> str:
        """
        Returns a unique hash for the pose considering its position and rotation.

        Returns:
            str: Hash of the pose.
        """
        return md5(
            (str(self.x) + str(self.y) + str(self.z) + str(self.yaw) + str(self.pitch) + str(self.roll)).encode(
                "utf-8"
            )
        ).hexdigest()


class InteractionType(str, Enum):
    DEPENDENCY = "Dependency"
    PRODUCT_INPUT = "ProductInput"
    PRODUCT_OUTPUT = "ProductOutput"
    PRODUCT_INTERNAL = "ProductInternal"


class InteractionPoint(CoreAsset):
    types: list[InteractionType]
    pose: Pose
    product_ids: Optional[List[str]] = Field(
        default=None,
        description="List of product IDs that can be processed at this interaction point.",
    )
    dependency_ids: Optional[List[str]] = Field(
        default=None,
        description="List of dependency IDs that can be processed at this interaction point.",
    )

    def hash(self) -> str:
        """
        Returns a unique hash for the interaction point considering its ID, description, types and pose.

        Returns:
            str: Hash of the interaction point.
        """
        # TODO: consider product_ids and dependency_ids for hash calculation based of their hash from the adapter!
        return md5(
            (str(self.types) + self.pose.hash()).encode(
                "utf-8"
            )
        ).hexdigest()
