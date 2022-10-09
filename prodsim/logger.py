from __future__ import annotations
from ast import Call

from functools import partial, wraps
import functools

from pydantic import BaseModel
from typing import Callable, List, Union

from . import material
from . import state
from . import resources
from . import source


class Datacollector(BaseModel):
    data: dict = {'Resources': []}

    def log_data_to_csv(self, filepath: str):
        import pandas as pd

        df = pd.DataFrame(self.data['Resources'])
        df['Activity'] = pd.Categorical(df['Activity'], 
                            categories=[
                                'created material', 
                                'end state', 
                                'end interrupt', 
                                'start state', 
                                'start interrupt', 
                                'finished material'],
                            ordered=True)
        #TODO: maybe delete this line
        df.sort_values(by=['Time', 'Activity'], inplace=True)

        df.to_csv(filepath)

    def patch_state(self, __resource: Union[state.StateInfo, material.MaterialInfo], attr: List[str], pre: functools.partial=None, post: functools.partial=None):
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
                    pre(__resource)
                # Perform actual operation
                ret = func(*args, **kwargs)
                # Call "post" callback
                if post:
                    post(__resource)
                return ret
            return wrapper
        # Replace the original operations with our wrapper
        for name in attr:
            if hasattr(__resource, name):
                setattr(__resource, name, get_wrapper(getattr(__resource, name)))

    def register_patch(self, __resource: Union[state.StateInfo, material.MaterialInfo], attr: List[str], pre:Callable=None, post: Callable=None):
        if pre is not None:
            pre = self.register_monitor(pre, self.data['Resources'])
        if post is not None:
            post = self.register_monitor(post, self.data['Resources'])
        self.patch_state(__resource, attr, pre, post)

    def register_monitor(self, monitor: Callable, data: list) -> functools.partial:
        partial_monitor = partial(monitor, data)
        return partial_monitor

def post_monitor_resource(data: List[tuple], __resource: resources.Resource):
    """This is our monitoring callback."""
    if __resource.current_process:
        process_ID = __resource.current_process.ID
    else:
        process_ID = None
    item = (
        __resource.ID,
        process_ID,
        __resource.count,
        __resource.env.now,
    )
    data.append(item)


def pre_monitor_state(data: List[tuple], __state: state.State):
    __resource = __state.resource
    if __resource.current_process:
        process_ID = __resource.current_process.ID
    else:
        process_ID = None

    item = (
        __resource.ID,
        process_ID,
        __resource.env.now,
        __state.done_in,
        False
    )
    data.append(item)

def post_monitor_state(data: List[tuple], __state: state.State):
    __resource = __state.resource
    if __resource.current_process:
        process_ID = __resource.current_process.ID
    else:
        process_ID = None

    item = (
        __resource.ID,
        process_ID,
        __resource.env.now,
        __state.done_in,
        True
    )
    data.append(item)

def post_monitor_state_info(data: List[tuple], state_info: state.StateInfo):
    item = {
        'Time': state_info._event_time,
        'Resource': state_info.resource_ID,
        'State': state_info.ID,
        'Activity': state_info._activity,
        'Expected End Time': state_info._expected_end_time,
        'Material': state_info._material_ID,
        'Target location': state_info._target_ID
    }
    data.append(item)

def post_monitor_material_info(data: List[tuple], material_info: material.MaterialInfo):

    item = {
        'Time': material_info.event_time,
        'Resource': material_info.resource_ID,
        'State': material_info.state_ID,
        'Activity': material_info.activity,
        'Material': material_info._material_ID
    }
    data.append(item)