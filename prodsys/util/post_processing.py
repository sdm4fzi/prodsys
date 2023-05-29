from dataclasses import dataclass, field
from functools import cached_property

from prodsys.simulation import state
from prodsys.models import performance_indicators

from typing import List

import pandas as pd

WARM_UP_CUT_OFF = 0.15


@dataclass
class PostProcessor:
    """
    Class that represents a post processor for the simulation results. It provides methods to read the simulation results from a csv file and to calculate simulation result analysis data and KPIs.

    The data frame that contains the raw simulation results contains the following columns:
        
        -Time: Time of the event
        -Resource: ID fo the Resource that performed the event
        -State: ID of the State of the resource (production states, transport states, breakdown states, setup states)
        -State Type: Type of the state according to the prodsys.simulation.state.StateTypeEnum
        -Activity: Activity of the resource according to the prodsys.simulation.state.StateEnum
        -Product: ID of the Product that is processed by the resource only for creation and production states
        -Expected End Time: Expected end time of the state at the beginning of the process
        -Target location: Target location of the product at the end of the process

    Args:
        filepath (str): Path to the csv file with the simulation results.
        df_raw (pd.DataFrame): Data frame with the simulation results.
    """
    filepath: str = field(default="")
    df_raw: pd.DataFrame = field(default=None)

    def __post_init__(self):
        if self.filepath:
            self.read_df_from_csv()

    def read_df_from_csv(self, filepath_input: str = None):
        """
        Reads the simulation results from a csv file.

        Args:
            filepath_input (str, optional): Path to the csv file with the simulation results. Defaults to None and the at instantiation provided filepath is used.
        """
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
    def df_prepared(self) -> pd.DataFrame:
        """
        Adds to self.df_raw the following columns:
            
            -DateTime: Time of the event
            -Combined_activity: Activity and state of the event combined for easier filtering
            -Product_type: Type of the product
            -State_type: Type of the state according to the StateTypeEnum
            -State_sorting_Index: Index to sort the states in the correct order
            
        Returns:
            pd.DataFrame: Data frame with the simulation results and the added columns.
        """
        df = self.df_raw.copy()
        df["DateTime"] = pd.to_datetime(df["Time"], unit="m")
        df["Combined_activity"] = df["State"] + " " + df["Activity"]
        df["Product_type"] = df["Product"].str.rsplit("_", n=1).str[0]
        df.loc[
            self.get_conditions_for_interface_state(df),
            "State_type",
        ] = "Interface State"
        df.loc[
            self.get_conditions_for_process_state(df),
            "State_type",
        ] = "Process State"

        df.loc[df["State"].str.contains("Breakdown"), "State_type"] = "Breakdown State"
        df = df.loc[df["State_type"] != "ProcessBreakdown"]

        COLUMNS = ["State_type", "Activity", "State_sorting_Index"]
        STATE_SORTING_INDEX = {
            "0": ["Interface State", "finished product", 1],
            "1": ["Interface State", "created product", 2],
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
    def df_finished_product(self) -> pd.DataFrame:
        """
        Returns a prepared data frame (df_prepared) with only finished products.

        Returns:
            pd.DataFrame: Data frame with only finished products.
        """
        df = self.df_prepared.copy()
        finished_product = df.loc[
            (df["Product"].notna()) & (df["Activity"] == "finished product")
        ]["Product"].unique()
        finished_product = pd.Series(finished_product, name="Product")
        df_finished_product = pd.merge(df, finished_product)
        return df_finished_product

    def get_df_with_product_entries(self, input_df: pd.DataFrame) -> pd.DataFrame:
        df = input_df.copy()
        product_types = df.loc[
            (df["Product_type"].notna()) & (df["Product_type"] != "")
        ]["Product_type"].unique()
        product_types = pd.Series(product_types, name="Product_type")
        df_product_info = pd.merge(df, product_types)
        return df_product_info

    def get_eventlog_for_product(self, product_type: str = "Product_1"):
        """
        Returns an event log for a specific product type. It can be further anaylzed with the pm4py library.

        Args:
            product_type (str, optional): Type of product that should be considered in the event log. Defaults to "Product_1".

        Returns:
            pm4py.event_log.EventLog: Event log for a specific product type.

        """
        import pm4py

        df_finished_product = self.df_finished_product.copy()
        df_for_pm4py = df_finished_product.loc[
            df_finished_product["Product"].notnull()
        ]
        df_for_pm4py = df_for_pm4py.rename(
            columns={"Product_type": "Product:Product_type"}
        )
        df_for_pm4py = df_for_pm4py.loc[
            df_for_pm4py["Product:Product_type"] == product_type
        ]
        df_for_pm4py = pm4py.format_dataframe(
            df_for_pm4py,
            case_id="Product",
            activity_key="Combined_activity",
            timestamp_key="DateTime",
        )
        log = pm4py.convert_to_event_log(df_for_pm4py)

        return log

    def save_inductive_petri_net(self):
        """
        Saves an inductive petri net for a specific product type, that shows the process model realized in the simulation for finishing the product.
        """
        import pm4py
        from pm4py.visualization.petri_net import visualizer as pn_visualizer

        log = self.get_eventlog_for_product()
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
    def df_throughput(self) -> pd.DataFrame:
        """
        Returns a data frame with the throughput time for each finished product.

        Returns:
            pd.DataFrame: Data frame with the throughput time for each finished product.
        """
        df = self.df_prepared.copy()
        df_finished_product = self.df_finished_product.copy()
        min = df_finished_product.groupby(by="Product")["Time"].min()
        min.name = "Start_time"
        max = df_finished_product.groupby(by="Product")["Time"].max()
        max.name = "End_time"
        tpt = max - min
        tpt.name = "Throughput_time"

        df_tpt = pd.merge(
            df[["Product_type", "Product"]].drop_duplicates(),
            tpt.to_frame().reset_index(),
        )
        df_tpt = pd.merge(df_tpt, min.to_frame().reset_index())
        df_tpt = pd.merge(df_tpt, max.to_frame().reset_index())

        return df_tpt
    
    @cached_property
    def dynamic_thoughput_time_KPIs(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of Dynamic Throughput KPI values for the throughput time of each finished product.

        Returns:
            List[performance_indicators.KPI]: List of Dynamic Throughput KPI values.
        """
        df_tp = self.df_throughput.copy()
        KPIs = []
        context = (performance_indicators.KPILevelEnum.SYSTEM,
            performance_indicators.KPILevelEnum.PRODUCT,)
        for index, values in df_tp.iterrows():
            KPIs.append(
                performance_indicators.DynamicThroughputTime(
                    name=performance_indicators.KPIEnum.DYNAMIC_THROUGHPUT_TIME,
                    context=context,
                    value=values["Throughput_time"],
                    product=index,
                    product_type=values["Product_type"],
                    start_time=values["Start_time"],
                    end_time=values["End_time"],
                )
            )
        return KPIs

    @cached_property
    def df_aggregated_throughput_time(self) -> pd.DataFrame:
        """
        Returns a data frame with the average throughput time for each product type.

        Returns:
            pd.DataFrame: Data frame with the average throughput time for each product type.
        """
        df = self.df_throughput.copy()
        max_time = df["End_time"].max()
        df = df.loc[df["Start_time"] >= max_time * WARM_UP_CUT_OFF]
        df = df.groupby(by=["Product_type"])["Throughput_time"].mean()
        return df
    
    @cached_property
    def aggregated_throughput_time_KPIs(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of average Throughput Time KPI values for each product type.

        Returns:
            List[performance_indicators.KPI]: List of average Throughput Time KPI values.
        """
        ser = self.df_aggregated_throughput_time.copy()
        KPIs = []
        context = (performance_indicators.KPILevelEnum.SYSTEM,
            performance_indicators.KPILevelEnum.PRODUCT_TYPE,)
        for index, value in ser.items():
            KPIs.append(
                performance_indicators.ThroughputTime(
                    name=performance_indicators.KPIEnum.TRHOUGHPUT_TIME,
                    value=value,
                    context=context,
                    product_type=index,
                )
            )
        return KPIs

    @cached_property
    def df_aggregated_output_and_throughput(self) -> pd.DataFrame:
        """
        Returns a data frame with the average throughput and output for each product type.

        Returns:
            pd.DataFrame: Data frame with the average throughput and output for each product type.
        """
        df = self.df_throughput.copy()
        max_time = df["End_time"].max()
        df = df.loc[df["Start_time"] >= max_time * WARM_UP_CUT_OFF]
        df_tp = df.groupby(by="Product_type")["Product"].count().to_frame()
        df_tp.rename(columns={"Product": "Output"}, inplace=True)
        available_time = max_time * (1 - WARM_UP_CUT_OFF) / 60
        df_tp["Throughput"] = df_tp["Output"] / available_time

        return df_tp
    
    @cached_property
    def throughput_and_output_KPIs(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of average Throughput and Output KPI values for each product type.

        Returns:
            List[performance_indicators.KPI]: List of average Throughput and Output KPI values.
        """
        df = self.df_aggregated_output_and_throughput.copy()
        KPIs = []
        context = (performance_indicators.KPILevelEnum.SYSTEM,
            performance_indicators.KPILevelEnum.PRODUCT_TYPE,)
        for index, values in df.iterrows():
            KPIs.append(
                performance_indicators.Throughput(
                    name=performance_indicators.KPIEnum.THROUGHPUT,
                    value=values["Throughput"],
                    context=context,
                    product_type=index,
                )
            )
            KPIs.append(
                performance_indicators.Output(
                    name=performance_indicators.KPIEnum.OUTPUT,
                    value=values["Output"],
                    context=context,
                    product_type=index,
                )
            )
        return KPIs

    @cached_property
    def df_aggregated_output(self) -> pd.DataFrame:
        """
        Returns a data frame with the total output for each product type.

        Returns:
            pd.DataFrame: Data frame with the total output for each product type.
        """
        df = self.df_throughput.copy()
        max_time = df["End_time"].max()
        df = df.loc[df["Start_time"] >= max_time * WARM_UP_CUT_OFF]
        df_tp = df.groupby(by="Product_type")["Product"].count()

        return df_tp

    @cached_property
    def df_resource_states(self) -> pd.DataFrame:
        """
        Returns a data frame with the machine states and the time spent in each state. 
        There are 4 different states a resource can spend its time: 
            -SB: A resource is in standby state, could process but no product is available
            -PR: A resource is in productive state and performs a process
            -UD: A resource is in unscheduled downtime state due to a breakdown
            -ST: A resource is in setup state

        Returns:
            pd.DataFrame: Data frame with the machine states and the time spent in each state.
        """
        df = self.df_prepared.copy()
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
    def df_aggregated_resource_states(self) -> pd.DataFrame:
        """
        Returns a data frame with the total time spent in each state of each resource. 

        There are 4 different states a resource can spend its time:
            -SB: A resource is in standby state, could process but no product is available
            -PR: A resource is in productive state and performs a process
            -UD: A resource is in unscheduled downtime state due to a breakdown
            -ST: A resource is in setup state

        Returns:
            pd.DataFrame: Data frame with the total time spent in each state of each resource.
        """
        df = self.df_resource_states.copy()

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
    def machine_state_KPIS(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of KPI values for the time spent in each state of each resource.

        Returns:
            List[performance_indicators.KPI]: List of KPI values for the time spent in each state of each resource.
        """
        df = self.df_aggregated_resource_states.copy()
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
        CREATED_CONDITION = df["Activity"] == "created product"
        FINISHED_CONDITION = df["Activity"] == "finished product"

        df["WIP_Increment"] = 0
        df.loc[CREATED_CONDITION, "WIP_Increment"] = 1
        df.loc[FINISHED_CONDITION, "WIP_Increment"] = -1

        df["WIP"] = df["WIP_Increment"].cumsum()

        return df

    @cached_property
    def df_WIP(self) -> pd.DataFrame:
        """
        Returns a data frame with the WIP over time in the total production system.

        Returns:
            pd.DataFrame: Data frame with the WIP over time in the total production system.
        """
        df = self.df_resource_states.copy()
        return self.get_WIP_KPI(df)

    @cached_property
    def df_WIP_per_product(self) -> pd.DataFrame:
        """
        Returns a data frame with the WIP over time for each product type.

        Returns:
            pd.DataFrame: Data frame with the WIP over time for each product type.
        """
        df = self.df_resource_states.copy()
        df = self.get_df_with_product_entries(df).copy()
        df = df.reset_index()
        for product_type in df["Product_type"].unique():
            if product_type != product_type:
                continue
            df_temp = df.loc[df["Product_type"] == product_type].copy()
            df_temp = self.get_WIP_KPI(df_temp)

            df = df.combine_first(df_temp)

        return df
    
    @cached_property
    def dynamic_WIP_KPIs(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of Dynamic WIP KPI values for the WIP over time for each product type and the whole system.

        Returns:
            List[performance_indicators.KPI]: List of Dynamic WIP KPI values.
        """
        df = self.df_WIP.copy()
        df["Product_type"] = "Total"
        df_per_product = self.df_WIP_per_product.copy()
        df = pd.concat([df, df_per_product])
        df = df.loc[df["WIP_Increment"] != 0]

        KPIs = []
        df["next_Time"] = df["Time"].groupby(by="Product_type").shift(-1)
        df["next_Time"] = df["next_Time"].fillna(df["Time"])
        for index, row in df.iterrows():
            if row["Product_type"] == "Total":
                context = (performance_indicators.KPILevelEnum.SYSTEM,
                           performance_indicators.KPILevelEnum.ALL_PRODUCTS)
            else:
                context = (
                    performance_indicators.KPILevelEnum.SYSTEM,
                    performance_indicators.KPILevelEnum.PRODUCT_TYPE,
                )
            KPIs.append(
                performance_indicators.DynamicWIP(
                    name=performance_indicators.KPIEnum.DYNAMIC_WIP,
                    value=row["WIP"],
                    context=context,
                    product_type=row["Product_type"],
                    start_time=row["Time"],
                    end_time=row["next_Time"],
                )
            )
        return KPIs       


    @cached_property
    def df_aggregated_WIP(self) -> pd.DataFrame:
        """
        Returns a data frame with the average WIP for each product type and the whole system.

        Returns:
            pd.DataFrame: Dataframe with the average WIP for each product type and the whole system.
        """
        df = self.df_WIP_per_product.copy()
        df_total_wip = self.df_WIP.copy()
        df_total_wip["Product_type"] = "Total"
        df = pd.concat([df, df_total_wip])

        max_time = df["Time"].max()

        df = df[df["Time"] >= max_time * WARM_UP_CUT_OFF]
        group = ["Product_type"]

        df = df.groupby(by=group)["WIP"].mean()

        return df

    @cached_property
    def WIP_KPIs(self) -> List[performance_indicators.KPI]:
        """
        Returns a list of average WIP KPI values for each product type and the whole system.

        Returns:
            List[performance_indicators.KPI]: List of average WIP KPI values.
        """
        ser = self.df_aggregated_WIP.copy()
        KPIs = []
        for index, value in ser.items():
            if index == "Total":
                context = (performance_indicators.KPILevelEnum.SYSTEM,
                           performance_indicators.KPILevelEnum.ALL_PRODUCTS)
                index = performance_indicators.KPILevelEnum.ALL_PRODUCTS
            else:
                context = (
                    performance_indicators.KPILevelEnum.SYSTEM,
                    performance_indicators.KPILevelEnum.PRODUCT_TYPE,
                )
            KPIs.append(
                performance_indicators.WIP(
                    name=performance_indicators.KPIEnum.WIP,
                    value=value,
                    context=context,
                    product_type=index,
                )
            )
        return KPIs

    def get_aggregated_data(self) -> dict:
        """
        Returns a dictionary with the aggregated data for the simulation results.

        Returns:
            dict: Dictionary with the aggregated data for throughput, wip, throughput time and resource states.
        """
        data = {}
        data["Throughput"] = (
            self.df_aggregated_output_and_throughput.copy()
            .reset_index()
            .to_dict()
        )
        data["WIP"] = self.df_aggregated_WIP.copy().reset_index().to_dict()
        data["Throughput time"] = (
            self.df_aggregated_throughput_time.copy()
            .reset_index()
            .to_dict()
        )
        data["Resource states"] = (
            self.df_aggregated_resource_states.copy()
            .set_index(["Resource", "Time_type"])
            .reset_index()
            .to_dict()
        )

        return data

    def get_aggregated_throughput_time_data(self) -> List[float]:
        return list(self.df_aggregated_throughput_time.values)

    def get_aggregated_throughput_data(self) -> List[float]:
        return list(self.df_aggregated_output.values)

    def get_aggregated_wip_data(self) -> List[float]:
        s = self.df_aggregated_WIP.copy()
        s = s.drop(labels=["Total"])
        return list(s.values)
