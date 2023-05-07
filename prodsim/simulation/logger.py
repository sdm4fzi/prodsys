from __future__ import annotations

import functools
import warnings
from enum import Enum
from abc import ABC, abstractmethod
warnings.simplefilter(action = "ignore", category = RuntimeWarning)
warnings.filterwarnings("ignore")
from functools import partial, wraps
from typing import Callable, List, Union, TYPE_CHECKING, Dict, Any, Optional

import pandas as pd
from pydantic import BaseModel

from prodsim.simulation import state


if TYPE_CHECKING:
    from prodsim.simulation import material, resources, control
    from prodsim.factories import resource_factory, material_factory


class Logger(BaseModel, ABC):

    @abstractmethod
    def get_data_as_dataframe(self) -> pd.DataFrame:
        pass

    def patch_state(
        self,
        object: Any,
        attr: List[str],
        pre: Optional[functools.partial] = None,
        post: Optional[functools.partial] = None,
    ):
        """Patch *state* so that it calls the callable *pre* before each
        operation and the callable *post* after each
        operation.  The only argument to these functions is the object
        instance."""

        def get_wrapper(func: Callable) -> Callable:
            # Generate a wrapper for a process state function
            @wraps(func)
            def wrapper(*args, **kwargs):
                # This is the actual wrapper
                # Call "pre" callback
                if pre:
                    pre(object)
                # Perform actual operation
                ret = func(*args, **kwargs)
                # Call "post" callback
                if post:
                    post(object)
                return ret

            return wrapper

        # Replace the original operations with our wrapper
        for name in attr:
            if hasattr(object, name):
                setattr(object, name, get_wrapper(getattr(object, name)))

    def register_patch(
        self,
        data: Any,
        object: Any,
        attr: List[str],
        pre: Optional[Callable] = None,
        post: Optional[Callable] = None,
    ):
        if pre is not None:
            pre = partial(pre, data)
        if post is not None:
            post = partial(post, data)
        self.patch_state(object, attr, pre, post)
    
    def log_data_to_csv(self, filepath: str):
        df = self.get_data_as_dataframe()
        df.to_csv(filepath)

    def log_data_to_json(self, filepath: str):
        df = self.get_data_as_dataframe()
        df.to_json(filepath)

 
def post_monitor_resource_states(data: List[dict], state_info: state.StateInfo):
    item = {
        "Time": state_info._event_time,
        "Resource": state_info.resource_ID,
        "State": state_info.ID,
        "State Type": state_info._state_type,
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
        "State Type": material_info.state_type,
        "Activity": material_info.activity,
        "Material": material_info.material_ID,
    }
    data.append(item)

class EventLogger(Logger):
    event_data: List[Dict[str, Union[str, int, float, Enum]]] = []


    def get_data_as_dataframe(self) -> pd.DataFrame:
        df = pd.DataFrame(self.event_data)
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
        df["Activity"] = df["Activity"].astype("string")
        return df
    
    def observe_resource_states(self, resource_factory: resource_factory.ResourceFactory):
        for r in resource_factory.resources:
            all_states = r.states + r.production_states + r.setup_states
            for __state in all_states:
                self.register_patch(
                    self.event_data,
                    __state.state_info,
                    attr=[
                        "log_start_state",
                        "log_start_interrupt_state",
                        "log_end_interrupt_state",
                        "log_end_state",
                    ],
                    post=post_monitor_resource_states,
                )

    def observe_terminal_material_states(self, material: material.Material):
        self.register_patch(
                    self.event_data,
                    material.material_info,
                    attr=["log_create_material", "log_finish_material"],
                    post=post_monitor_material_info,
                )


def post_monitor_resource(data: List[dict], resource: resources.Resource):
    production_state_info = []
    for production_state in resource.production_states:
        if production_state.process:
            production_process_info = {
                "Process": production_state.state_info.ID,
                "Material": production_state.state_info._material_ID,
                "Activity": production_state.state_info._activity,
                "State": production_state.state_info._state_type,
            }
            production_state_info.append(production_process_info)
    
    input_queue_info = []
    for queue in resource.input_queues:
        for material_data in queue.items:
            # TODO: implement function to retrieve material from material factory to get next process and next resource and waiting since
            production_process_info = {
                "Material": material_data.ID,
                "Activity": "waiting",
                # "Process": material.next_process,
                # "Next_Resource": material.next_resource,
                # "waiting_since": material.material_info.event_time
            }
            input_queue_info.append(production_process_info)

    output_queue_info = []
    for queue in resource.output_queues:
        for material_data in queue.items:
            production_process_info = {
                "Material": material_data.ID,
                "Activity": "waiting",
                # "Process": material.next_process,
                # "Next_Resource": material.next_resource,
                # "waiting_since": material.material_info.event_time
            }
            output_queue_info.append(production_process_info)
    item = {
        "Time": resource.env.now,
        "Resource": resource.data.ID,
        "Available": resource.active.triggered,
        "Users": production_state_info,
        "Input Queue": input_queue_info,
        "Output Queue": output_queue_info
    }
    data.append(item)


def monitor_controller(data: List[dict], controller: control.Controller):
    resource = controller.resource
    post_monitor_resource(data, resource)

class ObservationLogger(Logger):
    resource_state_data: List[Dict[str, Union[str, int, float, Enum]]] = []
    material_state_data: List[Dict[str, Union[str, int, float, Enum]]] = []

    def get_data_as_dataframe(self) -> pd.DataFrame:
        pass

    def observe_resources(self, resource: resources.Resource):
        self.register_patch(
            self.resource_state_data,
            resource,
            ["interrupt_states", "activate", "start_states", "setup"],
            post=post_monitor_resource,
        )
        controller = resource.get_controller()
        self.register_patch(
            self.resource_state_data,
            controller,
            ["start_process"],
            post=monitor_controller,
            pre=monitor_controller
        )

    # def observe_materials(self, material_factory: material_factory.MaterialFactory):
    #     pass