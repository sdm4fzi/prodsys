from functools import partial, wraps

import resource
from material import Material
import state


class Datacollector:
    data = {'Resources': []}

    def patch_state(self, __resource, attr, pre=None, post=None):
        """Patch *state* so that it calls the callable *pre* before each
        put/get/request/release operation and the callable *post* after each
        operation.  The only argument to these functions is the resource
        instance."""
        def get_wrapper(func):
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

    def register_patch(self, __resource, attr, pre=None, post=None):
        if pre is not None:
            pre = self.register_monitor(pre, self.data['Resources'])
        if post is not None:
            post = self.register_monitor(post, self.data['Resources'])
        self.patch_state(__resource, attr, pre, post)

    def register_monitor(self, monitor, data):
        partial_monitor = partial(monitor, data)
        return partial_monitor

def post_monitor_resource(data, __resource: resource.Resource):
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


def pre_monitor_state(data, __state: state.State):
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

def post_monitor_state(data, __state: state.State):
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


# def post_monitor_state_info(data, state_info: state.StateInfo):
#     item = (
#         state_info.event_time,
#         state_info._resource_ID,
#         state_info.ID,
#         state_info.activity,
#         state_info.expected_end_time
#     )
#     data.append(item)

def post_monitor_state_info(data, state_info: state.StateInfo):
    item = {
        'Time': state_info.event_time,
        'Resource': state_info._resource_ID,
        'State': state_info.ID,
        'Activity': state_info.activity,
        'Expected End Time': state_info.expected_end_time,
        'Material': state_info._material_ID,
        'Target location': state_info._target_ID
    }
    data.append(item)