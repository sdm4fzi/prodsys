import pandas as pd
import pm4py
from pm4py.visualization.petri_net import visualizer as pn_visualizer
import os
import plotly.figure_factory as ff
import plotly.express as px
import numpy as np
from dataclasses import dataclass, field

@dataclass
class PostProcessor:
    filepath: str = field(default="")
    df_raw: pd.DataFrame = field(default=None, init=False)

    def __post_init__(self):
        os.environ["PATH"] += os.pathsep + "C:/Program Files/Graphviz/bin"
        if self.filepath:
            self.read_df_from_csv()

    def read_df_from_csv(self, filepath_input: str=None):
        if filepath_input:
            self.filepath = filepath_input
        self.df_raw = pd.read_csv(self.filepath)
        self.df_raw.drop(columns=['Unnamed: 0'], inplace=True)

    def get_prepared_df(self) -> pd.DataFrame:
        df = self.df_raw.copy()
        df['DateTime'] = pd.to_datetime(df['Time'], unit='m')
        df['Material_type'] = df['Material'].str[:10]
        df['Combined_activity'] = df['State'] + ' ' + df['Activity']
        df['Material_type'] = df['Material'].str[:10]
        df.loc[df['State'].str.contains('S'), 'State_type'] = 'Interface State'
        df.loc[df['State'].str.contains('P'), 'State_type'] = 'Process State'
        df.loc[df['State'].str.contains('Breakdown'), 'State_type'] = 'Breakdown State'

        df_unique = df[['State_type', 'Activity']].drop_duplicates().sort_values(by=['State_type', 'Activity'])
        df_unique['State_sorting_Index'] = [2, 7, 1, 8, 3, 4, 6, 5]
        df_unique.sort_values(by='State_sorting_Index', inplace=True)

        df = pd.merge(df, df_unique)
        df = df.sort_values(by=['Time', 'Resource', 'State_sorting_Index'])
        return df

    def get_finished_material_df(self) -> pd.DataFrame:
        df = self.get_prepared_df()
        finished_material = df.loc[(df['Material'].notna()) & (df['Activity'] == "finished material")]['Material'].unique()
        finished_material = pd.Series(finished_material, name="Material")
        df_finished_material = pd.merge(df, finished_material)
        return df_finished_material

    def get_eventlog_for_material(self, material_type: str = 'Material_1'):
        df_finished_material = self.get_finished_material_df()
        df_for_pm4py = df_finished_material.loc[df_finished_material['Material'].notnull()]
        df_for_pm4py = df_for_pm4py.rename(columns={'Material_type': 'Material:Material_type'})
        df_for_pm4py = df_for_pm4py.loc[df_for_pm4py['Material:Material_type'] == material_type]
        df_for_pm4py = pm4py.format_dataframe(df_for_pm4py, case_id='Material', activity_key='Combined_activity', timestamp_key='DateTime')
        log = pm4py.convert_to_event_log(df_for_pm4py)

        return log

    def plot_inductive_bpmn(self):
        log = self.get_eventlog_for_material()
        process_tree = pm4py.discover_process_tree_inductive(log)
        bpmn_model = pm4py.convert_to_bpmn(process_tree)
        pm4py.view_bpmn(bpmn_model, format = "png")

    def save_inductive_petri_net(self):
        log = self.get_eventlog_for_material()
        net, initial_marking, final_marking = pm4py.discover_petri_net_inductive(log)
        # pm4py.view_petri_net(net, initial_marking, final_marking)
        parameters = {pn_visualizer.Variants.FREQUENCY.value.Parameters.FORMAT: "png"}
        gviz = pn_visualizer.apply(net, initial_marking, final_marking, parameters=parameters, variant=pn_visualizer.Variants.FREQUENCY, log=log)
        pn_visualizer.save(gviz, "results/inductive_frequency.png")


    def get_throughput_data_frame(self):
        df = self.get_prepared_df()
        df_finished_material = self.get_finished_material_df()
        min = df_finished_material.groupby(by='Material')['Time'].min()
        min.name = "Start_time"
        max = df_finished_material.groupby(by='Material')['Time'].max()
        max.name = "End_time"
        tp = max - min
        tp.name = "Throughput_time"

        df_tp = pd.merge(df[['Material_type', 'Material']].drop_duplicates(), tp.to_frame().reset_index())
        df_tp = pd.merge(df_tp, min.to_frame().reset_index())

        return df_tp

    def plot_throughput_time_distribution(self):
        df_tp = self.get_throughput_data_frame()
        grouped = df_tp.groupby(by='Material_type')['Throughput_time'].apply(list)

        values = grouped.values

        group_labels = grouped.index

        # Create distplot with custom bin_size
        fig = ff.create_distplot(values, group_labels, bin_size=.2, show_curve=True, show_hist=False)
        fig.show()

    def plot_throughput_over_time(self):
        df_tp = self.get_throughput_data_frame()
        fig = px.scatter(df_tp, x="Start_time", y="Throughput_time", color="Material_type")
        fig.show()

    def get_df_with_machine_states(self) -> pd.DataFrame:
        df = self.get_prepared_df()
        positive_condition = (df['State_type'] == 'Process State') & (df['Activity'] == 'start state')
        negative_condition = (df['State_type'] == 'Process State') & (df['Activity'] == 'end state')

        df['Increment'] = 0
        df.loc[positive_condition, 'Increment'] = 1
        df.loc[negative_condition, 'Increment'] = -1

        df['Used_Capacity'] = df.groupby(by='Resource')['Increment'].cumsum()

        fig = px.scatter(df, x="Time", y="Used_Capacity", color="Resource")

        df['next_State_sorting_Index'] = df.groupby(by='Resource')['State_sorting_Index'].shift(-1)
        df['next_Time'] = df.groupby('Resource')['Time'].shift(-1)


        STANDBY_CONDITION = (df['State_sorting_Index'] == 2) | ((df['State_sorting_Index'] == 4) & (df['Used_Capacity'] == 0))
        PRODUCTIVE_CONDITION = (df['State_sorting_Index'] == 5) | (df['State_sorting_Index'] == 3) | ((df['State_sorting_Index'] == 3) & df['Used_Capacity'] != 0)
        DOWN_CONDITION = (df['State_sorting_Index'] == 6) | (df['State_sorting_Index'] == 7)

        df['time_increment'] = df['next_Time'] - df['Time']

        df.loc[STANDBY_CONDITION, 'Time_type'] = 'SB'
        df.loc[PRODUCTIVE_CONDITION, 'Time_type'] = 'PR'
        df.loc[DOWN_CONDITION, 'Time_type'] = 'UD'

        return df

    def plot_time_per_state_of_resources(self):
        df = self.get_df_with_machine_states()

        df_time_per_state = df.groupby(['Resource', 'Time_type'])['time_increment'].sum()
        df_time_per_state = df_time_per_state.to_frame().reset_index()

        df_resource_time = df_time_per_state.groupby(by='Resource').sum().reset_index()
        df_resource_time.rename(columns={'time_increment': 'resource_time'}, inplace=True)
        df_time_per_state = pd.merge(df_time_per_state, df_resource_time)
        df_time_per_state['percentage'] = df_time_per_state['time_increment'] / df_time_per_state['resource_time']


        fig = px.bar(df_time_per_state, x="Resource", y="time_increment", color="Time_type", color_discrete_map={'PR': 'green', 'SB': 'yellow', 'UD': 'red' })
        fig.show()

    def get_df_with_WIP(self) -> pd.DataFrame:
        df = self.get_df_with_machine_states()

        CREATED_CONDITION = df['Activity'] == "created material"
        FINISHED_CONDITION = df['Activity'] == "finished material"

        df['WIP_Increment'] = 0
        df.loc[CREATED_CONDITION, 'WIP_Increment'] = 1
        df.loc[FINISHED_CONDITION, 'WIP_Increment'] = -1

        df['WIP'] = df['WIP_Increment'].cumsum()
        return df
    
    def plot_WIP(self):
        df = self.get_df_with_WIP()
        fig = px.scatter(df, x="Time", y="WIP")

        fig.show()


if __name__ == '__main__':
    p = PostProcessor(filepath='data/data.csv')

    p.plot_time_per_state_of_resources()
    p.plot_WIP()
    p.plot_throughput_over_time()
    p.plot_throughput_time_distribution()
    p.plot_inductive_bpmn()
    p.save_inductive_petri_net()

