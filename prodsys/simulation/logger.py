from __future__ import annotations

import functools
import warnings
from enum import Enum
from abc import ABC, abstractmethod

warnings.simplefilter(action="ignore", category=RuntimeWarning)
from functools import partial, wraps
from typing import Callable, List, Union, TYPE_CHECKING, Dict, Any, Optional

import pandas as pd
from pydantic import BaseModel

from prodsys.simulation import state


if TYPE_CHECKING:
    from prodsys.simulation import product, auxiliary
    from prodsys.factories import resource_factory


class Logger(BaseModel, ABC):
    """
    Base class for all loggers.
    """

    @abstractmethod
    def get_data_as_dataframe(self) -> pd.DataFrame:
        """
        Abstract method for returning the data as a pandas DataFrame.

        Returns:
            pd.DataFrame: The data as a pandas DataFrame.
        """
        pass

    def patch_state(
        self,
        object: Any,
        attr: List[str],
        pre: Optional[functools.partial] = None,
        post: Optional[functools.partial] = None,
    ):
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
        """
        Register a patch for the object.

        Args:
            data (Any): Data to log to used for preloading the pre and post functions.
            object (Any): The object to patch.
            attr (List[str]): The attributes of the object to patch.
            pre (Optional[Callable], optional): The function to call before each operation. Defaults to None.
            post (Optional[Callable], optional): The function to call after each operation. Defaults to None.
        """
        if pre is not None:
            pre = partial(pre, data)
        if post is not None:
            post = partial(post, data)
        self.patch_state(object, attr, pre, post)

    def log_data_to_csv(self, filepath: str):
        """
        Log the data to a csv file.

        Args:
            filepath (str): The path to the csv file.
        """
        df = self.get_data_as_dataframe()
        df.to_csv(filepath)

    def log_data_to_json(self, filepath: str):
        """
        Log the data to a json file.

        Args:
            filepath (str): The path to the json file.
        """
        df = self.get_data_as_dataframe()
        df.to_json(filepath)


def post_monitor_resource_states(data: List[dict], state_info: state.StateInfo):
    """
    Post function for monitoring resource states. With this post monitor, every state change is logged.

    Args:
        data (List[dict]): The data to log to.
        state_info (state.StateInfo): The state info object.
    """
    item = {
        "Time": state_info._event_time,
        "Resource": state_info.resource_ID,
        "State": state_info.ID,
        "State Type": state_info._state_type,
        "Activity": state_info._activity,
        "Expected End Time": state_info._expected_end_time,
        "Product": state_info._product_ID,
        "Origin location": state_info._origin_ID,
        "Target location": state_info._target_ID,
        "Empty Transport": state_info._empty_transport,
    }
    data.append(item)


def post_monitor_product_info(data: List[dict], product_info: product.ProductInfo):
    """
    Post function for monitoring product info. With this post monitor, every product creation and finish is logged.

    Args:
        data (List[dict]): The data to log to.
        product_info (product.ProductInfo): The product info object.
    """

    item = {
        "Time": product_info.event_time,
        "Resource": product_info.resource_ID,
        "State": product_info.state_ID,
        "State Type": product_info.state_type,
        "Activity": product_info.activity,
        "Product": product_info.product_ID,
    }
    data.append(item)


def post_monitor_auxiliary_info(
    data: List[dict], auxiliary_info: auxiliary.AuxiliaryInfo
):
    """
    Post function for monitoring auxiliary info. With this post monitor, every auxiliary creation and finish is logged.

    Args:
        data (List[dict]): The data to log to.
        product_info (product.ProductInfo): The product info object.
    """

    item = {
        "Time": auxiliary_info.event_time,
        "Resource": auxiliary_info.resource_ID,
        "State": auxiliary_info.state_ID,
        "State Type": auxiliary_info.state_type,
        "Activity": auxiliary_info.activity,
        "Product": auxiliary_info.product_ID,
    }
    data.append(item)


class EventLogger(Logger):
    """
    Logger for logging events.
    """

    event_data: List[Dict[str, Union[str, int, float, Enum]]] = []

    def get_data_as_dataframe(self) -> pd.DataFrame:
        """
        Get the data as a pandas DataFrame.

        Returns:
            pd.DataFrame: The data as a pandas DataFrame.
        """
        df = pd.DataFrame(self.event_data)
        df["Activity"] = pd.Categorical(
            df["Activity"],
            categories=[v.value for v in list(state.StateEnum)],
            ordered=True,
        )
        df["Activity"] = df["Activity"].astype("string")
        return df

    def observe_resource_states(
        self, resource_factory: resource_factory.ResourceFactory
    ):
        """
        Create patch to observe the resource states.

        Args:
            resource_factory (resource_factory.ResourceFactory): The resource factory.
        """
        for r in resource_factory.resources:
            all_states = (
                r.states + r.production_states + r.setup_states + r.charging_states
            )
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
        """
        Create path to observe the terminal product states.

        Args:
            product (product.Product): The product.
        """
        self.register_patch(
            self.event_data,
            product.product_info,
            attr=["log_create_product", "log_finish_product"],
            post=post_monitor_product_info,
        )

    def observe_terminal_auxiliary_states(self, auxiliary: auxiliary.Auxiliary):
        """
        Create path to observe the terminal auxiliary states.

        Args:
            auxiliary (auxiliary.Auxiliary): The auxiliary.
        """
        self.register_patch(
            self.event_data,
            auxiliary.auxiliary_info,
            attr=[
                "log_create_auxiliary",
                "log_start_auxiliary_usage",
                "log_end_auxiliary_usage",
            ],
            post=post_monitor_auxiliary_info,
        )
