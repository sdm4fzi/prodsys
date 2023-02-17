import os

import pandas as pd
import plotly.express as px
import plotly.figure_factory as ff
import plotly.graph_objects as go

from prodsim.util import post_processing

def hex_to_rgba(h, alpha):
    """
    converts color value in hex format to rgba format with alpha transparency
    """
    return tuple([int(h.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)] + [alpha])

def plot_throughput_time_distribution(post_processor: post_processing.PostProcessor):
    df_tp = post_processor.get_throughput_data_frame
    grouped = df_tp.groupby(by="Material_type")["Throughput_time"].apply(list)

    values = grouped.values

    group_labels = grouped.index

    # Create distplot with custom bin_size
    fig = ff.create_distplot(
        values, group_labels, bin_size=0.2, show_curve=True, show_hist=False
    )
    fig.show()

def plot_throughput_time_over_time(post_processor: post_processing.PostProcessor):
    df_tp = post_processor.get_throughput_data_frame
    fig = px.scatter(
        df_tp,
        x="Start_time",
        y="Throughput_time",
        color="Material_type",
        trendline="expanding",
    )
    fig.data = [t for t in fig.data if t.mode == "lines"]
    fig.update_traces(showlegend=True)
    fig.show()


def plot_time_per_state_of_resources(post_processor: post_processing.PostProcessor):
    df_time_per_state = post_processor.get_time_per_state_of_resources

    fig = px.bar(
        df_time_per_state,
        x="Resource",
        y="time_increment",
        color="Time_type",
        color_discrete_map={
            "PR": "green",
            "SB": "yellow",
            "UD": "red",
            "ST": "blue",
        },
    )
    fig.show()


def plot_WIP_with_range(post_processor: post_processing.PostProcessor):
    df = post_processor.get_df_with_WIP.copy()
    fig = px.scatter(df, x="Time", y="WIP")
    df["Material_type"] = "Total"

    df_per_material = post_processor.get_df_with_WIP_per_product.copy()

    df = pd.concat([df, df_per_material])

    fig = go.Figure()

    window = 5000
    colors = px.colors.qualitative.G10

    for material_type, df_material_type in df.groupby(by="Material_type"):
        df_material_type["WIP_avg"] = (
            df_material_type["WIP"].rolling(window=window).mean()
        )
        df_material_type["WIP_std"] = (
            df_material_type["WIP"].rolling(window=window).std()
        )

        color = colors.pop()
        fig.add_scatter(
            name=material_type,
            x=df_material_type["Time"],
            y=df_material_type["WIP_avg"],
            mode="lines",
            line=dict(color=color),
        )
        fig.add_scatter(
            name=material_type + " Upper Bound",
            x=df_material_type["Time"],
            y=df_material_type["WIP_avg"] + df_material_type["WIP_std"],
            mode="lines",
            line=dict(dash="dash", color=color),
            showlegend=False,
        )
        fig.add_scatter(
            name=material_type + " Lower Bound",
            x=df_material_type["Time"],
            y=df_material_type["WIP_avg"] - df_material_type["WIP_std"],
            mode="lines",
            line=dict(dash="dash", color=color),
            fill="tonexty",
            fillcolor="rgba" + str(hex_to_rgba(color, 0.2)),
            showlegend=False,
        )

    fig.show()

def plot_WIP(post_processor: post_processing.PostProcessor):
    df = post_processor.get_df_with_WIP.copy()
    fig = px.scatter(df, x="Time", y="WIP")
    df["Material_type"] = "Total"

    df_per_material = post_processor.get_df_with_WIP_per_product.copy()

    df = pd.concat([df, df_per_material])
    fig = px.scatter(
        df,
        x="Time",
        y="WIP",
        color="Material_type",
        trendline="expanding",
        opacity=0.01,
    )
    # fig = px.scatter(df, x='Time', y='WIP', color='Material_type', trendline="rolling", trendline_options=dict(window=20))
    fig.data = [t for t in fig.data if t.mode == "lines"]
    fig.update_traces(showlegend=True)

    fig.show()

def print_aggregated_data(post_processor: post_processing.PostProcessor):
    print("\n------------- Throughput -------------\n")

    print(post_processor.get_aggregated_output_and_throughput_data_frame)

    print("------------- WIP -------------\n")
    print(post_processor.get_df_with_aggregated_WIP)

    print("\n------------- Throughput time -------------\n")
    print(post_processor.get_aggregated_throughput_time_data_frame)

    print("\n------------- Resource states -------------\n")

    print(
        post_processor.get_time_per_state_of_resources.copy().set_index(["Resource", "Time_type"])
    )

def plot_inductive_bpmn(post_processor: post_processing.PostProcessor):
    import pm4py

    os.environ["PATH"] += os.pathsep + "C:/Program Files/Graphviz/bin"
    log = post_processor.get_eventlog_for_material()
    process_tree = pm4py.discover_process_tree_inductive(log)
    bpmn_model = pm4py.convert_to_bpmn(process_tree)
    pm4py.view_bpmn(bpmn_model, format="png")