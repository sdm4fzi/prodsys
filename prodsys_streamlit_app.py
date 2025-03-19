import json
import os
import time
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Any
import shutil
import tempfile
import backoff

st.set_page_config(page_title="Optimization Results Viewer", layout="wide")

# Initialize session state for UI controls
if "show_individual" not in st.session_state:
    st.session_state.show_individual = False
if "show_raw" not in st.session_state:
    st.session_state.show_raw = False
if "last_update_time" not in st.session_state:
    st.session_state.last_update_time = time.time()


# Enhanced function to load optimization results with retries and safe reading
@backoff.on_exception(
    backoff.expo, 
    (IOError, json.JSONDecodeError, FileNotFoundError, PermissionError),
    max_tries=5,  # Increased from 3
    max_time=30,  # Increased from 10
    jitter=None
)
def load_optimization_results(file_path: str) -> Dict:
    """
    Load optimization results from JSON file with enhanced error handling
    for cases when the file is being written to or temporarily unavailable.
    """
    try:
        # Check if file exists before attempting to read
        if not os.path.exists(file_path):
            st.warning(f"File not found: {file_path}, will retry...")
            time.sleep(2)  # Wait a bit before potential retry
            if "last_valid_data" in st.session_state and st.session_state.last_valid_data:
                return st.session_state.last_valid_data
            return {}
            
        # Create a temporary file to avoid reading partially written files
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name

        # Multiple attempts to copy the file
        for attempt in range(3):
            try:
                shutil.copy2(file_path, temp_path)
                break  # Success, exit loop
            except (IOError, PermissionError) as e:
                if attempt < 2:  # Not the last attempt
                    time.sleep(1 + attempt)  # Increasing sleep time
                    continue
                else:  # Last attempt failed
                    st.warning(
                        f"Could not make a copy of the optimization file after 3 attempts: {e}. Trying direct read."
                    )
                    # If all copy attempts fail, try direct read as fallback
                    try:
                        with open(file_path, "r") as f:
                            data = json.load(f)
                        # Store valid data in session state
                        st.session_state.last_valid_data = data
                        return data
                    except Exception as direct_read_error:
                        st.warning(f"Direct read also failed: {direct_read_error}")
                        if "last_valid_data" in st.session_state and st.session_state.last_valid_data:
                            return st.session_state.last_valid_data
                        raise

        # Read from temp file
        try:
            with open(temp_path, "r") as f:
                data = json.load(f)
            # Store successful data in session state for fallback
            st.session_state.last_valid_data = data
            # Clean up temp file after successful read
            os.unlink(temp_path)
            return data
        except Exception as e:
            try:
                os.unlink(temp_path)  # Ensure we clean up even on error
            except:
                pass  # Ignore errors during cleanup
            
            # Provide detailed error message
            st.warning(f"Error reading from temp file: {e}")
            
            # Fallback to last valid data if available
            if "last_valid_data" in st.session_state and st.session_state.last_valid_data:
                st.info("Using last successfully loaded data while waiting for file to become readable...")
                return st.session_state.last_valid_data
            
            # Rethrow to let backoff retry
            raise e

    except FileNotFoundError:
        st.warning(f"File not found: {file_path}")
        if "last_valid_data" in st.session_state and st.session_state.last_valid_data:
            st.info("Using last successfully loaded data...")
            return st.session_state.last_valid_data
        return {}
    except json.JSONDecodeError as e:
        st.warning(
            f"The optimization file appears to be in the middle of an update. Will retry on next refresh. Error: {e}"
        )
        if "last_valid_data" in st.session_state and st.session_state.last_valid_data:
            st.info("Using last successfully loaded data while waiting for file to become readable...")
            return st.session_state.last_valid_data
        return {}
    except PermissionError:
        st.error(f"Permission denied when accessing: {file_path}")
        st.info("Please check if you have the necessary permissions to access this file/directory.")
        if "last_valid_data" in st.session_state and st.session_state.last_valid_data:
            st.info("Using last successfully loaded data...")
            return st.session_state.last_valid_data
        return {}
    except Exception as e:
        st.error(f"Error loading file: {str(e)}")
        if "last_valid_data" in st.session_state and st.session_state.last_valid_data:
            st.info("Using last successfully loaded data...")
            return st.session_state.last_valid_data
        return {}


# Process results into a DataFrame
def process_results(results: Dict) -> pd.DataFrame:
    """Process optimization results into a flat DataFrame"""
    data = []

    for gen_idx, fitness_entries in results.items():
        for adapter_id, fitness_data in fitness_entries.items():
            # Basic data
            entry = {
                "generation": gen_idx,
                "adapter_id": adapter_id,
                "agg_fitness": fitness_data.get("agg_fitness", 0),
                "time_stamp": fitness_data.get("time_stamp", 0),
                "hash": fitness_data.get("hash", ""),
            }

            # Process individual fitness components
            fitness_values = fitness_data.get("fitness", [])
            objective_names = fitness_data.get("objective_names", [])

            # Map objective names to values, or use index if names aren't available
            if objective_names:
                for name, value in zip(objective_names, fitness_values):
                    entry[f"objective_{name}"] = value
            else:
                for i, value in enumerate(fitness_values):
                    entry[f"objective_{i}"] = value

            data.append(entry)

    return pd.DataFrame(data)


# Main app
def main():
    st.title("Real-Time Optimization Monitor")

    # File selection and auto-reload settings in sidebar (outside refresh loop)
    st.sidebar.header("Settings")
    default_path = os.path.join(os.getcwd(), "optimization_results.json")
    file_path = st.sidebar.text_input(
        "Path to optimization_results.json", value=default_path
    )

    # UI controls (outside refresh loop)
    auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True, key="auto_refresh")
    refresh_interval = st.sidebar.slider(
        "Refresh interval (seconds)", 1, 60, 5, key="refresh_interval"
    )
    st.sidebar.checkbox(
        "Show individual solutions",
        value=st.session_state.show_individual,
        key="show_individual",
        on_change=lambda: setattr(
            st.session_state, "show_individual", st.session_state.show_individual
        ),
    )

    # Create containers for plots
    overview_container = st.container()
    kpi_container = st.container()
    objectives_container = st.container()
    data_table_container = st.container()

    # Function to update visualizations
    def update_visualizations():
        try:
            if os.path.exists(file_path):
                results = load_optimization_results(file_path)
                if not results:  # If empty dict returned due to error
                    return

                # Store the successfully loaded data for fallback in case of future errors
                st.session_state.last_valid_data = results

                df = process_results(results)

                if df.empty:
                    with overview_container:
                        st.warning("No data found in the optimization results file.")
                    return

                # Ensure numeric sorting for generation and time_stamp
                df["generation"] = pd.to_numeric(df["generation"], errors="coerce")
                df = df.sort_values(["time_stamp", "generation"])

                st.sidebar.success(
                    f"Loaded {len(df)} data points across {df['generation'].nunique()} generations"
                )

                # Overview stats
                with overview_container:
                    st.header("Overview")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Generations", df["generation"].nunique())
                    with col2:
                        st.metric("Total Solutions", len(df))
                    with col3:
                        st.metric("Best Fitness", round(df["agg_fitness"].max(), 4))

                # KPIs container: two plots for Best Fitness and Average Fitness
                with kpi_container:
                    st.header("KPIs")
                    kpi_view = st.radio(
                        "View KPIs by:",
                        ["Time", "Generation"],
                        horizontal=True,
                        key="kpi_view",
                    )
                    col1, col2 = st.columns(2)

                    if kpi_view == "Time":
                        # Create time buckets and compute aggregates
                        df["time_bucket"] = pd.cut(df["time_stamp"], bins=20)
                        time_stats = (
                            df.groupby("time_bucket", observed=False)["agg_fitness"]
                            .agg(mean="mean", max="max")
                            .reset_index()
                        )
                        time_stats["time_bucket_mid"] = time_stats["time_bucket"].apply(
                            lambda x: x.mid
                        )
                        time_stats = time_stats.sort_values("time_bucket_mid")

                        with col1:
                            fig_best_time = go.Figure()
                            fig_best_time.add_trace(
                                go.Scatter(
                                    x=time_stats["time_bucket_mid"],
                                    y=time_stats["max"],
                                    mode="lines+markers",
                                    name="Best Fitness",
                                )
                            )
                            fig_best_time.update_layout(
                                title="Best Fitness Over Time",
                                xaxis_title="Time (seconds)",
                                yaxis_title="Fitness",
                            )
                            st.plotly_chart(fig_best_time, use_container_width=True)

                        with col2:
                            fig_avg_time = go.Figure()
                            fig_avg_time.add_trace(
                                go.Scatter(
                                    x=time_stats["time_bucket_mid"],
                                    y=time_stats["mean"],
                                    mode="lines+markers",
                                    name="Average Fitness",
                                )
                            )
                            fig_avg_time.update_layout(
                                title="Average Fitness Over Time",
                                xaxis_title="Time (seconds)",
                                yaxis_title="Fitness",
                            )
                            st.plotly_chart(fig_avg_time, use_container_width=True)

                    else:
                        # Generation view: sort by generation
                        best_by_gen = (
                            df.groupby("generation")["agg_fitness"]
                            .max()
                            .reset_index()
                            .sort_values("generation")
                        )
                        avg_by_gen = (
                            df.groupby("generation")["agg_fitness"]
                            .mean()
                            .reset_index()
                            .sort_values("generation")
                        )

                        with col1:
                            # For best fitness, display as a bar chart (one value per generation)
                            fig_best_gen = px.bar(
                                best_by_gen,
                                x="generation",
                                y="agg_fitness",
                                title="Best Fitness by Generation",
                                labels={
                                    "agg_fitness": "Fitness",
                                    "generation": "Generation",
                                },
                            )
                            st.plotly_chart(fig_best_gen, use_container_width=True)

                        with col2:
                            # For average fitness, show a box plot of the distribution per generation
                            fig_avg_gen = px.box(
                                df,
                                x="generation",
                                y="agg_fitness",
                                title="Fitness Distribution by Generation",
                                labels={
                                    "agg_fitness": "Fitness",
                                    "generation": "Generation",
                                },
                            )
                            # Overlay the average fitness as a line
                            fig_avg_gen.add_trace(
                                go.Scatter(
                                    x=avg_by_gen["generation"],
                                    y=avg_by_gen["agg_fitness"],
                                    mode="lines+markers",
                                    name="Average Fitness",
                                    marker_color="red",
                                )
                            )
                            st.plotly_chart(fig_avg_gen, use_container_width=True)

                # Individual objectives - enhanced with better visualizations
                with objectives_container:
                    # Get column names that start with 'objective_'
                    objective_cols = [
                        col for col in df.columns if col.startswith("objective_")
                    ]

                    if objective_cols:
                        st.header("Individual Objectives")

                        # Melt the DataFrame to plot all objectives
                        selected_objectives = st.multiselect(
                            "Select Objectives to Display",
                            options=objective_cols,
                            default=(
                                objective_cols[:3]
                                if len(objective_cols) > 3
                                else objective_cols
                            ),
                        )

                        if selected_objectives:
                            view_by = st.radio(
                                "View by:", ["Time", "Generation"], horizontal=True
                            )

                            if view_by == "Time":
                                # Create time buckets for aggregation
                                df["time_bucket"] = pd.cut(df["time_stamp"], bins=20)
                                
                                # For each objective, create a separate chart
                                for obj in selected_objectives:
                                    st.subheader(f"Objective: {obj.replace('objective_', '')}")
                                    
                                    # Get aggregated data for this objective
                                    obj_data = df.groupby("time_bucket", observed=False).agg({
                                        obj: ["mean", "max", "min"]
                                    }).reset_index()
                                    
                                    obj_data.columns = ["time_bucket", "mean", "max", "min"]
                                    obj_data["time_bucket_mid"] = obj_data["time_bucket"].apply(lambda x: x.mid)
                                    obj_data = obj_data.sort_values("time_bucket_mid")
                                    
                                    # Create 3 columns for different charts of the same objective
                                    col1, col2, col3 = st.columns(3)
                                    
                                    with col1:
                                        # Line chart for trend
                                        fig = go.Figure()
                                        fig.add_trace(
                                            go.Scatter(
                                                x=obj_data["time_bucket_mid"],
                                                y=obj_data["mean"],
                                                mode="lines+markers",
                                                name="Average",
                                                line=dict(color="#1f77b4")
                                            )
                                        )
                                        fig.add_trace(
                                            go.Scatter(
                                                x=obj_data["time_bucket_mid"],
                                                y=obj_data["max"],
                                                mode="lines+markers",
                                                name="Best",
                                                line=dict(color="#ff7f0e")
                                            )
                                        )
                                        fig.update_layout(
                                            title=f"Trend Over Time",
                                            xaxis_title="Time (seconds)",
                                            yaxis_title="Value",
                                            height=300,
                                            margin=dict(l=10, r=10, t=30, b=10)
                                        )
                                        # Individual y-axis scaling
                                        fig.update_yaxes(autorange=True)
                                        st.plotly_chart(fig, use_container_width=True)
                                    
                                    with col2:
                                        # Distribution of values
                                        specific_data = df[[obj, "time_stamp"]].copy()
                                        fig = px.histogram(
                                            specific_data, 
                                            x=obj,
                                            title="Value Distribution",
                                            height=300
                                        )
                                        fig.update_layout(
                                            xaxis_title="Value",
                                            yaxis_title="Count",
                                            margin=dict(l=10, r=10, t=30, b=10)
                                        )
                                        # Individual x-axis scaling
                                        fig.update_xaxes(autorange=True)
                                        st.plotly_chart(fig, use_container_width=True)
                                    
                                    with col3:
                                        # Box plot for statistical view
                                        fig = go.Figure()
                                        fig.add_trace(
                                            go.Box(
                                                y=df[obj],
                                                name=obj.replace("objective_", ""),
                                                boxmean=True
                                            )
                                        )
                                        fig.update_layout(
                                            title="Statistical Distribution",
                                            yaxis_title="Value",
                                            height=300,
                                            margin=dict(l=10, r=10, t=30, b=10)
                                        )
                                        # Individual y-axis scaling
                                        fig.update_yaxes(autorange=True)
                                        st.plotly_chart(fig, use_container_width=True)
                            
                            else:  # Generation view
                                # For each objective, create a separate chart
                                for obj in selected_objectives:
                                    st.subheader(f"Objective: {obj.replace('objective_', '')}")
                                    
                                    # Get aggregated data for this objective
                                    obj_data = df.groupby("generation").agg({
                                        obj: ["mean", "max", "min"]
                                    }).reset_index()
                                    
                                    obj_data.columns = ["generation", "mean", "max", "min"]
                                    obj_data = obj_data.sort_values("generation")
                                    
                                    # Create 3 columns for different charts of the same objective
                                    col1, col2, col3 = st.columns(3)
                                    
                                    with col1:
                                        # Line chart for trend
                                        fig = go.Figure()
                                        fig.add_trace(
                                            go.Scatter(
                                                x=obj_data["generation"],
                                                y=obj_data["mean"],
                                                mode="lines+markers",
                                                name="Average",
                                                line=dict(color="#1f77b4")
                                            )
                                        )
                                        fig.add_trace(
                                            go.Scatter(
                                                x=obj_data["generation"],
                                                y=obj_data["max"],
                                                mode="lines+markers",
                                                name="Best",
                                                line=dict(color="#ff7f0e")
                                            )
                                        )
                                        fig.update_layout(
                                            title=f"Trend By Generation",
                                            xaxis_title="Generation",
                                            yaxis_title="Value",
                                            height=300,
                                            margin=dict(l=10, r=10, t=30, b=10)
                                        )
                                        # Individual y-axis scaling
                                        fig.update_yaxes(autorange=True)
                                        st.plotly_chart(fig, use_container_width=True)
                                    
                                    with col2:
                                        # Box plot by generation
                                        fig = px.box(
                                            df, 
                                            x="generation", 
                                            y=obj,
                                            title="Distribution By Generation",
                                            height=300
                                        )
                                        fig.update_layout(
                                            xaxis_title="Generation",
                                            yaxis_title="Value",
                                            margin=dict(l=10, r=10, t=30, b=10)
                                        )
                                        # Individual y-axis scaling
                                        fig.update_yaxes(autorange=True)
                                        st.plotly_chart(fig, use_container_width=True)
                                    
                                    with col3:
                                        # Violin plot for more detailed distribution
                                        fig = px.violin(
                                            df, 
                                            y=obj, 
                                            box=True,
                                            title="Overall Distribution",
                                            height=300
                                        )
                                        fig.update_layout(
                                            yaxis_title="Value",
                                            margin=dict(l=10, r=10, t=30, b=10)
                                        )
                                        # Individual y-axis scaling
                                        fig.update_yaxes(autorange=True)
                                        st.plotly_chart(fig, use_container_width=True)

                # Raw data table - fix the duplication issue
                with data_table_container:
                    # Simplified raw data display without duplicate controls
                    st.header("Raw Data")
                    if st.checkbox("Show raw data table", value=False):
                        st.dataframe(df)

            else:
                with overview_container:
                    st.error(f"File not found: {file_path}")
                    st.info(
                        "Please verify the file path is correct and the file exists."
                    )

        except PermissionError as e:
            with overview_container:
                st.error(f"Permission denied: {str(e)}")
                st.info(
                    "Please check if you have the necessary permissions to access the data files."
                )
        except Exception as e:
            with overview_container:
                st.error(f"Error loading or processing the file: {str(e)}")

    # Initial visualization update
    update_visualizations()

    # Set up auto-refresh
    if auto_refresh:
        while True:
            # Calculate time since last update
            time_to_wait = max(
                0, refresh_interval - (time.time() - st.session_state.last_update_time)
            )
            with st.sidebar:
                progress_text = "Waiting for refresh..."
                progress_bar = st.progress(0)
                for i in range(int(time_to_wait)):
                    progress_bar.progress((i + 1) / time_to_wait)
                    time.sleep(1)
                progress_bar.empty()
            st.session_state.last_update_time = time.time()
            st.rerun()  # Trigger a full rerun to reload all data


if __name__ == "__main__":
    main()
