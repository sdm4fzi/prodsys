from typing import Dict, List, TYPE_CHECKING, List

from pydantic import TypeAdapter

from prodsys.simulation import sim
from prodsys.factories import time_model_factory
from prodsys.models import state_data
from prodsys.simulation import state


if TYPE_CHECKING:
    from prodsys.models import production_system_data


STATE_MAP = {
    state_data.StateTypeEnum.SetupState: state.SetupState,
    state_data.StateTypeEnum.BreakDownState: state.BreakDownState,
    state_data.StateTypeEnum.TransportState: state.TransportState,
    state_data.StateTypeEnum.ProductionState: state.ProductionState,
    state_data.StateTypeEnum.ProcessBreakDownState: state.ProcessBreakDownState,
    state_data.StateTypeEnum.ChargingState: state.ChargingState,
    state_data.StateTypeEnum.NonScheduled: state.NonScheduledState,
}


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
        self.states: Dict[str, state.STATE_UNION] = {}

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
            loading_time_model_dict["loading_time_model"] = (
                self.time_model_factory.get_time_model(
                    transport_state.loading_time_model_id
                )
            )
        if transport_state.unloading_time_model_id is not None:
            loading_time_model_dict["unloading_time_model"] = (
                self.time_model_factory.get_time_model(
                    transport_state.unloading_time_model_id
                )
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

    def get_non_scheduled_time_model_data(
        self, state_data: state_data.STATE_DATA_UNION
    ) -> dict:
        non_scheduled_time_model_dict = {}
        if (
            "non_scheduled_time_model_id" in state_data.model_dump()
            and state_data.model_dump()["non_scheduled_time_model_id"] is not None
        ):
            return {
                "non_scheduled_time_model": self.time_model_factory.get_time_model(
                    state_data.non_scheduled_time_model_id
                )
            }
        return non_scheduled_time_model_dict

    def add_state(self, state_data: state_data.STATE_DATA_UNION):
        values = {
            "data": state_data,
            "time_model": self.time_model_factory.get_time_model(
                state_data.time_model_id
            ),
            "env": self.env,
        }
        values.update(self.get_loading_time_models_data(state_data))
        values.update(self.get_repair_time_model_data(state_data))
        values.update(self.get_battery_time_model_data(state_data))
        values.update(self.get_non_scheduled_time_model_data(state_data))

        state_class = STATE_MAP.get(state_data.type)
        if state_class is None:
            raise ValueError(f"Unknown state type: {state_data.type}")
        new_state = state_class(**values)
        self.states[state_data.ID] = new_state

    def create_states(self, adapter: "production_system_data.ProductionSystemData"):
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
        return [self.states[ID] for ID in IDs if ID in self.states]
