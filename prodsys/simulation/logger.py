from __future__ import annotations

import functools
import warnings
from enum import Enum
from abc import ABC, abstractmethod
warnings.simplefilter(action = "ignore", category = RuntimeWarning)
from functools import partial, wraps
from typing import Callable, List, Union, TYPE_CHECKING, Dict, Any, Optional

import pandas as pd
from pydantic import BaseModel

from prodsys.simulation import state


if TYPE_CHECKING:
    from prodsys.simulation import product
    from prodsys.factories import resource_factory


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
        "Product": state_info._product_ID,
        "Target location": state_info._target_ID,
    }
    data.append(item)


def post_monitor_product_info(data: List[dict], product_info: product.ProductInfo):

    item = {
        "Time": product_info.event_time,
        "Resource": product_info.resource_ID,
        "State": product_info.state_ID,
        "State Type": product_info.state_type,
        "Activity": product_info.activity,
        "Product": product_info.product_ID,
    }
    data.append(item)

class EventLogger(Logger):
    event_data: List[Dict[str, Union[str, int, float, Enum]]] = []


    def get_data_as_dataframe(self) -> pd.DataFrame:
        df = pd.DataFrame(self.event_data)
        df["Activity"] = pd.Categorical(
            df["Activity"],
            categories=[
                v.value for v in list(state.StateEnum)
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

    def observe_terminal_product_states(self, product: product.Product):
        self.register_patch(
                    self.event_data,
                    product.product_info,
                    attr=["log_create_product", "log_finish_product"],
                    post=post_monitor_product_info,
                )
