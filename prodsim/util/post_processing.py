from dataclasses import dataclass, field
from functools import cached_property

from prodsim.simulation import state
from prodsim.data_structures import performance_indicators

from typing import List

import pandas as pd

WARM_UP_CUT_OFF = 0.15


@dataclass
class PostProcessor:
    filepath: str = field(default="")
    df_raw: pd.DataFrame = field(default=None)

    def __post_init__(self):
        if self.filepath:
            self.read_df_from_csv()

    def read_df_from_csv(self, filepath_input: str = None):
        if filepath_input:
            self.filepath = filepath_input
        self.df_raw = pd.read_csv(self.filepath)
        self.df_raw.drop(columns=["Unnamed: 0"], inplace=True)

    def get_conditions_for_interface_state(self, df: pd.DataFrame) -> pd.DataFrame:
        return df["State Type"].isin(
            [state.StateTypeEnum.source, state.StateTypeEnum.sink]
        )

    def get_conditions_for_process_state(self, df: pd.DataFrame) -> pd.DataFrame:
        return df["State Type"].isin(
            [
                state.StateTypeEnum.production,
                state.StateTypeEnum.transport,
                state.StateTypeEnum.breakdown,
                state.StateTypeEnum.setup,
            ]
        )

    @cached_property
    def get_prepared_df(self) -> pd.DataFrame:
        df = self.df_raw.copy()
        df["DateTime"] = pd.to_datetime(df["Time"], unit="m")
        df["Combined_activity"] = df["State"] + " " + df["Activity"]
        df["Material_type"] = df["Material"].str.rsplit("_", n=1).str[0]
        df.loc[
            self.get_conditions_for_interface_state(df),
            "State_type",
        ] = "Interface State"
        df.loc[
            self.get_conditions_for_process_state(df),
            "State_type",
        ] = "Process State"

        df.loc[df["State"].str.contains("Breakdown"), "State_type"] = "Breakdown State"

        COLUMNS = ["State_type", "Activity", "State_sorting_Index"]
        STATE_SORTING_INDEX = {
            "0": ["Interface State", "finished material", 1],
            "1": ["Interface State", "created material", 2],
            "2": ["Process State", "end interrupt", 3],
            "3": ["Process State", "end state", 4],
            "4": ["Process State", "start state", 5],
            "5": ["Process State", "start interrupt", 6],
            "6": ["Interface State", "end state", 7],
            "7": ["Interface State", "start state", 8],
        }

        df_unique = pd.DataFrame.from_dict(
            data=STATE_SORTING_INDEX, orient="index", columns=COLUMNS
        )

        df = pd.merge(df, df_unique)
        df = df.sort_values(by=["Time", "Resource", "State_sorting_Index"])
        return df

    @cached_property
    def get_finished_material_df(self) -> pd.DataFrame:
        df = self.get_prepared_df.copy()
        finished_material = df.loc[
            (df["Material"].notna()) & (df["Activity"] == "finished material")
        ]["Material"].unique()
        finished_material = pd.Series(finished_material, name="Material")
        df_finished_material = pd.merge(df, finished_material)
        return df_finished_material

    def get_df_with_material_entries(self, input_df: pd.DataFrame) -> pd.DataFrame:
        df = input_df.copy()
        material_types = df.loc[
            (df["Material_type"].notna()) & (df["Material_type"] != "")
        ]["Material_type"].unique()
        material_types = pd.Series(material_types, name="Material_type")
        df_material_info = pd.merge(df, material_types)
        return df_material_info

    def get_eventlog_for_material(self, material_type: str = "Material_1"):
        import pm4py

        df_finished_material = self.get_finished_material_df.copy()
        df_for_pm4py = df_finished_material.loc[
            df_finished_material["Material"].notnull()
        ]
        df_for_pm4py = df_for_pm4py.rename(
            columns={"Material_type": "Material:Material_type"}
        )
        df_for_pm4py = df_for_pm4py.loc[
            df_for_pm4py["Material:Material_type"] == material_type
        ]
        df_for_pm4py = pm4py.format_dataframe(
            df_for_pm4py,
            case_id="Material",
            activity_key="Combined_activity",
            timestamp_key="DateTime",
        )
        log = pm4py.convert_to_event_log(df_for_pm4py)

        return log

    def save_inductive_petri_net(self):
        import pm4py
        from pm4py.visualization.petri_net import visualizer as pn_visualizer

        log = self.get_eventlog_for_material()
        net, initial_marking, final_marking = pm4py.discover_petri_net_inductive(log)
        # pm4py.view_petri_net(net, initial_marking, final_marking)
        parameters = {pn_visualizer.Variants.FREQUENCY.value.Parameters.FORMAT: "png"}
        gviz = pn_visualizer.apply(
            net,
            initial_marking,
            final_marking,
            parameters=parameters,
            variant=pn_visualizer.Variants.FREQUENCY,
            log=log,
        )
        pn_visualizer.save(gviz, "data/inductive_frequency.png")

    @cached_property
    def get_throughput_data_frame(self) -> pd.DataFrame:
        df = self.get_prepared_df.copy()
        df_finished_material = self.get_finished_material_df.copy()
        min = df_finished_material.groupby(by="Material")["Time"].min()
        min.name = "Start_time"
        max = df_finished_material.groupby(by="Material")["Time"].max()
        max.name = "End_time"
        tpt = max - min
        tpt.name = "Throughput_time"

        df_tpt = pd.merge(
            df[["Material_type", "Material"]].drop_duplicates(),
            tpt.to_frame().reset_index(),
        )
        df_tpt = pd.merge(df_tpt, min.to_frame().reset_index())
        df_tpt = pd.merge(df_tpt, max.to_frame().reset_index())

        return df_tpt

    @cached_property
    def get_aggregated_throughput_time_data_frame(self) -> pd.DataFrame:
        df = self.get_throughput_data_frame.copy()
        max_time = df["End_time"].max()
        df = df.loc[df["Start_time"] >= max_time * WARM_UP_CUT_OFF]
        df = df.groupby(by=["Material_type"])["Throughput_time"].mean()
        return df
    
    @cached_property
    def get_aggregated_throughput_time_KPIs(self) -> List[performance_indicators.KPI]:
        ser = self.get_aggregated_throughput_time_data_frame.copy()
        KPIs = []
        context = (performance_indicators.KPILevelEnum.SYSTEM,
            performance_indicators.KPILevelEnum.MATERIAL_TYPE,)
        for index, value in ser.items():
            KPIs.append(
                performance_indicators.ThroughputTime(
                    name=performance_indicators.KPIEnum.TRHOUGHPUT_TIME,
                    value=value,
                    context=context,
                    material_type=index,
                )
            )
        return KPIs

    @cached_property
    def get_aggregated_output_and_throughput_data_frame(self) -> pd.DataFrame:
        df = self.get_throughput_data_frame.copy()
        max_time = df["End_time"].max()
        df = df.loc[df["Start_time"] >= max_time * WARM_UP_CUT_OFF]
        df_tp = df.groupby(by="Material_type")["Material"].count().to_frame()
        df_tp.rename(columns={"Material": "Output"}, inplace=True)
        available_time = max_time * (1 - WARM_UP_CUT_OFF) / 60
        df_tp["Throughput"] = df_tp["Output"] / available_time

        return df_tp
    
    @cached_property
    def get_throughput_and_output_KPIs(self) -> List[performance_indicators.KPI]:
        df = self.get_aggregated_output_and_throughput_data_frame.copy()
        KPIs = []
        context = (performance_indicators.KPILevelEnum.SYSTEM,
            performance_indicators.KPILevelEnum.MATERIAL_TYPE,)
        for index, values in df.iterrows():
            KPIs.append(
                performance_indicators.Throughput(
                    name=performance_indicators.KPIEnum.THROUGHPUT,
                    value=values["Throughput"],
                    context=context,
                    material_type=index,
                )
            )
            KPIs.append(
                performance_indicators.Output(
                    name=performance_indicators.KPIEnum.OUTPUT,
                    value=values["Output"],
                    context=context,
                    material_type=index,
                )
            )
        return KPIs

    @cached_property
    def get_aggregated_output_data_frame(self) -> pd.DataFrame:
        df = self.get_throughput_data_frame.copy()
        max_time = df["End_time"].max()
        df = df.loc[df["Start_time"] >= max_time * WARM_UP_CUT_OFF]
        df_tp = df.groupby(by="Material_type")["Material"].count()

        return df_tp

    @cached_property
    def get_df_with_machine_states(self) -> pd.DataFrame:
        df = self.get_prepared_df.copy()
        positive_condition = (
            (df["State_type"] == "Process State")
            & (df["Activity"] == "start state")
            & (df["State Type"] != state.StateTypeEnum.setup)
        )
        negative_condition = (
            (df["State_type"] == "Process State")
            & (df["Activity"] == "end state")
            & (df["State Type"] != state.StateTypeEnum.setup)
        )

        df["Increment"] = 0
        df.loc[positive_condition, "Increment"] = 1
        df.loc[negative_condition, "Increment"] = -1

        df["Used_Capacity"] = df.groupby(by="Resource")["Increment"].cumsum()

        for resource in df["Resource"].unique():
            if "source" in resource or "sink" in resource:
                continue
            example_row = (
                df.loc[
                    (df["Resource"] == resource)
                    & (
                        ((df["State_sorting_Index"] == 4) & (df["Used_Capacity"] == 0))
                        | (df["State_sorting_Index"] == 7)
                    )
                ]
                .copy()
                .head(1)
            )
            example_row["Time"] = 0.0
            df = pd.concat([example_row, df]).reset_index(drop=True)

        df["next_Time"] = df.groupby("Resource")["Time"].shift(-1)
        df["next_Time"].fillna(df["Time"].max(), inplace=True)
        df["time_increment"] = df["next_Time"] - df["Time"]

        df.to_csv("test.csv")

        STANDBY_CONDITION = (
            (df["State_sorting_Index"] == 4) & (df["Used_Capacity"] == 0)
        ) | (df["State_sorting_Index"] == 7)
        PRODUCTIVE_CONDITION = (
            (df["State_sorting_Index"] == 5)
            | (df["State_sorting_Index"] == 3)
            | ((df["State_sorting_Index"] == 4) & df["Used_Capacity"] != 0)
        )
        DOWN_CONDITION = (df["State_sorting_Index"] == 6) | (
            df["State_sorting_Index"] == 8
        )
        SETUP_CONDITION = ((df["State_sorting_Index"] == 5)) & (
            df["State Type"] == state.StateTypeEnum.setup
        )

        df.loc[STANDBY_CONDITION, "Time_type"] = "SB"
        df.loc[PRODUCTIVE_CONDITION, "Time_type"] = "PR"
        df.loc[DOWN_CONDITION, "Time_type"] = "UD"
        df.loc[SETUP_CONDITION, "Time_type"] = "ST"

        return df

    @cached_property
    def get_time_per_state_of_resources(self) -> pd.DataFrame:
        df = self.get_df_with_machine_states.copy()

        df_time_per_state = df.groupby(["Resource", "Time_type"])[
            "time_increment"
        ].sum()
        df_time_per_state = df_time_per_state.to_frame().reset_index()

        df_resource_time = (
            df_time_per_state.groupby(by="Resource")
            .sum(numeric_only=True)
            .reset_index()
        )
        df_resource_time.rename(
            columns={"time_increment": "resource_time"}, inplace=True
        )
        df_time_per_state = pd.merge(df_time_per_state, df_resource_time)
        df_time_per_state["percentage"] = (
            df_time_per_state["time_increment"] / df_time_per_state["resource_time"]
        )

        return df_time_per_state
    
    @cached_property
    def get_machine_state_KPIS(self) -> List[performance_indicators.KPI]:
        df = self.get_time_per_state_of_resources.copy()
        KPIs = []
        context = (performance_indicators.KPILevelEnum.RESOURCE, )
        class_dict = {
            "SB": (performance_indicators.StandbyTime, performance_indicators.KPIEnum.STANDBY_TIME),
            "PR": (performance_indicators.ProductiveTime, performance_indicators.KPIEnum.PRODUCTIVE_TIME),	
            "UD": (performance_indicators.UnscheduledDowntime, performance_indicators.KPIEnum.UNSCHEDULED_DOWNTIME),
            "ST": (performance_indicators.SetupTime, performance_indicators.KPIEnum.SETUP_TIME),
        }
        for index, values in df.iterrows():
            KPIs.append(
                class_dict[values["Time_type"]][0](
                    name=class_dict[values["Time_type"]][1],
                    value=values["percentage"],
                    context=context,
                    resource=values["Resource"],
                )
            )
        return KPIs

    def get_WIP_KPI(self, df) -> pd.DataFrame:
        CREATED_CONDITION = df["Activity"] == "created material"
        FINISHED_CONDITION = df["Activity"] == "finished material"

        df["WIP_Increment"] = 0
        df.loc[CREATED_CONDITION, "WIP_Increment"] = 1
        df.loc[FINISHED_CONDITION, "WIP_Increment"] = -1

        df["WIP"] = df["WIP_Increment"].cumsum()

        return df

    @cached_property
    def get_df_with_WIP(self) -> pd.DataFrame:
        df = self.get_df_with_machine_states.copy()
        return self.get_WIP_KPI(df)

    @cached_property
    def get_df_with_WIP_per_product(self) -> pd.DataFrame:
        df = self.get_df_with_machine_states.copy()
        df = self.get_df_with_material_entries(df).copy()
        df = df.reset_index()
        for material_type in df["Material_type"].unique():
            if material_type != material_type:
                continue
            df_temp = df.loc[df["Material_type"] == material_type].copy()
            df_temp = self.get_WIP_KPI(df_temp)

            df = df.combine_first(df_temp)

        return df

    @cached_property
    def get_df_with_aggregated_WIP(self) -> pd.Series:
        df = self.get_df_with_WIP_per_product.copy()
        df_total_wip = self.get_df_with_WIP.copy()
        df_total_wip["Material_type"] = "Total"
        df = pd.concat([df, df_total_wip])

        max_time = df["Time"].max()

        df = df[df["Time"] >= max_time * WARM_UP_CUT_OFF]
        group = ["Material_type"]

        df = df.groupby(by=group)["WIP"].mean()

        return df

    @cached_property
    def System_WIP_total_and_per_product(self) -> List[performance_indicators.WIP]:
        ser = self.get_df_with_aggregated_WIP.copy()
        KPIs = []
        for index, value in ser.items():
            if index == "Total":
                context = (performance_indicators.KPILevelEnum.SYSTEM,
                           performance_indicators.KPILevelEnum.ALL_MATERIALS)
                index = performance_indicators.KPILevelEnum.ALL_MATERIALS
            else:
                context = (
                    performance_indicators.KPILevelEnum.SYSTEM,
                    performance_indicators.KPILevelEnum.MATERIAL_TYPE,
                )
            KPIs.append(
                performance_indicators.WIP(
                    name=performance_indicators.KPIEnum.WIP,
                    value=value,
                    context=context,
                    material_type=index,
                )
            )
        return KPIs

    def get_aggregated_data(self) -> dict:
        data = {}
        data["Throughput"] = (
            self.get_aggregated_output_and_throughput_data_frame.copy()
            .reset_index()
            .to_dict()
        )
        data["WIP"] = self.get_df_with_aggregated_WIP.copy().reset_index().to_dict()
        data["Throughput time"] = (
            self.get_aggregated_throughput_time_data_frame.copy()
            .reset_index()
            .to_dict()
        )
        data["Resource states"] = (
            self.get_time_per_state_of_resources.copy()
            .set_index(["Resource", "Time_type"])
            .reset_index()
            .to_dict()
        )

        return data

    def get_aggregated_throughput_time_data(self) -> List[float]:
        return list(self.get_aggregated_throughput_time_data_frame.values)

    def get_aggregated_throughput_data(self) -> List[float]:
        return list(self.get_aggregated_output_data_frame.values)

    def get_aggregated_wip_data(self) -> List[float]:
        s = self.get_df_with_aggregated_WIP.copy()
        s = s.drop(labels=["Total"])
        return list(s.values)
