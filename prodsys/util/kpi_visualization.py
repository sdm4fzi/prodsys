import os

import pandas as pd
import plotly.express as px
import plotly.figure_factory as ff
import plotly.graph_objects as go

from prodsys.util import post_processing

def hex_to_rgba(h, alpha):
    return tuple([int(h.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)] + [alpha])

def plot_throughput_time_distribution(post_processor: post_processing.PostProcessor):
    """
    Plots the throughput time distribution of the simulation.

    Args:
        post_processor (post_processing.PostProcessor): Post processor of the simulation.
    """
    df_tp = post_processor.df_throughput
    grouped = df_tp.groupby(by="Product_type")["Throughput_time"].apply(list)

    values = grouped.values

    group_labels = grouped.index

    # Create distplot with custom bin_size
    fig = ff.create_distplot(
        values, group_labels, bin_size=0.2, show_curve=True, show_hist=False
    )
    fig.show()

def plot_throughput_time_over_time(post_processor: post_processing.PostProcessor):
    """
    Plots the throughput time over time of the simulation.

    Args:
        post_processor (post_processing.PostProcessor): Post processor of the simulation.
    """
    df_tp = post_processor.df_throughput
    fig = px.scatter(
        df_tp,
        x="Start_time",
        y="Throughput_time",
        color="Product_type",
        trendline="expanding",
    )
    fig.data = [t for t in fig.data if t.mode == "lines"]
    fig.update_traces(showlegend=True)
    fig.show()


def plot_time_per_state_of_resources(post_processor: post_processing.PostProcessor, normalized: bool=True):
    """
    Plots the time per state of the resources of the simulation.

    Args:
        post_processor (post_processing.PostProcessor): Post processor of the simulation.
        normalized (bool, optional): If True, the time per state is normalized with the total time of the simulation. Defaults to True.
    """
    df_time_per_state = post_processor.df_aggregated_resource_states

    if normalized:
        y_column = "percentage"
    else:
        y_column = "time_increment"

    fig = px.bar(
        df_time_per_state,
        x="Resource",
        y=y_column,
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
    """
    Plots the WIP of the production system over time of the simulation with a range of the WIP based on a standard deviation.

    Args:
        post_processor (post_processing.PostProcessor): Post processor of the simulation.
    """
    df = post_processor.df_WIP.copy()
    fig = px.scatter(df, x="Time", y="WIP")
    df["Product_type"] = "Total"

    df_per_product = post_processor.df_WIP_per_product.copy()

    df = pd.concat([df, df_per_product])

    fig = go.Figure()

    window = 5000
    colors = px.colors.qualitative.G10

    for product_type, df_product_type in df.groupby(by="Product_type"):
        df_product_type["WIP_avg"] = (
            df_product_type["WIP"].rolling(window=window).mean()
        )
        df_product_type["WIP_std"] = (
            df_product_type["WIP"].rolling(window=window).std()
        )

        color = colors.pop()
        fig.add_scatter(
            name=product_type,
            x=df_product_type["Time"],
            y=df_product_type["WIP_avg"],
            mode="lines",
            line=dict(color=color),
        )
        fig.add_scatter(
            name=product_type + " Upper Bound",
            x=df_product_type["Time"],
            y=df_product_type["WIP_avg"] + df_product_type["WIP_std"],
            mode="lines",
            line=dict(dash="dash", color=color),
            showlegend=False,
        )
        fig.add_scatter(
            name=product_type + " Lower Bound",
            x=df_product_type["Time"],
            y=df_product_type["WIP_avg"] - df_product_type["WIP_std"],
            mode="lines",
            line=dict(dash="dash", color=color),
            fill="tonexty",
            fillcolor="rgba" + str(hex_to_rgba(color, 0.2)),
            showlegend=False,
        )

    fig.show()

def plot_WIP(post_processor: post_processing.PostProcessor):
    """
    Plots the WIP of the production system over time of the simulation.

    Args:
        post_processor (post_processing.PostProcessor): Post processor of the simulation.
    """
    df = post_processor.df_WIP.copy()
    fig = px.scatter(df, x="Time", y="WIP")
    df["Product_type"] = "Total"

    df_per_product = post_processor.df_WIP_per_product.copy()

    df = pd.concat([df, df_per_product])
    fig = px.scatter(
        df,
        x="Time",
        y="WIP",
        color="Product_type",
        trendline="expanding",
        opacity=0.01,
    )
    fig.data = [t for t in fig.data if t.mode == "lines"]
    fig.update_traces(showlegend=True)

    fig.show()

def plot_WIP_per_resource(post_processor: post_processing.PostProcessor):
    """
    Plots the WIP of the production system and the resources in the production system over time of the simulation.

    Args:
        post_processor (post_processing.PostProcessor): Post processor of the simulation.
    """
    df = post_processor.df_WIP.copy()
    fig = px.scatter(df, x="Time", y="WIP")
    df["Resource"] = "Total"

    df_per_resource = post_processor.df_WIP_per_resource.copy()
    df_per_resource["Resource"] = df_per_resource["WIP_resource"]

    df = pd.concat([df, df_per_resource])
    fig = px.scatter(
        df,
        x="Time",
        y="WIP",
        color="Resource",
        trendline="expanding",
        opacity=0.01,
    )
    fig.data = [t for t in fig.data if t.mode == "lines"]
    fig.update_traces(showlegend=True)

    fig.show()

def print_aggregated_data(post_processor: post_processing.PostProcessor):
    """
    Prints the aggregated data of the simulation, comprising the throughput, WIP, throughput time and resource states.

    Args:
        post_processor (post_processing.PostProcessor): Post processor of the simulation.
    """
    print("\n------------- Throughput -------------\n")

    print(post_processor.df_aggregated_output_and_throughput)

    print("------------- WIP -------------\n")
    print(post_processor.df_aggregated_WIP)

    print("\n------------- Throughput time -------------\n")
    print(post_processor.df_aggregated_throughput_time)

    print("\n------------- Resource states -------------\n")

    print(
        post_processor.df_aggregated_resource_states.copy().set_index(["Resource", "Time_type"])
    )
