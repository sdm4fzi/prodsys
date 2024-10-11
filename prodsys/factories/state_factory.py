from __future__ import annotations

from dataclasses import field
from typing import List, TYPE_CHECKING

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

    def __init__(self, env: sim.Environment, time_model_factory: time_model_factory.TimeModelFactory):
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

    def add_state(self, state_data: state_data.STATE_DATA_UNION):
        values = {}
        values.update({"state_data": state_data})
        time_model = self.time_model_factory.get_time_model(
            values["state_data"].time_model_id
        )
        values.update({"time_model": time_model, "env": self.env})
        if "repair_time_model_id" in state_data.model_dump():
            repair_time_model = self.time_model_factory.get_time_model(
                state_data.repair_time_model_id
            )
            values.update({"repair_time_model": repair_time_model})
        if "battery_time_model_id" in state_data.model_dump():
            battery_time_model = self.time_model_factory.get_time_model(
                state_data.battery_time_model_id
            )
            values.update({"battery_time_model": battery_time_model})
        # FIXME: resolve bug when importing simulation types#
        print(values)
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
