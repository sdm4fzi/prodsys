import os
from typing import List
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.figure_factory as ff
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from prodsys.util import post_processing


def hex_to_rgba(h, alpha):
    return tuple([int(h.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)] + [alpha])


def plot_output_over_time(
    post_processor: post_processing.PostProcessor,
    return_html: bool = False,
    return_image: bool = False,
):
    """
    Plots the output of the production system over time of the simulation.

    Args:
        post_processor (post_processing.PostProcessor): Post processor of the simulation.
    """
    df_tpt = post_processor.df_throughput.copy()
    df_tpt.sort_values(by="End_time", inplace=True)
    # Output is just the index of each row grouped by each product type    
    df_tpt["Output"] = df_tpt.groupby("Product_type")["Product"].cumcount() + 1
    fig = px.line(
        df_tpt,
        x="End_time",
        y="Output",
        color="Product_type",
        # trendline="expanding",
        line_shape="hv"
        # opacity=0.01,
    )
    # fig.data = [t for t in fig.data if t.mode == "lines"]
    fig.update_traces(showlegend=True)
    fig.update_layout(
        xaxis_title="Time [Minutes]",
        yaxis_title="Output [Products]",
    )
    min_start_time = df_tpt["End_time"].min()
    max_start_time = df_tpt["End_time"].max()
    new_x_range = [min_start_time, max_start_time]
    fig.update_layout(xaxis_range=new_x_range)
    fig.add_vline(
        x=post_processor.warm_up_cutoff_time,
        line_dash="dash",
        line_color="red",
        annotation_text="Steady State",
        annotation_position="top right",
    )
    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))
    fig.write_html( 
        os.path.join(os.getcwd(), "plots", "output_over_time.html"),
        auto_open=not return_html,
    )
    if return_html:
        return pio.to_html(fig, full_html=False)
    if return_image:
        image_path = os.path.join(os.getcwd(), "plots", "output_over_time.png")
        fig.write_image(image_path)
        return image_path


def plot_throughput_time_distribution(
    post_processor: post_processing.PostProcessor,
    return_html: bool = False,
    return_image: bool = False,
):
    """
    Plots the throughput time distribution of the simulation.

    Args:
        post_processor (post_processing.PostProcessor): Post processor of the simulation.
    """
    df_tp = post_processor.df_throughput
    grouped = df_tp.groupby(by="Product_type")["Throughput_time"].apply(list)

    values = grouped.values

    group_labels = grouped.index

    if len(values) < 30:
        return None

    # Create distplot with custom bin_size
    fig = ff.create_distplot(
        values, group_labels, bin_size=0.2, show_curve=True, show_hist=False
    )
    fig.update_layout(
        xaxis_title="Throughput Time [Minutes]",
        yaxis_title="Probability Density",
    )
    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))
    fig.write_html(
        os.path.join(os.getcwd(), "plots", "throughput_time_distribution.html"),
        auto_open=not return_html,
    )

    if return_html:
        return pio.to_html(fig, include_plotlyjs="cdn", full_html=False)
    if return_image:
        image_path = os.path.join(
            os.getcwd(), "plots", "throughput_time_distribution.png"
        )
        fig.write_image(image_path)
        return image_path


def plot_line_balance_kpis(
    post_processor: post_processing.PostProcessor,
    return_html: bool = False,
    return_image: bool = False,
):
    """
    Plots line balancing key performance indicators (throughput, WIP, and Throughput Time) after total time.

    Args:
        post_processor (post_processing.PostProcessor): Post processor of the simulation.
    """

    df_output = post_processor.get_aggregated_data()
    fig = make_subplots(
        rows=1,
        cols=3,
        specs=[[{"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}]],
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=round(np.sum(list(df_output["Throughput"]["Output"].values()))),
            title={"text": "Total Output [Products]"},
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=round(np.mean(list(df_output["WIP"]["WIP"].values()))),
            title={"text": "Average Work In Progress (WIP) [Products]"},
        ),
        row=1,
        col=2,
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=round(
                np.nanmean(
                    list(df_output["Throughput time"]["Throughput_time"].values())
                )
            ),
            title={"text": "Average Throughput Time [Minutes]"},
        ),
        row=1,
        col=3,
    )

    fig.update_layout(
        title_text="Line Balancing KPIs after Total Time",
        annotations=[
            dict(
                x=0.5,
                y=-0.1,
                showarrow=False,
                text="All KPI's are calculated for the steady state production",
                xref="paper",
                yref="paper",
            )
        ],
    )
    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))
    fig.write_html(
        os.path.join(os.getcwd(), "plots", "line_balance.html"),
        auto_open=not return_html,
    )

    if return_html:
        return pio.to_html(fig, full_html=False)
    if return_image:
        image_path = os.path.join(os.getcwd(), "plots", "line_balance_kpis.png")
        fig.write_image(image_path)
        return image_path


def plot_oee(
    post_processor: post_processing.PostProcessor,
    return_html: bool = False,
    return_image: bool = False,
):
    """
    Plots the Overall Equipment Effectiveness (OEE) with Availability, Performance & Quality using the given post_processor.

    Args:
        post_processor: An instance of the post_processing.PostProcessor class.
    """
    df_oee = post_processor.df_oee_production_system
    fig = make_subplots(
        rows=1,
        cols=4,
        specs=[
            [
                {"type": "indicator"},
                {"type": "indicator"},
                {"type": "indicator"},
                {"type": "indicator"},
            ]
        ],
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=df_oee["Value"][0],
            title={"text": "Availability in %"},
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=df_oee["Value"][1],
            title={"text": "Performance in %"},
        ),
        row=1,
        col=2,
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=df_oee["Value"][2],
            title={"text": "Quality in %"},
        ),
        row=1,
        col=3,
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=df_oee["Value"][3],
            title={"text": "OEE in %"},
        ),
        row=1,
        col=4,
    )

    fig.update_layout(
        title_text="Overall Equipment Effectiveness (OEE)",
        annotations=[
            dict(
                x=0.5,
                y=-0.1,
                showarrow=False,
                text="OEE = Availability * Performance * Quality",
                xref="paper",
                yref="paper",
            )
        ],
    )
    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))
    fig.write_html(
        os.path.join(os.getcwd(), "plots", "oee.html"), auto_open=not return_html
    )

    if return_html:
        return pio.to_html(fig, full_html=True)
    if return_image:
        image_path = os.path.join(os.getcwd(), "plots", "oee.png")
        fig.write_image(image_path)
        return image_path


def plot_oee_over_time(
    post_processor: post_processing.PostProcessor,
    resource_names: List[str] = None,
    interval_minutes: float = 10.0,
    return_html: bool = False,
    return_image: bool = False,
):
    """
    Plots OEE (Overall Equipment Effectiveness) over time for specified resources.
    
    Shows Availability, Performance, Quality, and OEE as separate lines for each resource.

    Args:
        post_processor (post_processing.PostProcessor): The post processor object containing the data.
        resource_names (List[str], optional): List of resource names to plot. If None, plots all resources.
        interval_minutes (float): Time interval in minutes for aggregation. Defaults to 10.0.
        return_html (bool): If True, returns HTML string instead of saving file.
        return_image (bool): If True, saves as image and returns path.
    """
    df_oee = post_processor.get_oee_per_resource_by_interval(interval_minutes)
    
    if len(df_oee) == 0:
        print("No OEE data available for plotting.")
        return None
    
    if resource_names is not None:
        resource_names = set(resource_names)
        df_oee = df_oee[df_oee["Resource"].isin(resource_names)]
    
    if len(df_oee) == 0:
        print("No OEE data available for specified resources.")
        return None
    
    # Create subplots for each OEE component
    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=("Availability", "Performance", "Quality", "OEE"),
        vertical_spacing=0.12,
        horizontal_spacing=0.1,
    )
    
    resources = df_oee["Resource"].unique()
    colors = px.colors.qualitative.Set3[:len(resources)] if len(resources) <= 12 else px.colors.qualitative.Dark24
    
    for idx, resource in enumerate(resources):
        df_resource = df_oee[df_oee["Resource"] == resource].sort_values("Interval_start")
        color = colors[idx % len(colors)]
        
        # Availability
        fig.add_trace(
            go.Scatter(
                x=df_resource["Interval_start"],
                y=df_resource["Availability"],
                mode="lines+markers",
                name=f"{resource}",
                line=dict(color=color),
                showlegend=True,
            ),
            row=1,
            col=1,
        )
        
        # Performance
        fig.add_trace(
            go.Scatter(
                x=df_resource["Interval_start"],
                y=df_resource["Performance"],
                mode="lines+markers",
                name=f"{resource}",
                line=dict(color=color),
                showlegend=False,
            ),
            row=1,
            col=2,
        )
        
        # Quality
        fig.add_trace(
            go.Scatter(
                x=df_resource["Interval_start"],
                y=df_resource["Quality"],
                mode="lines+markers",
                name=f"{resource}",
                line=dict(color=color),
                showlegend=False,
            ),
            row=2,
            col=1,
        )
        
        # OEE
        fig.add_trace(
            go.Scatter(
                x=df_resource["Interval_start"],
                y=df_resource["OEE"],
                mode="lines+markers",
                name=f"{resource}",
                line=dict(color=color),
                showlegend=False,
            ),
            row=2,
            col=2,
        )
    
    fig.update_xaxes(title_text="Time [Minutes]", row=2, col=1)
    fig.update_xaxes(title_text="Time [Minutes]", row=2, col=2)
    fig.update_yaxes(title_text="Percentage [%]", row=1, col=1)
    fig.update_yaxes(title_text="Percentage [%]", row=1, col=2)
    fig.update_yaxes(title_text="Percentage [%]", row=2, col=1)
    fig.update_yaxes(title_text="Percentage [%]", row=2, col=2)
    fig.update_yaxes(range=[0, 100])
    
    fig.update_layout(
        title_text="OEE Over Time",
        height=800,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.1,
            xanchor="center",
            x=0.5,
        ),
    )
    
    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))
    fig.write_html(
        os.path.join(os.getcwd(), "plots", "oee_over_time.html"),
        auto_open=not return_html,
    )
    
    if return_html:
        return pio.to_html(fig, full_html=True)
    if return_image:
        image_path = os.path.join(os.getcwd(), "plots", "oee_over_time.png")
        fig.write_image(image_path)
        return image_path


def plot_resource_states_over_time(
    post_processor: post_processing.PostProcessor,
    resource_names: List[str] = None,
    time_types: List[str] = None,
    interval_minutes: float = 10.0,
    return_html: bool = False,
    return_image: bool = False,
):
    """
    Plots resource states over time for specified resources.
    
    Shows the percentage of time spent in each state (PR, SB, UD, ST, CR, etc.) over time.

    Args:
        post_processor (post_processing.PostProcessor): The post processor object containing the data.
        resource_names (List[str], optional): List of resource names to plot. If None, plots all resources.
        time_types (List[str], optional): List of time types to plot (e.g., ["PR", "SB", "UD"]). 
                                         If None, plots all time types.
        interval_minutes (float): Time interval in minutes for aggregation. Defaults to 10.0.
        return_html (bool): If True, returns HTML string instead of saving file.
        return_image (bool): If True, saves as image and returns path.
    """
    df_states = post_processor.get_aggregated_resource_states_by_interval(interval_minutes)
    
    if len(df_states) == 0:
        print("No resource states data available for plotting.")
        return None
    
    if resource_names is not None:
        resource_names = set(resource_names)
        df_states = df_states[df_states["Resource"].isin(resource_names)]
    
    if time_types is not None:
        time_types = set(time_types)
        df_states = df_states[df_states["Time_type"].isin(time_types)]
    
    if len(df_states) == 0:
        print("No resource states data available for specified filters.")
        return None
    
    # Color mapping for time types
    color_map = {
        "PR": "green",
        "SB": "yellow",
        "UD": "red",
        "ST": "blue",
        "CR": "grey",
        "DP": "lightgreen",
        "NS": "darkgrey",
    }
    
    fig = go.Figure()
    
    # Group by resource and time type
    for resource in df_states["Resource"].unique():
        df_resource = df_states[df_states["Resource"] == resource].sort_values("Interval_start")
        
        for time_type in df_resource["Time_type"].unique():
            df_type = df_resource[df_resource["Time_type"] == time_type].sort_values("Interval_start")
            
            color = color_map.get(time_type, "black")
            name = f"{resource} - {time_type}"
            
            fig.add_trace(
                go.Scatter(
                    x=df_type["Interval_start"],
                    y=df_type["percentage"],
                    mode="lines+markers",
                    name=name,
                    line=dict(color=color),
                    legendgroup=resource,
                )
            )
    
    fig.update_layout(
        title="Resource States Over Time",
        xaxis_title="Time [Minutes]",
        yaxis_title="Percentage [%]",
        height=600,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
        ),
    )
    fig.update_yaxes(range=[0, 100])
    
    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))
    fig.write_html(
        os.path.join(os.getcwd(), "plots", "resource_states_over_time.html"),
        auto_open=not return_html,
    )
    
    if return_html:
        return pio.to_html(fig, full_html=True)
    if return_image:
        image_path = os.path.join(
            os.getcwd(), "plots", "resource_states_over_time.png"
        )
        fig.write_image(image_path)
        return image_path


def plot_oee_system_over_time(
    post_processor: post_processing.PostProcessor,
    interval_minutes: float = 10.0,
    return_html: bool = False,
    return_image: bool = False,
):
    """
    Plots system-level OEE over time.
    
    Calculates system OEE as weighted average of resource OEEs for each interval.

    Args:
        post_processor (post_processing.PostProcessor): The post processor object containing the data.
        interval_minutes (float): Time interval in minutes for aggregation. Defaults to 10.0.
        return_html (bool): If True, returns HTML string instead of saving file.
        return_image (bool): If True, saves as image and returns path.
    """
    df_oee = post_processor.get_oee_per_resource_by_interval(interval_minutes)
    df_states = post_processor.get_aggregated_resource_states_by_interval(interval_minutes)
    
    if len(df_oee) == 0 or len(df_states) == 0:
        print("No OEE or resource states data available for system-level calculation.")
        return None
    
    # Calculate system-level OEE per interval as weighted average
    intervals = sorted(df_oee["Interval_start"].unique())
    system_oee_data = []
    
    for interval_start in intervals:
        interval_oee = df_oee[df_oee["Interval_start"] == interval_start]
        interval_states = df_states[df_states["Interval_start"] == interval_start]
        
        if len(interval_oee) == 0:
            continue
        
        # Calculate weights based on planned production time (resource_time - NS time)
        resource_weights = {}
        for resource in interval_states["Resource"].unique():
            df_resource = interval_states[interval_states["Resource"] == resource]
            interval_time = df_resource["interval_time"].iloc[0] if len(df_resource) > 0 else 0
            ns_time = df_resource[df_resource["Time_type"] == "NS"]["time_increment"].sum()
            planned_time = interval_time - ns_time
            resource_weights[resource] = max(0, planned_time)
        
        total_weight = sum(resource_weights.values())
        
        if total_weight > 0:
            # Calculate weighted averages
            availability_sum = 0.0
            performance_sum = 0.0
            quality_sum = 0.0
            oee_sum = 0.0
            
            for _, row in interval_oee.iterrows():
                resource = row["Resource"]
                weight = resource_weights.get(resource, 0)
                if weight > 0:
                    availability_sum += (row["Availability"] / 100.0) * weight
                    performance_sum += (row["Performance"] / 100.0) * weight
                    quality_sum += (row["Quality"] / 100.0) * weight
                    oee_sum += (row["OEE"] / 100.0) * weight
            
            system_oee_data.append({
                "Interval_start": interval_start,
                "Availability": (availability_sum / total_weight) * 100,
                "Performance": (performance_sum / total_weight) * 100,
                "Quality": (quality_sum / total_weight) * 100,
                "OEE": (oee_sum / total_weight) * 100,
            })
    
    if len(system_oee_data) == 0:
        print("No system-level OEE data calculated.")
        return None
    
    df_system_oee = pd.DataFrame(system_oee_data).sort_values("Interval_start")
    
    # Create subplots
    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=("Availability", "Performance", "Quality", "OEE"),
        vertical_spacing=0.12,
        horizontal_spacing=0.1,
    )
    
    # Availability
    fig.add_trace(
        go.Scatter(
            x=df_system_oee["Interval_start"],
            y=df_system_oee["Availability"],
            mode="lines+markers",
            name="System Availability",
            line=dict(color="blue"),
        ),
        row=1,
        col=1,
    )
    
    # Performance
    fig.add_trace(
        go.Scatter(
            x=df_system_oee["Interval_start"],
            y=df_system_oee["Performance"],
            mode="lines+markers",
            name="System Performance",
            line=dict(color="green"),
        ),
        row=1,
        col=2,
    )
    
    # Quality
    fig.add_trace(
        go.Scatter(
            x=df_system_oee["Interval_start"],
            y=df_system_oee["Quality"],
            mode="lines+markers",
            name="System Quality",
            line=dict(color="orange"),
        ),
        row=2,
        col=1,
    )
    
    # OEE
    fig.add_trace(
        go.Scatter(
            x=df_system_oee["Interval_start"],
            y=df_system_oee["OEE"],
            mode="lines+markers",
            name="System OEE",
            line=dict(color="red"),
        ),
        row=2,
        col=2,
    )
    
    fig.update_xaxes(title_text="Time [Minutes]", row=2, col=1)
    fig.update_xaxes(title_text="Time [Minutes]", row=2, col=2)
    fig.update_yaxes(title_text="Percentage [%]", row=1, col=1)
    fig.update_yaxes(title_text="Percentage [%]", row=1, col=2)
    fig.update_yaxes(title_text="Percentage [%]", row=2, col=1)
    fig.update_yaxes(title_text="Percentage [%]", row=2, col=2)
    fig.update_yaxes(range=[0, 100])
    
    fig.update_layout(
        title_text="System OEE Over Time",
        height=800,
        showlegend=True,
    )
    
    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))
    fig.write_html(
        os.path.join(os.getcwd(), "plots", "oee_system_over_time.html"),
        auto_open=not return_html,
    )
    
    if return_html:
        return pio.to_html(fig, full_html=True)
    if return_image:
        image_path = os.path.join(os.getcwd(), "plots", "oee_system_over_time.png")
        fig.write_image(image_path)
        return image_path


def plot_production_flow_rate_per_product(
    post_processor: post_processing.PostProcessor,
    return_html: bool = False,
    return_image: bool = False,
):
    """
    Plots the production flow rate per product.

    Args:
        post_processor (post_processing.PostProcessor): The post processor object containing the data.
    """
    percentage_df = post_processor.df_production_flow_ratio

    fig = go.Figure(
        data=[
            go.Bar(
                name="Production",
                y=percentage_df["Product_type"],
                x=percentage_df["Production "],
                marker_color="steelblue",
                orientation="h",
                text=percentage_df["Production "].round(2),
                textposition="auto",
                textangle=-90,
            ),
            go.Bar(
                name="Transport",
                y=percentage_df["Product_type"],
                x=percentage_df["Transport "],
                marker_color="darkseagreen",
                orientation="h",
                text=percentage_df["Transport "].round(2),
                textposition="auto",
                textangle=-90,
            ),
            go.Bar(
                name="Idle",
                y=percentage_df["Product_type"],
                x=percentage_df["Idle "],
                marker_color="lightcoral",
                orientation="h",
                text=percentage_df["Idle "].round(2),
                textposition="auto",
                textangle=-90,
            ),
        ]
    )
    # Change the bar mode
    fig.update_layout(barmode="stack")
    fig.update_xaxes(title_text="Percentage [%]")
    fig.update_layout(
        title_text="Production Flow Rate (PFO) per Product",
        annotations=[
            dict(
                x=0.5,
                y=-0.1,
                showarrow=False,
                text="Time spent of product in Production, Transport and Idle during the whole throughput time",
                xref="paper",
                yref="paper",
            )
        ],
    )
    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))
    fig.write_html(
        os.path.join(os.getcwd(), "plots", "production_flow_rate_product_type.html"),
        auto_open=not return_html,
    )

    if return_html:
        return pio.to_html(fig, full_html=True)
    if return_image:
        image_path = os.path.join(
            os.getcwd(), "plots", "production_flow_rate_per_product.png"
        )
        fig.write_image(image_path)
        return image_path


def plot_boxplot_resource_utilization(
    post_processor: post_processing.PostProcessor,
    interval_minutes: float = 100.0,
    return_html: bool = False,
    return_image: bool = False,
):
    """
    Plots a boxplot to visualize resource utilization per station.

    Args:
        post_processor (post_processing.PostProcessor): The post processor object containing the data.
        interval_minutes (float): Time interval in minutes for aggregation. Defaults to 100.0.
    """
    df_time_per_state = post_processor.get_aggregated_resource_states_by_interval(interval_minutes)
    resources = df_time_per_state["Resource"].unique()
    df_productive_time = df_time_per_state.loc[df_time_per_state["Time_type"] == "PR"]
    fig = go.Figure()

    for resource in resources:
        df_resource = df_productive_time.loc[df_time_per_state["Resource"] == resource]

        if len(df_resource) == 0:
            df_resource = pd.DataFrame({"Resource": [resource], "percentage": [0]})

        fig.add_trace(
            go.Box(
                y=df_resource["percentage"],
                name=f"{resource}",
                boxmean=True,
            )
        )

    fig.update_layout(
        title_text="Utilization per Station",
        yaxis_title="Percentage [%]",
        showlegend=False,
        annotations=[
            dict(
                x=0.5,
                y=-0.7,
                showarrow=False,
                # text="Dashed Line = Mean & Solid Line = Median, Whiskers = Q1/Q3 +/- 1.5 * IQR(Q3-Q1)",
                xref="paper",
                yref="paper",
            )
        ],
        height=600,
    )
    fig.update_yaxes(range=[0, 100])

    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))
    fig.write_html(
        os.path.join(os.getcwd(), "plots", "resource_box_plots.html"),
        auto_open=not return_html,
    )

    if return_html:
        return pio.to_html(fig, full_html=True)
    if return_image:
        image_path = os.path.join(
            os.getcwd(), "plots", "boxplot_resource_utilization.png"
        )
        fig.write_image(image_path)
        return image_path


def plot_throughput_time_over_time(
    post_processor: post_processing.PostProcessor,
    return_html: bool = False,
    return_image: bool = False,
):
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
    fig.update_layout(
        xaxis_title="Start Time [Minutes]",
        yaxis_title="Throughput Time [Minutes]",
    )
    min_start_time = df_tp["Start_time"].min()
    max_start_time = df_tp["Start_time"].max()

    warum_up_cut_off_time = post_processor.warm_up_cutoff_time

    new_x_range = [min_start_time, max_start_time]

    fig.update_layout(xaxis_range=new_x_range)

    fig.add_vline(
        x=warum_up_cut_off_time,
        line_dash="dash",
        line_color="red",
        annotation_text="Steady State",
        annotation_position="top right",
    )
    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))
    fig.write_html(
        os.path.join(os.getcwd(), "plots", "throughput.html"), auto_open=not return_html
    )

    if return_html:
        return pio.to_html(fig, full_html=True)
    if return_image:
        image_path = os.path.join(os.getcwd(), "plots", "throughput_time_over_time.png")
        fig.write_image(image_path)
        return image_path


def plot_time_per_state_of_resources(
    post_processor: post_processing.PostProcessor,
    normalized: bool = True,
    return_html: bool = False,
    return_image: bool = False,
):
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
            "CR": "grey",
            "DP": "lightgreen",
            "NS": "grey",
        },
        category_orders={
            "Time_type": ["UD", "NS", "PR", "DP", "ST", "SB", "CR"]
        },
    )
    fig.update_traces(name="Productive", selector=dict(name="PR"))
    fig.update_traces(name="Standby", selector=dict(name="SB"))
    fig.update_traces(name="Unscheduled Downtime", selector=dict(name="UD"))
    fig.update_traces(name="Non-Scheduled", selector=dict(name="NS"))
    fig.update_traces(name="Setup", selector=dict(name="ST"))
    fig.update_traces(name="Charging", selector=dict(name="CR"))
    fig.update_traces(name="Dependency", selector=dict(name="DP"))
    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))
    fig.write_html(
        os.path.join(os.getcwd(), "plots", "resource_states.html"),
        auto_open=not return_html,
    )

    if return_html:
        return pio.to_html(fig, full_html=True)
    if return_image:
        image_path = os.path.join(
            os.getcwd(), "plots", "time_per_state_of_resources.png"
        )
        fig.write_image(image_path)
        return image_path


def plot_WIP_resource_boxplots(
    post_processor: post_processing.PostProcessor,
    normalized: bool = True,
    return_html: bool = False,
    return_image: bool = False,
):
    """
    Plots the WIP per resource as boxplots.

    Args:
        post_processor (post_processing.PostProcessor): Post processor of the simulation.
        normalized (bool, optional): Not used, kept for compatibility. Defaults to True.
        return_html (bool): If True, returns HTML string instead of saving file.
        return_image (bool): If True, saves as image and returns path.
    """
    df_time_per_state = post_processor.df_WIP_per_resource
    fig1 = go.Figure()
    resources = df_time_per_state["WIP_resource"].unique()
    for resource_id in resources:
        df_resource = df_time_per_state.loc[df_time_per_state["WIP_resource"] == resource_id]
        fig1.add_trace(
            go.Box(
                y=df_resource["WIP"],
                name=f"{resource_id}",
                boxmean=True,  # mean and standard deviation
            )
        )

    fig1.update_xaxes(categoryorder="array", categoryarray=resources)

    fig = make_subplots(rows=1, cols=1, shared_xaxes=True, vertical_spacing=0.1)
    for trace in fig1.data:
        fig.add_trace(trace, row=1, col=1)

    fig.update_layout(
        title="WIP per Resource",
        showlegend=False,
        height=600,  # adjust height if needed
    )

    fig.update_yaxes(title_text="WIP [Products]", row=1, col=1)

    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))
    fig.write_html(
        os.path.join(os.getcwd(), "plots", "mean_wip_util_station.html"),
        auto_open=not return_html,
    )

    if return_html:
        return pio.to_html(fig, full_html=True)
    if return_image:
        image_path = os.path.join(os.getcwd(), "plots", "WIP_resource.png")
        fig.write_image(image_path)
        return image_path


def plot_transport_utilization_over_time(
    post_processor: post_processing.PostProcessor,
    transport_resource_names: List[str],
    interval_minutes: float = 10.0,
    return_html: bool = False,
    return_image: bool = False,
):
    """
    Plots the utilization of the transport_agv resource over time.

    Args:
        post_processor (post_processing.PostProcessor): The post processor object containing the data.
        transport_resource_names (List[str]): List of names of the transport resources.
        interval_minutes (float): Time interval in minutes for aggregation. Defaults to 10.0.
    """
    df_time_per_state = post_processor.get_aggregated_resource_states_by_interval(interval_minutes)
    transport_resource_names = set(transport_resource_names)
    df_agv_pr = df_time_per_state.loc[
        (df_time_per_state["Time_type"] == "PR")
        & (df_time_per_state["Resource"].isin(transport_resource_names))
    ]
    fig = go.Figure()
    for resource in transport_resource_names:
        df_agv_pr_resource = df_agv_pr.loc[df_agv_pr["Resource"] == resource]
        fig.add_trace(
            go.Scatter(
                x=df_agv_pr_resource["Interval_start"],
                y=df_agv_pr_resource["percentage"],
                mode="lines",
                name=resource,
                #    line=dict(shape='spline', smoothing=2),  # Apply smoothing
                #    line=dict(shape='hv'),  # Apply smoothing
            ),
        )

    fig.update_layout(
        title="AGV Utilization Over Time",
        xaxis_title="Time in Minutes",
        yaxis_title="Percentage [%]",
    )

    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))
    fig.write_html(
        os.path.join(os.getcwd(), "plots", "Transport_utilization_over_time.html"),
        auto_open=not return_html,
    )

    if return_html:
        return pio.to_html(fig, full_html=True)
    if return_image:
        image_path = os.path.join(
            os.getcwd(), "plots", "transport_utilization_over_time.png"
        )
        fig.write_image(image_path)
        return image_path


def plot_WIP_with_range(
    post_processor: post_processing.PostProcessor,
    return_html: bool = False,
    return_image: bool = False,
):
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

    def get_colors() -> List[str]:
        return (
            px.colors.qualitative.Dark24
            + px.colors.qualitative.Light24
            + px.colors.qualitative.G10
        )

    colors = get_colors()

    for product_type, df_product_type in df.groupby(by="Product_type"):
        df_product_type["WIP_avg"] = (
            df_product_type["WIP"].rolling(window=int(post_processor.df_aggregated_output_and_throughput["Output"].mean()) + 5).mean()
        )
        df_product_type["WIP_std"] = df_product_type["WIP"].rolling(window=int(post_processor.df_aggregated_output_and_throughput["Output"].mean()) + 5).std()
        if not colors:
            colors = get_colors()
        color = colors.pop(0)
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
    fig.update_layout(
        title="Mean WIP and Range per Product Type",
        showlegend=True,
        xaxis_title="Time [Minutes]",
        yaxis_title="WIP [Products]",
    )

    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))
    fig.write_html(
        os.path.join(os.getcwd(), "plots", "WIP_with_range.html"),
        auto_open=not return_html,
    )

    if return_html:
        return pio.to_html(fig, full_html=True)
    if return_image:
        image_path = os.path.join(os.getcwd(), "plots", "WIP_with_range.png")
        fig.write_image(image_path)
        return image_path


def plot_WIP(
    post_processor: post_processing.PostProcessor,
    return_html: bool = False,
    return_image: bool = False,
):
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
    fig = px.line(
        df,
        x="Time",
        y="WIP",
        color="Product_type",
        line_shape="vh"
    )
    fig.data = [t for t in fig.data if t.mode == "lines"]
    fig.update_traces(showlegend=True)
    fig.update_layout(
        xaxis_title="Time [Minutes]",
        yaxis_title="WIP [Products]",
    )

    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))
    fig.write_html(
        os.path.join(os.getcwd(), "plots", "WIP.html"), auto_open=not return_html
    )

    if return_html:
        return pio.to_html(fig, full_html=True)
    if return_image:
        image_path = os.path.join(os.getcwd(), "plots", "WIP.png")
        fig.write_image(image_path)
        return image_path


def plot_primitive_WIP(
    post_processor: post_processing.PostProcessor,
    return_html: bool = False,
    return_image: bool = False,
):
    """
    Plots the WIP of the production system over time of the simulation.

    Args:
        post_processor (post_processing.PostProcessor): Post processor of the simulation.
    """
    df = post_processor.df_primitive_WIP.copy()
    fig = px.scatter(df, x="Time", y="primitive_WIP")
    df["Primitive_type"] = "Total"

    df_per_product = post_processor.df_primitive_WIP_per_primitive_type.copy()

    df = pd.concat([df, df_per_product])
    fig = px.line(
        df,
        x="Time",
        y="primitive_WIP",
        color="Primitive_type",
        line_shape="vh",
    )
    fig.data = [t for t in fig.data if t.mode == "lines"]
    fig.update_traces(showlegend=True)
    fig.update_layout(
        xaxis_title="Time [Minutes]",
        yaxis_title="Primitive WIP [Products]",
    )

    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))
    fig.write_html(
        os.path.join(os.getcwd(), "plots", "WIP.html"), auto_open=not return_html
    )

    if return_html:
        return pio.to_html(fig, full_html=True)
    if return_image:
        image_path = os.path.join(os.getcwd(), "plots", "WIP.png")
        fig.write_image(image_path)
        return image_path


def plot_WIP_per_resource(
    post_processor: post_processing.PostProcessor,
    return_html: bool = False,
    return_image: bool = False,
):
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
    fig = px.line(
        df,
        x="Time",
        y="WIP",
        color="Resource",
        line_shape="vh",
    )
    fig.data = [t for t in fig.data if t.mode == "lines"]
    fig.update_traces(showlegend=True)
    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.3,
            xanchor="center",
            x=0.5,
        ),
        xaxis_title="Time [Minutes]",
        yaxis_title="WIP [Products]",
    )

    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))
    fig.write_html(
        os.path.join(os.getcwd(), "plots", "WIP_per_resource.html"),
        auto_open=not return_html,
    )

    if return_html:
        return pio.to_html(fig, full_html=True)
    if return_image:
        image_path = os.path.join(os.getcwd(), "plots", "WIP_per_resource.png")
        fig.write_image(image_path)
        return image_path


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

    if post_processor.get_primitive_types():
        print("\n------------- WIP per Primitive -------------\n")
        print(post_processor.df_aggregated_primitive_WIP)

    print("\n------------- Throughput time -------------\n")
    print(post_processor.df_aggregated_throughput_time)

    print("\n------------- Resource states -------------\n")

    print(
        post_processor.df_aggregated_resource_states.copy().set_index(
            ["Resource", "Time_type"]
        )
    )
