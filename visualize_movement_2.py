import json
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Rectangle, Circle
from io import StringIO
import numpy as np

# def visualize_production_flow(production_system_desc: dict, event_log_df_orig: pd.DataFrame):

#     event_log_df = event_log_df_orig.copy()  # Work on a copy

#     # --- 1. Preprocessing and Data Structures ---
#     entity_locations = {}
#     resource_types = {}  # To distinguish machines from transporters

#     for r_type in ["source_data", "sink_data", "resource_data"]:
#         for entity in production_system_desc.get(r_type, []):
#             entity_locations[entity["ID"]] = np.array(entity["location"])
#             if r_type == "resource_data":
#                 if (
#                     "tp" in entity["process_ids"]
#                 ):  # Heuristic: if it can do 'tp', it's a transporter
#                     resource_types[entity["ID"]] = "transporter"
#                 else:
#                     resource_types[entity["ID"]] = "machine"  # or processing resource

#     # Initialize states
#     # Resource states: {res_id: {'status': 'idle'/'processing'/'setup'/'moving',
#     #                            'product': prod_id, 'target_loc_id': loc_id,
#     #                            'current_pos': [x,y], 'move_start_time': t, 'move_end_time': t}}
#     resource_states = {}
#     for res_id, loc in entity_locations.items():
#         if res_id in resource_types:  # Only for resources
#             resource_states[res_id] = {
#                 "status": "idle",
#                 "product": None,
#                 "target_loc_id": None,
#                 "current_pos": np.array(loc),  # Initial static position
#                 "move_start_time": 0,
#                 "move_end_time": 0,
#                 "activity": None,  # e.g. 'p1', 'S1', 'tp'
#             }

#     # Product states: {prod_id: {'location_id': entity_id, 'status': 'at_source'/'queued'/'processing'/'on_transport'/'at_sink', 'type': 'product1'/'product2'}}
#     product_states = {}
#     active_products = (
#         {}
#     )  # {prod_id: {'artist': Circle_object, 'text_artist': Text_object}}

#     unique_times = sorted(event_log_df["Time"].unique())
#     time_to_events_map = {time: group for time, group in event_log_df.groupby("Time")}

#     # --- 2. Matplotlib Setup ---
#     fig, ax = plt.subplots(figsize=(12, 8))

#     # Colors
#     colors = {
#         "source": "lightgreen",
#         "sink": "lightcoral",
#         "machine_idle": "lightblue",
#         "machine_processing": "orange",
#         "machine_setup": "lightyellow",
#         "transporter_idle": "grey",
#         "transporter_moving": "darkgrey",
#         "product1": "blue",
#         "product2": "red",
#         "dependency_worker": "magenta",
#     }

#     # --- 3. Animation Update Function ---
#     def update_frame(time_idx):
#         ax.clear()
#         current_time = unique_times[time_idx]

#         # Process events up to and including current_time
#         # This means iterating through events at the current_time step
#         if current_time in time_to_events_map:
#             events = time_to_events_map[current_time]
#             for _, event in events.iterrows():
#                 res_id = event["Resource"]
#                 activity = event["Activity"]
#                 state_type = event["State Type"]
#                 state = event["State"]  # e.g., p1, S1, tp
#                 prod_id = (
#                     event["Product"]
#                     if pd.notna(event["Product"]) and event["Product"] != "nan"
#                     else None
#                 )

#                 # Update resource_states and product_states based on event
#                 if res_id in resource_states:  # It's a machine or transporter
#                     current_res_state = resource_states[res_id]
#                     current_res_state["activity"] = state  # Update activity regardless

#                     if state_type == "Source" and activity == "created product":
#                         prod_type_from_system = "product1"  # Default
#                         for s in production_system_desc["source_data"]:
#                             if s["ID"] == res_id:
#                                 prod_type_from_system = s["product_type"]
#                                 break
#                         product_states[prod_id] = {
#                             "location_id": res_id,
#                             "status": "at_source",
#                             "type": prod_type_from_system,
#                             "current_pos": np.array(entity_locations[res_id]),
#                         }
#                         active_products[prod_id] = {"artist": None, "text_artist": None}

#                     elif state_type == "Transport":
#                         if activity == "start state":
#                             current_res_state["status"] = "moving"
#                             current_res_state["target_loc_id"] = event[
#                                 "Target location"
#                             ]
#                             current_res_state["move_start_time"] = event["Time"]
#                             current_res_state["move_end_time"] = event[
#                                 "Expected End Time"
#                             ]

#                             # If carrying a product (not 'Empty Transport' == 'False' or if prod_id is a product)
#                             empty_transport_str = str(event["Empty Transport"]).lower()
#                             is_carrying_product = (empty_transport_str == "false") or (
#                                 prod_id and "dependency" not in prod_id.lower()
#                             )

#                             if is_carrying_product and prod_id in product_states:
#                                 current_res_state["product"] = prod_id
#                                 product_states[prod_id]["status"] = "on_transport"
#                                 product_states[prod_id][
#                                     "location_id"
#                                 ] = res_id  # Product is with the transporter
#                             else:  # Moving empty or for dependency
#                                 current_res_state["product"] = (
#                                     prod_id
#                                     if "dependency" in str(prod_id).lower()
#                                     else None
#                                 )

#                         elif activity == "end state":
#                             current_res_state["status"] = (
#                                 "idle"  # Becomes idle at destination
#                             )
#                             # Update actual position to target
#                             if event["Target location"] in entity_locations:
#                                 current_res_state["current_pos"] = np.array(
#                                     entity_locations[event["Target location"]]
#                                 )

#                             carried_prod = current_res_state["product"]
#                             if (
#                                 carried_prod
#                                 and carried_prod in product_states
#                                 and "dependency" not in carried_prod.lower()
#                             ):
#                                 target_loc_id = event["Target location"]
#                                 product_states[carried_prod][
#                                     "location_id"
#                                 ] = target_loc_id
#                                 if (
#                                     target_loc_id in resource_types
#                                     and resource_types[target_loc_id] == "machine"
#                                 ):
#                                     product_states[carried_prod][
#                                         "status"
#                                     ] = "at_machine_input"  # Or queued
#                                 elif target_loc_id.startswith("sink"):
#                                     product_states[carried_prod]["status"] = "at_sink"
#                                 else:  # e.g. arrived at another source to pick up etc.
#                                     product_states[carried_prod][
#                                         "status"
#                                     ] = "at_location"
#                                 product_states[carried_prod]["current_pos"] = np.array(
#                                     entity_locations[target_loc_id]
#                                 )
#                             current_res_state["product"] = None  # No longer carrying

#                     elif state_type == "Production" or state_type == "Setup":
#                         if activity == "start state":
#                             current_res_state["status"] = (
#                                 "processing" if state_type == "Production" else "setup"
#                             )
#                             if prod_id and prod_id in product_states:
#                                 current_res_state["product"] = prod_id
#                                 product_states[prod_id]["status"] = "processing"
#                                 product_states[prod_id]["location_id"] = res_id
#                         elif activity == "end state":
#                             current_res_state["status"] = "idle"
#                             if (
#                                 current_res_state["product"]
#                                 and current_res_state["product"] in product_states
#                             ):
#                                 finished_prod_id = current_res_state["product"]
#                                 product_states[finished_prod_id][
#                                     "status"
#                                 ] = "at_machine_output"  # Ready for pickup
#                             current_res_state["product"] = None

#                     elif (
#                         state_type == "Dependency" and state == "Production"
#                     ):  # Worker involved in dependency
#                         # The 'Resource' (e.g. worker) is now tied to the 'Requesting Item' (e.g. machine)
#                         # For visualization, worker moves to the machine and stays there.
#                         requesting_machine_id = event["Requesting Item"]
#                         if activity == "start state":
#                             current_res_state["status"] = "dependency_assisting"
#                             current_res_state["product"] = (
#                                 f"dep_{requesting_machine_id}"  # Mark worker as busy with dependency
#                             )
#                             # Worker should have already moved if separate transport events were logged.
#                             # If not, we assume it's at the machine.
#                             if requesting_machine_id in entity_locations:
#                                 current_res_state["current_pos"] = np.array(
#                                     entity_locations[requesting_machine_id]
#                                 )
#                         elif activity == "end state":
#                             current_res_state["status"] = "idle"
#                             current_res_state["product"] = None
#                             # Worker might move back or to next task based on subsequent events.

#         # Interpolate positions for moving transporters
#         for res_id, state in resource_states.items():
#             if (
#                 state["status"] == "moving"
#                 and state["target_loc_id"] in entity_locations
#             ):
#                 start_pos = (
#                     np.array(
#                         entity_locations[
#                             event_log_df[
#                                 (event_log_df["Resource"] == res_id)
#                                 & (
#                                     event_log_df["Target location"]
#                                     == state["target_loc_id"]
#                                 )
#                                 & (event_log_df["Activity"] == "start state")
#                                 & (event_log_df["Time"] == state["move_start_time"])
#                             ]["Origin location"].iloc[0]
#                         ]
#                     )
#                     if state["move_start_time"] > 0
#                     else state["current_pos"]
#                 )

#                 target_pos = np.array(entity_locations[state["target_loc_id"]])

#                 if state["move_end_time"] > state["move_start_time"]:
#                     progress = (current_time - state["move_start_time"]) / (
#                         state["move_end_time"] - state["move_start_time"]
#                     )
#                     progress = min(max(progress, 0), 1)  # Clamp between 0 and 1
#                     state["current_pos"] = (
#                         start_pos + (target_pos - start_pos) * progress
#                     )
#                 else:  # Instantaneous or already arrived
#                     state["current_pos"] = target_pos

#                 # If transporter is carrying a product, update product's position
#                 if (
#                     state["product"]
#                     and state["product"] in product_states
#                     and "dependency" not in state["product"].lower()
#                 ):
#                     product_states[state["product"]]["current_pos"] = state[
#                         "current_pos"
#                     ]

#         # --- 4. Drawing ---
#         # Draw static entities (Sources, Sinks, Machine locations)
#         for sid, loc in entity_locations.items():
#             if sid.startswith("source"):
#                 ax.add_patch(
#                     Rectangle(
#                         (loc[0] - 0.3, loc[1] - 0.3),
#                         0.6,
#                         0.6,
#                         color=colors["source"],
#                         alpha=0.7,
#                     )
#                 )
#                 ax.text(loc[0], loc[1], sid, ha="center", va="center", fontsize=8)
#             elif sid.startswith("sink"):
#                 ax.add_patch(
#                     Rectangle(
#                         (loc[0] - 0.3, loc[1] - 0.3),
#                         0.6,
#                         0.6,
#                         color=colors["sink"],
#                         alpha=0.7,
#                     )
#                 )
#                 ax.text(loc[0], loc[1], sid, ha="center", va="center", fontsize=8)
#             elif (
#                 sid in resource_types and resource_types[sid] == "machine"
#             ):  # Machine base location
#                 r_state = resource_states[sid]
#                 color = colors["machine_idle"]
#                 if r_state["status"] == "processing":
#                     color = colors["machine_processing"]
#                 elif r_state["status"] == "setup":
#                     color = colors["machine_setup"]

#                 ax.add_patch(
#                     Rectangle(
#                         (loc[0] - 0.4, loc[1] - 0.4),
#                         0.8,
#                         0.8,
#                         color=color,
#                         alpha=0.7,
#                         ec="black",
#                     )
#                 )
#                 info_text = f"{sid}\n{r_state['status']}"
#                 if r_state["product"]:
#                     info_text += f"\n({r_state['product'][:10]})"  # Show product ID being processed
#                 ax.text(loc[0], loc[1], info_text, ha="center", va="center", fontsize=7)

#         # Draw dynamic entities (Transporters and Products)
#         # Transporters
#         for res_id, state in resource_states.items():
#             if res_id in resource_types and resource_types[res_id] == "transporter":
#                 pos = state["current_pos"]
#                 color = colors["transporter_idle"]
#                 if state["status"] == "moving":
#                     color = colors["transporter_moving"]
#                 elif state["status"] == "dependency_assisting":
#                     color = colors["dependency_worker"]

#                 # Use a different shape for transporters, e.g., a diamond or smaller rectangle
#                 # For simplicity, using a slightly different rectangle
#                 ax.add_patch(
#                     Rectangle(
#                         (pos[0] - 0.2, pos[1] - 0.2),
#                         0.4,
#                         0.4,
#                         color=color,
#                         alpha=0.9,
#                         ec="black",
#                     )
#                 )
#                 label = res_id
#                 if (
#                     state["product"]
#                     and "dependency" not in state["product"].lower()
#                     and state["product"] in product_states
#                 ):
#                     label += f"\n({state['product'][:6]})"  # Show product being carried
#                 elif state["product"] and "dependency" in state["product"].lower():
#                     label += f"\n(Dep)"  # Show dependency task
#                 ax.text(pos[0], pos[1], label, ha="center", va="center", fontsize=6)

#         # Products
#         # Clean up artists for products that might have been removed or changed
#         for prod_id in list(active_products.keys()):  # Iterate over a copy of keys
#             if (
#                 prod_id not in product_states
#                 or product_states[prod_id]["status"] == "at_sink"
#             ):
#                 if (
#                     active_products[prod_id]["artist"]
#                     and active_products[prod_id]["artist"] in ax.patches
#                 ):
#                     active_products[prod_id]["artist"].remove()
#                 if (
#                     active_products[prod_id]["text_artist"]
#                     and active_products[prod_id]["text_artist"] in ax.texts
#                 ):
#                     active_products[prod_id]["text_artist"].remove()
#                 del active_products[prod_id]
#                 if (
#                     prod_id in product_states
#                     and product_states[prod_id]["status"] == "at_sink"
#                 ):
#                     del product_states[prod_id]  # remove from tracking
#                 continue  # Skip drawing if sunk

#             p_state = product_states[prod_id]

#             # Determine product position
#             if p_state["status"] == "on_transport":
#                 # Position is already updated by transporter logic, use p_state['current_pos']
#                 prod_pos = p_state["current_pos"] + np.array(
#                     [0.1, 0.1]
#                 )  # Offset slightly from transporter center
#             elif p_state["location_id"] in entity_locations:
#                 # Queued at machine input/output, or at source
#                 base_loc = np.array(entity_locations[p_state["location_id"]])
#                 offset = np.array([0, -0.5])  # Default for input queue / source
#                 if p_state["status"] == "at_machine_output":
#                     offset = np.array([0, 0.5])  # For output queue
#                 elif p_state["status"] == "processing":  # Centered on machine
#                     offset = np.array([0, 0])
#                 prod_pos = base_loc + offset
#                 p_state["current_pos"] = prod_pos  # Update current_pos for consistency
#             else:  # Should not happen if logic is correct
#                 continue

#             prod_color = colors.get(
#                 p_state["type"], "purple"
#             )  # Default color if type not in map

#             # Remove old artist before adding new one to avoid duplicates if not clearing fully
#             if (
#                 active_products[prod_id]["artist"]
#                 and active_products[prod_id]["artist"] in ax.patches
#             ):
#                 active_products[prod_id]["artist"].remove()
#             if (
#                 active_products[prod_id]["text_artist"]
#                 and active_products[prod_id]["text_artist"] in ax.texts
#             ):
#                 active_products[prod_id]["text_artist"].remove()

#             circle = Circle(prod_pos, 0.15, color=prod_color, alpha=0.8, zorder=10)
#             ax.add_patch(circle)
#             active_products[prod_id]["artist"] = circle

#             text = ax.text(
#                 prod_pos[0],
#                 prod_pos[1],
#                 prod_id.split("_")[-1],
#                 ha="center",
#                 va="center",
#                 fontsize=6,
#                 color="white",
#                 zorder=11,
#             )
#             active_products[prod_id]["text_artist"] = text

#         # Set plot limits and labels
#         all_x = [loc[0] for loc in entity_locations.values()]
#         all_y = [loc[1] for loc in entity_locations.values()]
#         ax.set_xlim(min(all_x) - 1, max(all_x) + 1)
#         ax.set_ylim(min(all_y) - 2, max(all_y) + 2)  # More y-space for queue viz
#         ax.set_title(f"Production Flow - Time: {current_time:.2f}")
#         ax.set_xlabel("X Coordinate")
#         ax.set_ylabel("Y Coordinate")
#         ax.set_aspect("equal", adjustable="box")
#         plt.tight_layout()

#         return ax.patches + ax.texts  # Return all artists to be redrawn

#     # --- 5. Create and Run Animation ---
#     # The interval is the delay between frames in milliseconds.
#     # Faster for many events, slower for fewer.
#     ani = animation.FuncAnimation(
#         fig,
#         update_frame,
#         frames=len(unique_times),
#         interval=50,
#         repeat=False,
#         blit=False,
#     )  # blit=False often more stable

#     plt.show()
#     # To save the animation, you might need ffmpeg or imagemagick installed:
#     ani.save("production_flow.mp4", writer='ffmpeg', fps=5)
#     # ani.save("production_flow.gif", writer='imagemagick', fps=5)


def visualize_production_flow(
    production_system_desc: dict, event_log_df_orig: pd.DataFrame
):

    event_log_df = event_log_df_orig.copy()

    entity_locations = {}
    resource_types = {}

    for r_type in ["source_data", "sink_data", "resource_data"]:
        for entity in production_system_desc.get(r_type, []):
            entity_locations[entity["ID"]] = np.array(entity["location"])
            if r_type == "resource_data":
                if "tp" in entity.get("process_ids", []):
                    resource_types[entity["ID"]] = "transporter"
                else:
                    resource_types[entity["ID"]] = "machine"

    resource_states = {}
    for res_id, loc in entity_locations.items():
        if res_id in resource_types:
            resource_states[res_id] = {
                "status": "idle",
                "product": None,
                "target_loc_id": None,
                "current_pos": np.array(loc),
                "move_start_time": 0,
                "move_end_time": 0,
                "activity": None,
            }

    product_states = {}
    active_products = {}

    unique_times = sorted(event_log_df["Time"].unique())
    time_to_events_map = {time: group for time, group in event_log_df.groupby("Time")}

    fig, ax = plt.subplots(figsize=(12, 8))
    colors = {
        "source": "lightgreen",
        "sink": "lightcoral",
        "machine_idle": "lightblue",
        "machine_processing": "orange",
        "machine_setup": "lightyellow",
        "transporter_idle": "grey",
        "transporter_moving": "darkgrey",
        "product1": "blue",
        "product2": "red",
        "dependency_worker": "magenta",
    }

    def update_frame(time_idx):
        ax.clear()
        current_time = unique_times[time_idx]

        if current_time in time_to_events_map:
            events = time_to_events_map[current_time]
            for _, event in events.iterrows():
                res_id = event["Resource"]
                activity = event["Activity"]
                state_type = event["State Type"]
                state_event_val = event[
                    "State"
                ]  # Renamed to avoid conflict with 'state' dict
                prod_id = event["Product"] if event["Product"] != "nan" else None

                if res_id in resource_states:
                    current_res_state = resource_states[res_id]
                    current_res_state["activity"] = state_event_val

                    if state_type == "Source" and activity == "created product":
                        prod_type = "product1"  # Default
                        for s_data in production_system_desc.get("source_data", []):
                            if s_data["ID"] == res_id:
                                prod_type = s_data["product_type"]
                                break
                        product_states[prod_id] = {
                            "location_id": res_id,
                            "status": "at_source",
                            "type": prod_type,
                            "current_pos": np.array(entity_locations[res_id]),
                        }
                        active_products[prod_id] = {"artist": None, "text_artist": None}

                    elif state_type == "Transport":
                        if activity == "start state":
                            current_res_state["status"] = "moving"
                            current_res_state["target_loc_id"] = event[
                                "Target location"
                            ]
                            current_res_state["move_start_time"] = event["Time"]
                            current_res_state["move_end_time"] = event[
                                "Expected End Time"
                            ]

                            empty_transport_str = str(event["Empty Transport"]).lower()

                            if (
                                prod_id and "dependency" in str(prod_id).lower()
                            ):  # Moving for a dependency task
                                current_res_state["product"] = prod_id
                            elif (
                                empty_transport_str == "false"
                                and prod_id
                                and prod_id in product_states
                            ):  # Carrying product
                                current_res_state["product"] = prod_id
                                product_states[prod_id]["status"] = "on_transport"
                                product_states[prod_id]["location_id"] = res_id
                            else:  # Moving empty
                                current_res_state["product"] = None

                        elif activity == "end state":
                            current_res_state["status"] = "idle"
                            if event["Target location"] in entity_locations:
                                current_res_state["current_pos"] = np.array(
                                    entity_locations[event["Target location"]]
                                )

                            carried_prod = current_res_state[
                                "product"
                            ]  # Product it *was* carrying or task it *was* on
                            if (
                                carried_prod
                                and carried_prod in product_states
                                and not ("dependency" in str(carried_prod).lower())
                            ):
                                target_loc_id = event["Target location"]
                                product_states[carried_prod][
                                    "location_id"
                                ] = target_loc_id
                                if (
                                    target_loc_id in resource_types
                                    and resource_types[target_loc_id] == "machine"
                                ):
                                    product_states[carried_prod][
                                        "status"
                                    ] = "at_machine_input"
                                elif target_loc_id.startswith("sink"):
                                    product_states[carried_prod]["status"] = "at_sink"
                                else:
                                    product_states[carried_prod][
                                        "status"
                                    ] = "at_location"
                                product_states[carried_prod]["current_pos"] = np.array(
                                    entity_locations[target_loc_id]
                                )
                            current_res_state["product"] = (
                                None  # Clear product/task from transporter
                            )

                    elif state_type == "Production" or state_type == "Setup":
                        if activity == "start state":
                            current_res_state["status"] = (
                                "processing" if state_type == "Production" else "setup"
                            )
                            if prod_id and prod_id in product_states:
                                current_res_state["product"] = prod_id
                                product_states[prod_id]["status"] = "processing"
                                product_states[prod_id]["location_id"] = res_id
                        elif activity == "end state":
                            current_res_state["status"] = "idle"
                            if (
                                current_res_state["product"]
                                and current_res_state["product"] in product_states
                            ):
                                product_states[current_res_state["product"]][
                                    "status"
                                ] = "at_machine_output"
                            current_res_state["product"] = None

                    elif (
                        state_type == "Dependency" and state_event_val == "Production"
                    ):  # Matches your event log structure
                        requesting_machine_id = event["Requesting Item"]
                        if activity == "start state":
                            current_res_state["status"] = "dependency_assisting"
                            current_res_state["product"] = (
                                f"dep_{requesting_machine_id}"  # Mark worker with specific assist task
                            )
                            if (
                                requesting_machine_id in entity_locations
                            ):  # Should be at machine
                                current_res_state["current_pos"] = np.array(
                                    entity_locations[requesting_machine_id]
                                )
                        elif activity == "end state":
                            current_res_state["status"] = "idle"
                            current_res_state["product"] = None  # Clear assist task

        for (
            res_id,
            r_state_dict,
        ) in resource_states.items():  # Renamed 'state' to 'r_state_dict'
            if (
                r_state_dict["status"] == "moving"
                and r_state_dict["target_loc_id"] in entity_locations
            ):
                # Find original origin from an event, tricky if multiple moves, use current_pos as fallback
                origin_events = event_log_df[
                    (event_log_df["Resource"] == res_id)
                    & (event_log_df["Target location"] == r_state_dict["target_loc_id"])
                    & (event_log_df["Activity"] == "start state")
                    & (event_log_df["Time"] == r_state_dict["move_start_time"])
                ]
                start_pos_id = r_state_dict[
                    "current_pos"
                ]  # Default to current if no clear origin event for this segment
                if (
                    not origin_events.empty
                    and origin_events["Origin location"].iloc[0] in entity_locations
                ):
                    start_pos_id = entity_locations[
                        origin_events["Origin location"].iloc[0]
                    ]

                start_pos = np.array(start_pos_id)
                target_pos = np.array(entity_locations[r_state_dict["target_loc_id"]])

                if r_state_dict["move_end_time"] > r_state_dict["move_start_time"]:
                    progress = (current_time - r_state_dict["move_start_time"]) / (
                        r_state_dict["move_end_time"] - r_state_dict["move_start_time"]
                    )
                    progress = min(max(progress, 0), 1)
                    r_state_dict["current_pos"] = (
                        start_pos + (target_pos - start_pos) * progress
                    )
                else:
                    r_state_dict["current_pos"] = target_pos

                if (
                    r_state_dict["product"]
                    and r_state_dict["product"] in product_states
                    and not ("dependency" in str(r_state_dict["product"]).lower())
                ):
                    product_states[r_state_dict["product"]]["current_pos"] = (
                        r_state_dict["current_pos"]
                    )

        # --- 4. Drawing ---
        for sid, loc in entity_locations.items():
            if sid.startswith("source"):
                ax.add_patch(
                    Rectangle(
                        (loc[0] - 0.3, loc[1] - 0.3),
                        0.6,
                        0.6,
                        color=colors["source"],
                        alpha=0.7,
                    )
                )
                ax.text(loc[0], loc[1], sid, ha="center", va="center", fontsize=8)
            elif sid.startswith("sink"):
                ax.add_patch(
                    Rectangle(
                        (loc[0] - 0.3, loc[1] - 0.3),
                        0.6,
                        0.6,
                        color=colors["sink"],
                        alpha=0.7,
                    )
                )
                ax.text(loc[0], loc[1], sid, ha="center", va="center", fontsize=8)
            elif sid in resource_types and resource_types[sid] == "machine":
                r_state_dict = resource_states[sid]
                color = colors["machine_idle"]
                if r_state_dict["status"] == "processing":
                    color = colors["machine_processing"]
                elif r_state_dict["status"] == "setup":
                    color = colors["machine_setup"]
                ax.add_patch(
                    Rectangle(
                        (loc[0] - 0.4, loc[1] - 0.4),
                        0.8,
                        0.8,
                        color=color,
                        alpha=0.7,
                        ec="black",
                    )
                )
                info_text = f"{sid}\n{r_state_dict['status']}"
                if r_state_dict["product"]:
                    info_text += f"\n({str(r_state_dict['product'])[:10]})"
                ax.text(loc[0], loc[1], info_text, ha="center", va="center", fontsize=7)

        for res_id, r_state_dict in resource_states.items():
            if res_id in resource_types and resource_types[res_id] == "transporter":
                base_pos = np.array(r_state_dict["current_pos"])
                current_display_pos = base_pos.copy()
                color = colors["transporter_idle"]
                label = res_id

                if r_state_dict["status"] == "moving":
                    color = colors["transporter_moving"]
                    if r_state_dict["product"]:
                        if (
                            "dependency" in str(r_state_dict["product"]).lower()
                        ):  # e.g. 'worker_dependency'
                            label += f"\n(Task: {str(r_state_dict['product'])[:6]})"
                        elif r_state_dict["product"] in product_states:
                            label += f"\n({str(r_state_dict['product'])[:6]})"

                elif r_state_dict["status"] == "dependency_assisting":
                    color = colors["dependency_worker"]
                    label += f"\n(Assisting)"
                    if r_state_dict["product"] and str(
                        r_state_dict["product"]
                    ).startswith("dep_"):
                        assisted_machine_id = str(r_state_dict["product"]).split(
                            "dep_"
                        )[1]
                        if assisted_machine_id in entity_locations:
                            machine_loc = np.array(
                                entity_locations[assisted_machine_id]
                            )
                            dependency_offset_x = 0.6
                            current_display_pos[0] = (
                                machine_loc[0] - dependency_offset_x
                            )
                            current_display_pos[1] = machine_loc[1]

                # No specific label for "idle" beyond res_id unless product is somehow stuck (should be cleared by events)

                ax.add_patch(
                    Rectangle(
                        (current_display_pos[0] - 0.2, current_display_pos[1] - 0.2),
                        0.4,
                        0.4,
                        color=color,
                        alpha=0.9,
                        ec="black",
                    )
                )
                ax.text(
                    current_display_pos[0],
                    current_display_pos[1],
                    label,
                    ha="center",
                    va="center",
                    fontsize=6,
                )

        for prod_id in list(active_products.keys()):
            if (
                prod_id not in product_states
                or product_states[prod_id]["status"] == "at_sink"
            ):
                if (
                    active_products[prod_id]["artist"]
                    and active_products[prod_id]["artist"] in ax.patches
                ):
                    active_products[prod_id]["artist"].remove()
                if (
                    active_products[prod_id]["text_artist"]
                    and active_products[prod_id]["text_artist"] in ax.texts
                ):
                    active_products[prod_id]["text_artist"].remove()
                if prod_id in active_products:
                    del active_products[prod_id]  # Ensure removal
                if (
                    prod_id in product_states
                    and product_states[prod_id]["status"] == "at_sink"
                ):
                    del product_states[prod_id]
                continue

            p_state = product_states[prod_id]
            prod_pos = np.array([0.0, 0.0])  # Default
            if p_state["status"] == "on_transport":
                prod_pos = p_state["current_pos"] + np.array([0.1, 0.1])
            elif p_state["location_id"] in entity_locations:
                base_loc = np.array(entity_locations[p_state["location_id"]])
                offset = np.array([0, -0.5])
                if p_state["status"] == "at_machine_output":
                    offset = np.array([0, 0.5])
                elif p_state["status"] == "processing":
                    offset = np.array([0, 0])
                prod_pos = base_loc + offset
                p_state["current_pos"] = prod_pos

            prod_color_key = p_state["type"]
            prod_color = colors.get(prod_color_key, "purple")

            if (
                active_products[prod_id]["artist"]
                and active_products[prod_id]["artist"] in ax.patches
            ):
                active_products[prod_id]["artist"].remove()
            if (
                active_products[prod_id]["text_artist"]
                and active_products[prod_id]["text_artist"] in ax.texts
            ):
                active_products[prod_id]["text_artist"].remove()

            circle = Circle(prod_pos, 0.15, color=prod_color, alpha=0.8, zorder=10)
            ax.add_patch(circle)
            active_products[prod_id]["artist"] = circle
            text = ax.text(
                prod_pos[0],
                prod_pos[1],
                prod_id.split("_")[-1],
                ha="center",
                va="center",
                fontsize=6,
                color="white",
                zorder=11,
            )
            active_products[prod_id]["text_artist"] = text

        all_x = [loc[0] for loc in entity_locations.values()]
        all_y = [loc[1] for loc in entity_locations.values()]
        ax.set_xlim(min(all_x) - 1, max(all_x) + 1)
        ax.set_ylim(min(all_y) - 2, max(all_y) + 2)
        ax.set_title(f"Production Flow - Time: {current_time:.2f}")
        ax.set_xlabel("X Coordinate")
        ax.set_ylabel("Y Coordinate")
        ax.set_aspect("equal", adjustable="box")
        plt.tight_layout()
        return ax.patches + ax.texts

    ani = animation.FuncAnimation(
        fig,
        update_frame,
        frames=len(unique_times),
        interval=500,
        repeat=False,
        blit=False,
    )
    plt.show()
    # To save:
    try:
        ani.save("production_flow_dependency.gif", fps=24)
        # print("Animation saved as production_flow_dependency.gif")
        # save as mp4
        # ani.save("production_flow_dependency.mp4", writer="ffmpeg", fps=24)
    except Exception as e:
        print(f"Could not save animation (imagemagick might not be installed or configured): {e}")


if __name__ == "__main__":
    # Example usage
    # Load event log and production system data
    df = pd.read_csv("examples\\20250516-194107.csv")
    # only first 1000 rows
    df = df.iloc[:80]
    with open("examples\\dependency_example_model.json", "r") as f:
        production_system = json.load(f)
    visualize_production_flow(production_system, df)