import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.figure_factory as ff
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))   
    fig.write_html(os.path.join(os.getcwd(), "plots", "throughput_time_distribution.html"), auto_open=True)

def plot_line_balance_kpis(post_processor: post_processing.PostProcessor):
    """
    Plots line balancing key performance indicators (throughput, WIP, and Throughput Time) after total time.

    Args:
        post_processor (post_processing.PostProcessor): Post processor of the simulation.
    """

    df_output = post_processor.get_aggregated_data()
    fig = make_subplots(rows=1, cols=3,
                        specs=[[{"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}]])

    fig.add_trace(go.Indicator(
        mode = "number",
        value = round(np.sum(list(df_output['Throughput']['Output'].values()))),
        title = {"text": "Total Output"},
    ), row=1, col=1)

    fig.add_trace(go.Indicator(
        mode = "number",
        value = round(np.mean(list(df_output['WIP']['WIP'].values()))),
        title = {"text": "Average Work In Progress (WIP)"},
    ), row=1, col=2)

    fig.add_trace(go.Indicator(
        mode = "number",
        value = round(np.mean(list(df_output['Throughput time']['Throughput_time'].values()))),
        title = {"text": "Average Throughput Time"},
    ), row=1, col=3)

    fig.update_layout(
        title_text="Line Balancing KPIs after Total Time",
        annotations=[
            dict(
                x=0.5,
                y=-0.1,
                showarrow=False,
                text="All KPI's are calculated for the steady state production",
                xref="paper",
                yref="paper"
            )
        ]
    )
    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))   
    fig.write_html(os.path.join(os.getcwd(), "plots", "line_balance.html"), auto_open=True)

def plot_oee(post_processor: post_processing.PostProcessor):
    """
    Plots the Overall Equipment Effectiveness (OEE) with Availability, Performance & Quality using the given post_processor.

    Parameters:
    - post_processor: An instance of the post_processing.PostProcessor class.
    """
    df_oee = post_processor.df_oee_production_system    
    fig = make_subplots(rows=1, cols=4,
                        specs=[[{"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}]])

    fig.add_trace(go.Indicator(
        mode = "number",
        value = df_oee['Value'][0],
        title = {"text": "Availability in %"},
    ), row=1, col=1)

    fig.add_trace(go.Indicator(
        mode = "number",
        value = df_oee['Value'][1],
        title = {"text": "Performance in %"},
    ), row=1, col=2)

    fig.add_trace(go.Indicator(
        mode = "number",
        value = df_oee['Value'][2],
        title = {"text": "Quality in %"},
    ), row=1, col=3)

    fig.add_trace(go.Indicator(
        mode = "number",
        value = df_oee['Value'][3],
        title = {"text": "OEE in %"},
    ), row=1, col=4)

    fig.update_layout(
        title_text="Overall Equipment Effectiveness (OEE)",
        annotations=[
            dict(
                x=0.5,
                y=-0.1,
                showarrow=False,
                text="OEE = Availability * Performance * Quality",
                xref="paper",
                yref="paper"
            )
        ]
    )
    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))   
    fig.write_html(os.path.join(os.getcwd(), "plots", "oee.html"), auto_open=True)


def plot_production_flow_rate_per_product(post_processor: post_processing.PostProcessor):
    """
    Plots the production flow rate per product.

    Args:
        post_processor (post_processing.PostProcessor): The post processor object containing the data.
    """
    percentage_df = post_processor.df_production_flow_ratio

    fig = go.Figure(data=[
    go.Bar(name='Production', y=percentage_df['Product_type'], x=percentage_df['Production '], marker_color='steelblue', orientation='h',  text=percentage_df['Production '].round(2), textposition='auto', textangle=-90),
    go.Bar(name='Transport', y=percentage_df['Product_type'], x=percentage_df['Transport '], marker_color='darkseagreen', orientation='h', text=percentage_df['Transport '].round(2),  textposition='auto', textangle=-90),
    go.Bar(name='Idle', y=percentage_df['Product_type'], x=percentage_df['Idle '], marker_color='lightcoral', orientation='h', text=percentage_df['Idle '].round(2),  textposition='auto', textangle=-90)
    ])
    # Change the bar mode
    fig.update_layout(barmode='stack')
    fig.update_xaxes(title_text="Percentage")
    fig.update_layout(
        title_text="Production Flow Rate (PFO) per Product",
        annotations=[
            dict(
                x=0.5,
                y=-0.1,
                showarrow=False,
                text="Time spent of product in Production, Transport and Idle during the whole throughput time",
                xref="paper",
                yref="paper"
            )
        ]
    )
    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))   
    fig.write_html(os.path.join(os.getcwd(), "plots", "production_flow_rate_product_type.html"), auto_open=True)


def plot_boxplot_resource_utilization(post_processor: post_processing.PostProcessor):
    """
    Plots a boxplot to visualize resource utilization per station.

    Args:
        post_processor (post_processing.PostProcessor): The post processor object containing the data.
    """
    df_time_per_state = post_processor.df_aggregated_resource_bucket_states_boxplot
    resources = df_time_per_state['Resource'].unique()
    df_productive_time = df_time_per_state.loc[df_time_per_state['Time_type'] == 'PR']
    fig = go.Figure()

    for resource in resources:
        df_resource = df_productive_time.loc[df_time_per_state['Resource'] == resource]

        if len(df_resource) == 0:
            df_resource = pd.DataFrame({'Resource': [resource], 'percentage': [0]})
        
        fig.add_trace(go.Box(
            y=df_resource['percentage'],
            name=f'{resource}',
            boxmean=True,
        ))

    fig.update_layout(title_text="Utilization per Station", yaxis_title='Percentage', annotations=[
            dict(
                x=0.5,
                y=-0.18,
                showarrow=False,
                text="Dashed Line = Mean & Solid Line = Median, Whiskers = Q1/Q3 +/- 1.5 * IQR(Q3-Q1)",
                xref="paper",
                yref="paper"
            )
        ])
    fig.update_yaxes(range=[0, 100])

    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))   
    fig.write_html(os.path.join(os.getcwd(), "plots", "resource_box_plots.html"), auto_open=True)


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
    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))   
    fig.write_html(os.path.join(os.getcwd(), "plots", "throughput.html"), auto_open=True)

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
    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))   
    fig.write_html(os.path.join(os.getcwd(), "plots", "resource_states.html"), auto_open=True)


def plot_util_WIP_resource(post_processor: post_processing.PostProcessor, normalized: bool=True):
    """
    Plots the time per state of the resources of the simulation.

    Args:
        post_processor (post_processing.PostProcessor): Post processor of the simulation.
        normalized (bool, optional): If True, the time per state is normalized with the total time of the simulation. Defaults to True.
    """
    df_time_per_state = post_processor.df_mean_wip_per_station
    # df_time_per_state.sort_values(by='column_to_sort', inplace=True)
    fig1 = go.Figure()
    df_time_per_state['mean_wip'] = np.maximum(np.ceil(df_time_per_state['mean_wip']), 1)
    fig1.add_trace(go.Bar(name='mean_wip', x=df_time_per_state['Resource'], y=df_time_per_state['mean_wip'], marker_color='purple', yaxis='y2'))

    df_time_per_state2 = post_processor.df_aggregated_resource_bucket_states
    fig2 = go.Figure()
    resources = df_time_per_state2['Resource'].unique()
    for resource in resources:
        df_resource = df_time_per_state2[df_time_per_state2['Resource'] == resource]
        
        df_time_per_state2 = df_time_per_state2[df_time_per_state2['Time_type'] == 'PR']
        fig2.add_trace(go.Box(
            y=df_resource['percentage'],
            name=f'{resource}',
            boxmean=True  # mean and standard deviation
        ))
    fig2.update_xaxes(categoryorder='array', categoryarray=resources)
    fig = make_subplots(rows=2, cols=1)
    for trace in fig1.data:
        fig.add_trace(trace, row=2, col=1)
    for trace in fig2.data:
        fig.add_trace(trace, row=1, col=1)

    fig.update_yaxes(title_text='WIP in #product', row=2, col=1)
    fig.update_yaxes(title_text='Percentage', row=1, col=1)

    fig.update_layout(title='Mean WIP and Utilization per Station', showlegend=False)
    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))   
    fig.write_html(os.path.join(os.getcwd(), "plots", "mean_wip_util_station.html"), auto_open=True)

def plot_transport_utilization_over_time(post_processor: post_processing.PostProcessor):
    """
    Plots the utilization of the transport_agv resource over time.

    Args:
        post_processor (post_processing.PostProcessor): The post processor object containing the data.
    """
    df_time_per_state = post_processor.df_aggregated_resource_bucket_states
    # FIXME: do not use the resource transport_agv here but a list of resource names of transport resources!
    df_agv_pr = df_time_per_state[(df_time_per_state['Time_type'] == 'PR') & (df_time_per_state['Resource'] == 'transport_agv')]
    fig = go.Figure(data=go.Scatter(x=df_agv_pr['Time'], y=df_agv_pr['percentage'], mode='lines', name='PR'))

    fig.update_layout(title='AGV Utilization Over Time', xaxis_title='Time in Minutes', yaxis_title='Percentage')

    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))   
    fig.write_html(os.path.join(os.getcwd(), "plots", "Transport_utilization_over_time.html"), auto_open=True)


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

    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))   
    fig.write_html(os.path.join(os.getcwd(), "plots", "WIP_with_range.html"), auto_open=True)

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

    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))   
    fig.write_html(os.path.join(os.getcwd(), "plots", "WIP.html"), auto_open=True)

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

    if not os.path.exists(os.path.join(os.getcwd(), "plots")):
        os.makedirs(os.path.join(os.getcwd(), "plots"))   
    fig.write_html(os.path.join(os.getcwd(), "plots", "WIP_per_resource.html"), auto_open=True)

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
