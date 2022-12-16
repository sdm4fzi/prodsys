from __future__ import annotations

from typing import Literal, Union, List, Tuple, Optional

from pydantic import validator

from prodsim.data_structures.core_asset import CoreAsset


class MaterialData(CoreAsset):
    material_type: str
    processes: Union[List[str], str]
    transport_process: str
