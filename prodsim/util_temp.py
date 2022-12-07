from __future__ import annotations

import random

import numpy as np
from typing import Dict, Union


def get_class_from_str(name: str, cls_dict: dict):
    if name not in cls_dict.keys():
        raise ValueError(f"Class '{name}' is not implemented.")
    return cls_dict[name]

def set_seed(seed: int) -> None:
    np.random.seed(seed)
    random.seed(seed)
