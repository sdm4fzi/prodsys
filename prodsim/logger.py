from __future__ import annotations

import functools
from functools import partial, wraps
from typing import Callable, List, Union, TYPE_CHECKING, Dict, Any, Optional

import pandas as pd
from pydantic import BaseModel


if TYPE_CHECKING:
    from prodsim import material, resources, state


class Datacollector(BaseModel):
    data: Dict[str, Any] = {"Resources": []}

    def log_data_to_csv(self, filepath: str):

        df = self.get_data()
        df["Activity"] = pd.Categorical(
            df["Activity"],
            categories=[
                "created material",
                "end state",
                "end interrupt",
                "start state",
                "start interrupt",
                "finished material",
            ],
            ordered=True,
        )
        df.to_csv(filepath)

    def get_data(self) -> pd.DataFrame:
        df = pd.DataFrame(self.data["Resources"])
        return df

    def patch_state(
        self,
        resource: Union[state.StateInfo, material.MaterialInfo],
        attr: List[str],
        pre: Optional[functools.partial] = None,
        post: Optional[functools.partial] = None,
    ):
        """Patch *state* so that it calls the callable *pre* before each
        put/get/request/release operation and the callable *post* after each
        operation.  The only argument to these functions is the resource
        instance."""

        def get_wrapper(func: Callable) -> Callable:
            # Generate a wrapper for a process state function
            @wraps(func)
            def wrapper(*args, **kwargs):
                # This is the actual wrapper
                # Call "pre" callback
                if pre:
                    pre(resource)
                # Perform actual operation
                ret = func(*args, **kwargs)
                # Call "post" callback
                if post:
                    post(resource)
                return ret

            return wrapper

        # Replace the original operations with our wrapper
        for name in attr:
            if hasattr(resource, name):
                setattr(resource, name, get_wrapper(getattr(resource, name)))

    def register_patch(
        self,
        resource: Union[state.StateInfo, material.MaterialInfo],
        attr: List[str],
        pre: Optional[Callable] = None,
        post: Optional[Callable] = None,
    ):  
        if pre is not None:
            pre = self.register_monitor(pre, self.data["Resources"])
        if post is not None:
            post = self.register_monitor(post, self.data["Resources"])
        self.patch_state(resource, attr, pre, post)

    def register_monitor(self, monitor: Callable, data: list) -> functools.partial:
        partial_monitor = partial(monitor, data)
        return partial_monitor


def post_monitor_resource(data: List[tuple], resource: resources.Resourcex):
    """This is our monitoring callback."""
    if resource.current_process:
        process_ID = resource.current_process.process_data.ID
    else:
        process_ID = None
    item = (
        resource.data.ID,
        process_ID,
        resource.count,
        resource.env.now,
    )
    data.append(item)


def pre_monitor_state(data: List[tuple], state: state.State):
    resource = state.resource
    if resource.current_process:
        process_ID = resource.current_process.process_data.ID
    else:
        process_ID = None

    item = (
        resource.data.ID,
        process_ID,
        resource.env.now,
        state.done_in,  # type: ignore        False
    )
    data.append(item)


def post_monitor_state(data: List[tuple], state: state.State):
    resource = state.resource
    if resource.current_process:
        process_ID = resource.current_process.process_data.ID
    else:
        process_ID = None

    item = (
        resource.data.ID,
        process_ID,
        resource.env.now,
        state.done_in,  # type: ignore False
        True,
    )
    data.append(item)


def post_monitor_state_info(data: List[dict], state_info: state.StateInfo):
    item = {
        "Time": state_info._event_time,
        "Resource": state_info.resource_ID,
        "State": state_info.ID,
        "Activity": state_info._activity,
        "Expected End Time": state_info._expected_end_time,
        "Material": state_info._material_ID,
        "Target location": state_info._target_ID,
    }
    data.append(item)


def post_monitor_material_info(data: List[dict], material_info: material.MaterialInfo):

    item = {
        "Time": material_info.event_time,
        "Resource": material_info.resource_ID,
        "State": material_info.state_ID,
        "Activity": material_info.activity,
        "Material": material_info.material_ID,
    }
    data.append(item)
