"""
The `prodsys.models.layout_data` module contains data structures that describe the physical
layout of a production system floor plan.

These models are used by the node/link generation utilities to plan traversable paths
based solely on the prodsys model — without requiring external XML layout files.

The following classes are available:

- `ResourceFootprint`: Physical bounding-box dimensions of a resource (width × height).
- `ObstacleData`: A standalone physical obstacle (wall, pillar, …) with no process association.
- `LayoutAreaData`: A rectangular traversable area on the factory floor.
- `LayoutData`: Top-level container that collects areas and obstacles for one production system.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field

from prodsys.models.core_asset import Location2D


class ResourceFootprint(BaseModel):
    """
    Physical bounding-box of a resource on the factory floor.

    The footprint is centered on the resource's ``location`` and defines how much
    floor space the resource occupies.  It is used by the node/link generation to
    create station obstacles and correctly size trajectory-node offsets.

    Args:
        width (float): Extent of the resource in the x-direction (metres or the
            same unit as ``location``).
        height (float): Extent of the resource in the y-direction.
    """

    width: float = Field(..., gt=0, description="Bounding-box width in the x-direction.")
    height: float = Field(..., gt=0, description="Bounding-box height in the y-direction.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"width": 2.0, "height": 3.0}
        }
    )


class ObstacleData(BaseModel):
    """
    A physical obstacle in the factory layout that has no associated process or resource.

    Obstacles are used purely for layout planning: they block free-space so that
    path-planning algorithms route around them.  Typical examples are pillars,
    walls, structural columns, or keep-out zones.

    Args:
        ID (str): Unique identifier of the obstacle.
        description (str): Human-readable description.  Defaults to ``""``.
        location (list[float]): Centre of the obstacle as ``[x, y]``.
        width (float): Extent in the x-direction.
        height (float): Extent in the y-direction.
    """

    ID: str
    description: str = ""
    location: Location2D = Field(..., description="Centre of the obstacle [x, y].")
    width: float = Field(..., gt=0, description="Obstacle extent in the x-direction.")
    height: float = Field(..., gt=0, description="Obstacle extent in the y-direction.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ID": "Pillar_1",
                "description": "Structural pillar",
                "location": [5.0, 10.0],
                "width": 0.5,
                "height": 0.5,
            }
        }
    )


class LayoutAreaData(BaseModel):
    """
    A rectangular traversable area on the factory floor.

    When one or more ``LayoutAreaData`` entries are present in ``LayoutData``,
    the node/link generator uses them as the boundary for path planning instead
    of auto-computing borders from resource locations.  This allows the factory
    floor plan to be expressed directly in the prodsys model.

    Multiple areas can model non-rectangular floor plans (e.g. L-shaped shops).

    Args:
        ID (str): Unique identifier of the area.  Defaults to ``""``.
        description (str): Human-readable description.  Defaults to ``""``.
        x_min (float): Left boundary.
        y_min (float): Bottom boundary.
        x_max (float): Right boundary.
        y_max (float): Top boundary.
    """

    ID: str = ""
    description: str = ""
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ID": "MainFloor",
                "description": "Main production floor",
                "x_min": -5.0,
                "y_min": -5.0,
                "x_max": 50.0,
                "y_max": 30.0,
            }
        }
    )


class LayoutData(BaseModel):
    """
    Physical layout information for a production system.

    Attach this to ``ProductionSystemData.layout_data`` to enable model-driven
    layout planning without external XML files.

    - ``areas``: Define the traversable floor area(s).  If empty, the generator
      auto-derives a bounding box from resource locations (existing behaviour).
    - ``obstacles``: Physical obstacles (pillars, walls, …) that block paths.
      Each obstacle blocks the rectangular region around its ``location``.

    Args:
        areas (List[LayoutAreaData]): Traversable floor areas.  Defaults to ``[]``.
        obstacles (List[ObstacleData]): Physical obstacles.  Defaults to ``[]``.
    """

    areas: List[LayoutAreaData] = []
    obstacles: List[ObstacleData] = []

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "areas": [
                    {
                        "ID": "MainFloor",
                        "x_min": 0.0,
                        "y_min": 0.0,
                        "x_max": 40.0,
                        "y_max": 20.0,
                    }
                ],
                "obstacles": [
                    {
                        "ID": "Pillar_1",
                        "description": "Centre pillar",
                        "location": [20.0, 10.0],
                        "width": 1.0,
                        "height": 1.0,
                    }
                ],
            }
        }
    )
