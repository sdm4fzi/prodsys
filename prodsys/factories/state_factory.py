from __future__ import annotations

from dataclasses import field
from typing import List, TYPE_CHECKING, Optional, List

from pydantic import ConfigDict, BaseModel, TypeAdapter

from prodsys.simulation import sim
from prodsys.factories import time_model_factory
from prodsys.models import state_data
from prodsys.simulation import state


if TYPE_CHECKING:
    from prodsys.adapters import adapter


class StateFactory:
    """
    Factory class that creates and stores `prodsys.simulation` state objects from `prodsys.models` state objects.

    Args:
        env (sim.Environment): prodsys simulation environment.
        time_model_factory (time_model_factory.TimeModelFactory): Factory that creates time model objects.
    """

    def __init__(
        self,
        env: sim.Environment,
        time_model_factory: time_model_factory.TimeModelFactory,
    ):
        self.env = env
        self.time_model_factory = time_model_factory
        self.state_data: List[state_data.STATE_DATA_UNION] = []
        self.states: List[state.STATE_UNION] = []

    def create_states_from_configuration_data(self, configuration_data: dict):
        for cls_name, items in configuration_data.items():
            for values in items.values():
                values.update({"type": cls_name})
                self.state_data.append(
                    TypeAdapter(state_data.STATE_DATA_UNION).validate_python(values)
                )
                self.add_state(self.state_data[-1])

    def get_loading_time_models_data(
        self, transport_state: state_data.STATE_DATA_UNION
    ) -> dict:
        if not isinstance(transport_state, state_data.TransportStateData):
            return {}
        loading_time_model_dict = {}
        if transport_state.loading_time_model_id is not None:
            loading_time_model_dict[
                "loading_time_model"
            ] = self.time_model_factory.get_time_model(
                transport_state.loading_time_model_id
            )
        if transport_state.unloading_time_model_id is not None:
            loading_time_model_dict[
                "unloading_time_model"
            ] = self.time_model_factory.get_time_model(
                transport_state.unloading_time_model_id
            )
        return loading_time_model_dict

    def get_repair_time_model_data(
        self, state_data: state_data.STATE_DATA_UNION
    ) -> dict:
        repair_time_model_dict = {}
        if (
            "repair_time_model_id" in state_data.model_dump()
            and state_data.model_dump()["repair_time_model_id"] is not None
        ):
            return {
                "repair_time_model": self.time_model_factory.get_time_model(
                    state_data.repair_time_model_id
                )
            }
        return repair_time_model_dict

    def get_battery_time_model_data(
        self, state_data: state_data.STATE_DATA_UNION
    ) -> dict:
        battery_time_model_dict = {}
        if (
            "battery_time_model_id" in state_data.model_dump()
            and state_data.model_dump()["battery_time_model_id"] is not None
        ):
            return {
                "battery_time_model": self.time_model_factory.get_time_model(
                    state_data.battery_time_model_id
                )
            }
        return battery_time_model_dict

    def add_state(self, state_data: state_data.STATE_DATA_UNION):
        values = {
            "state_data": state_data,
            "time_model": self.time_model_factory.get_time_model(
                state_data.time_model_id
            ),
            "env": self.env,
        }
        values.update(self.get_loading_time_models_data(state_data))
        values.update(self.get_repair_time_model_data(state_data))
        values.update(self.get_battery_time_model_data(state_data))
        self.states.append(TypeAdapter(state.STATE_UNION).validate_python(values))

    def create_states(self, adapter: adapter.ProductionSystemAdapter):
        """
        Creates state objects based on the given adapter.

        Args:
            adapter (adapter.ProductionSystemAdapter): Adapter that contains the state data.
        """
        for state_data in adapter.state_data:
            self.add_state(state_data)

    def get_states(self, IDs: List[str]) -> List[state.STATE_UNION]:
        """
        Returns a list of state objects with the given IDs.

        Args:
            IDs (List[str]): List of IDs that is used to sort the state objects.

        Returns:
            List[state.STATE_UNION]: List of state objects with the given IDs.
        """
        return [st for st in self.states if st.state_data.ID in IDs]
