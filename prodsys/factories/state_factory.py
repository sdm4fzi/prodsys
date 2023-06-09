from __future__ import annotations

from dataclasses import field
from typing import List, TYPE_CHECKING

from pydantic import parse_obj_as, BaseModel

from prodsys.simulation import sim
from prodsys.factories import time_model_factory
from prodsys.models import state_data
from prodsys.simulation import state


if TYPE_CHECKING:
    from prodsys.adapters import adapter


class StateFactory(BaseModel):
    """
    Factory class that creates and stores `prodsys.simulation` state objects from `prodsys.models` state objects.

    Args:
        env (sim.Environment): prodsys simulation environment.
        time_model_factory (time_model_factory.TimeModelFactory): Factory that creates time model objects.
    """
    env: sim.Environment
    time_model_factory: time_model_factory.TimeModelFactory

    state_data: List[state_data.STATE_DATA_UNION] = []
    states: List[state.STATE_UNION] = []

    class Config:
        arbitrary_types_allowed = True

    def create_states_from_configuration_data(self, configuration_data: dict):
        for cls_name, items in configuration_data.items():
            for values in items.values():
                values.update({"type": cls_name})
                self.state_data.append(
                    parse_obj_as(state_data.STATE_DATA_UNION, values)
                )
                self.add_state(self.state_data[-1])

    def add_state(self, state_data: state_data.STATE_DATA_UNION):
        values = {}
        values.update({"state_data": state_data})
        time_model = self.time_model_factory.get_time_model(
            values["state_data"].time_model_id
        )
        values.update({"time_model": time_model, "env": self.env})
        if "repair_time_model_id" in state_data.dict():
            repair_time_model = self.time_model_factory.get_time_model(
                state_data.repair_time_model_id
            )
            values.update({"repair_time_model": repair_time_model})
        self.states.append(parse_obj_as(state.STATE_UNION, values))

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
