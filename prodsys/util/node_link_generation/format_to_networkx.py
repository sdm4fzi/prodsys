import math
import statistics
import networkx as nx
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yaml
import os


class NetworkXGraphGenerator:
    def __init__(self, graph, station_config):
        self.graph = graph
        self.station_config = station_config
        self.G = nx.Graph()
        self.DiG = nx.DiGraph()
        self.G_sim = nx.Graph()
        self.DiG_sim = nx.Graph()

    def generate_nx_graph(self, plot=False) -> (nx.Graph, nx.DiGraph):
        """
        Generate a networkx graph from the graph class.
        :param plot: If True, the graph is plotted.
        :return: The networkx graph and the directed networkx graph.
        """
        # Add nodes to the graph.
        for node_index, node in enumerate(self.graph.nodes): #take the node ids from the prodsys json
            node.node_id = node_index + 1
            if node.node_orientation is not None:
                orientation_deg = node.node_orientation
                orientation_rad = math.radians(orientation_deg)
                if orientation_rad > math.pi:
                    orientation_rad -= 2 * math.pi
                node_orientation = orientation_rad
            else:
                node_orientation = 'None'

            self.G.add_node(node.node_id, pos=node.position, type=node.node_type, orientation=node_orientation)
            self.DiG.add_node(node.node_id, pos=node.position, type=node.node_type, orientation=node_orientation)

        # Add edges to the graph.
        for edge_index, edge in enumerate(self.graph.edges):
            edge.edge_id = edge_index + 1

            # Undirected graph.
            self.G.add_edge(edge.node1.node_id, edge.node2.node_id, type=edge.edge_type, weight=edge.shapely_line.length, capacity=1)

            # Directed graph.
            if edge.direction == '1 -> 2':
                self.DiG.add_edge(edge.node1.node_id, edge.node2.node_id, type=edge.edge_type, weight=edge.shapely_line.length, capacity=1)
            elif edge.direction == '2 -> 1':
                self.DiG.add_edge(edge.node2.node_id, edge.node1.node_id, type=edge.edge_type, weight=edge.shapely_line.length, capacity=1)
            elif edge.direction == 'bi':
                self.DiG.add_edge(edge.node1.node_id, edge.node2.node_id, type=edge.edge_type, weight=edge.shapely_line.length, capacity=1)
                self.DiG.add_edge(edge.node2.node_id, edge.node1.node_id, type=edge.edge_type, weight=edge.shapely_line.length, capacity=1)

        if plot:
            self.plot_nx_graph(self.G)
            self.plot_nx_graph(self.DiG)

        # Save the graph to a file in gml format.
        #path_G = 'NodeEdgeNetworkGeneration/output_files/nx_graph.gml'
        #nx.write_gml(self.G, path_G)
        #path_DiG = 'NodeEdgeNetworkGeneration/output_files/nx_digraph.gml'
        #nx.write_gml(self.DiG, path_DiG)

        # Load the graph from a file in gml format.
        # self.G = nx.read_gml(path_G, destringizer=int)
        # self.DiG = nx.read_gml(path_DiG, destringizer=int)

        return self.G, self.DiG

    def generate_nx_graph_simulation_ifl(self, plot=False):
        """
        Generate a networkx graph from the graph class for the simulation of the IFL.
        """
        # Add nodes to the graph
        for node_index, node in enumerate(self.graph.nodes):
            node.node_id = node_index
            if node.node_type == 'station':
                for station in self.station_config.stations:
                    if node.position == station.station_node:
                        station_id = str(station.station_number)
                        break
                self.G_sim.add_node(node.node_id, coords=(node.position[0], -node.position[1]), station=1, station_id=station_id)
            else:
                self.G_sim.add_node(node.node_id, coords=(node.position[0], -node.position[1]), station=0)

        # Add edges to the graph
        for edge_index, edge in enumerate(self.graph.edges):
            edge.edge_id = edge_index + 1

            # Undirected graph.
            self.G_sim.add_edge(edge.node1.node_id, edge.node2.node_id, weight=edge.shapely_line.length)

            # Directed graph.
            if edge.direction == '1 -> 2':
                self.DiG_sim.add_edge(edge.node1.node_id, edge.node2.node_id, weight=edge.shapely_line.length)
            elif edge.direction == '2 -> 1':
                self.DiG_sim.add_edge(edge.node2.node_id, edge.node1.node_id, weight=edge.shapely_line.length)
            elif edge.direction == 'bi':
                self.DiG_sim.add_edge(edge.node1.node_id, edge.node2.node_id, weight=edge.shapely_line.length)
                self.DiG_sim.add_edge(edge.node2.node_id, edge.node1.node_id, weight=edge.shapely_line.length)

        if plot:
            self.plot_nx_graph(self.G_sim, sim=True)

        # Save the graph to a file in gml format.
        path = 'NodeEdgeNetworkGeneration/output_files/nx_graph_simulation_ifl.gml'
        nx.write_gml(self.G_sim, path)
        path = 'NodeEdgeNetworkGeneration/output_files/nx_digraph_simulation_ifl.gml'
        nx.write_gml(self.DiG_sim, path)

        # Load the graph from a file in gml format.
        # self.G_sim = nx.read_gml(path, destringizer=int)

    def reset_nx_graph(self):
        """
        Reset the networkx graph.
        """
        self.G = nx.Graph()
        self.DiG = nx.DiGraph()
        self.G_sim = nx.Graph()
        self.DiG_sim = nx.Graph()

    def analyze_graph_connectivity(self):
        """
        Analyze the edge connectivity between stations in the graph.
        """
        for graph in [self.G, self.DiG]:
            if graph == self.G:
                print("Graph: G")
            else:
                print()
                print("Graph: DiG")

            station_trajectory_nodes = [node for node, data in graph.nodes(data=True) if data['type'] == 'trajectory']
            #station_buffer_nodes = [node for node, data in graph.nodes(data=True) if data['type'] == 'buffer']
            min_edge_connectivity = float('inf')
            min_node_connectivity = float('inf')
            sum_edge_connectivity = 0
            sum_node_connectivity = 0
            sum_shortest_paths_length = 0
            sum_shortest_paths_nodes = 0
            for i in range(len(station_trajectory_nodes)):
                for j in range(len(station_trajectory_nodes)):
                    if i == j:
                        continue
                    edge_connectivity = nx.edge_connectivity(graph, station_trajectory_nodes[i], station_trajectory_nodes[j])
                    sum_edge_connectivity += edge_connectivity
                    min_edge_connectivity = min(min_edge_connectivity, edge_connectivity)
                    node_connectivity = nx.node_connectivity(graph, station_trajectory_nodes[i], station_trajectory_nodes[j])
                    sum_node_connectivity += node_connectivity
                    min_node_connectivity = min(min_node_connectivity, node_connectivity)
                    sum_shortest_paths_length += nx.shortest_path_length(graph, station_trajectory_nodes[i], station_trajectory_nodes[j], 'weight')
                    sum_shortest_paths_nodes += nx.shortest_path_length(graph, station_trajectory_nodes[i], station_trajectory_nodes[j])

            number_of_connections = len(station_trajectory_nodes) * (len(station_trajectory_nodes) - 1)

            mean_edge_connectivity = sum_edge_connectivity / number_of_connections
            mean_node_connectivity = sum_node_connectivity / number_of_connections
            mean_shortest_paths_length = sum_shortest_paths_length / number_of_connections
            mean_shortest_paths_nodes = sum_shortest_paths_nodes / number_of_connections

            print("Min edge connectivity: " + str(min_edge_connectivity))
            print("Mean edge connectivity: " + str(mean_edge_connectivity))
            print("Min node connectivity: " + str(min_node_connectivity))
            print("Mean node connectivity: " + str(mean_node_connectivity))
            print("Mean shortest paths length: " + str(mean_shortest_paths_length))
            print("Mean shortest paths nodes: " + str(mean_shortest_paths_nodes))

            if graph == self.G:
                algebraic_connectivity = nx.algebraic_connectivity(graph)
                print("Algebraic connectivity: " + str(algebraic_connectivity))

                max_node_degree = max(degree for node, degree in nx.degree(graph))
                print("Max node degree: " + str(max_node_degree))

                mean_node_degree = statistics.mean(degree for node, degree in nx.degree(graph))
                print("Mean node degree: " + str(mean_node_degree))

                mean_node_degree_no_stations = statistics.mean(degree for node, degree in nx.degree(graph) if degree > 1)
                print("Mean node degree (no stations): " + str(mean_node_degree_no_stations))

                number_of_nodes = self.G.number_of_nodes()
                print("Number of nodes: " + str(number_of_nodes))
                number_of_edges = self.G.number_of_edges()
                print("Number of edges: " + str(number_of_edges))

                alpha_index = (number_of_edges - number_of_nodes + 1) / (2 * number_of_nodes - 5)
                print("Alpha index: " + str(alpha_index))
                beta_index = number_of_edges / number_of_nodes
                print("Beta index: " + str(beta_index))
                gamma_index = number_of_edges / (3 * (number_of_nodes - 2))
                print("Gamma index: " + str(gamma_index))

                # Define pandas dataframe.
                df_G = pd.DataFrame(columns=['number_of_nodes', 'number_of_edges',
                                             'min_node_connectivity', 'mean_node_connectivity',
                                             'min_edge_connectivity', 'mean_edge_connectivity',
                                             'algebraic_connectivity', 'alpha_index',
                                             'beta_index', 'gamma_index',
                                             'max_node_degree', 'mean_node_degree',
                                             'mean_node_degree_no_stations',
                                             'sum_shortest_paths_length', 'mean_shortest_paths_length',
                                             'sum_shortest_paths_nodes', 'mean_shortest_paths_nodes'])
                df_G.loc[len(df_G)] = [number_of_nodes, number_of_edges,
                                       min_node_connectivity, mean_node_connectivity,
                                       min_edge_connectivity, mean_edge_connectivity,
                                       algebraic_connectivity, alpha_index,
                                       beta_index, gamma_index,
                                       max_node_degree, mean_node_degree,
                                       mean_node_degree_no_stations,
                                       sum_shortest_paths_length, mean_shortest_paths_length,
                                       sum_shortest_paths_nodes, mean_shortest_paths_nodes]

                histogram = []
                histogram = nx.degree_histogram(graph)
                plt.figure(figsize=(10, 7))
                plt.bar(range(len(histogram)), histogram)
                plt.xlabel('Anzahl Kanten an Knoten / Vernetzungsgrad')
                plt.ylabel('Anzahl Knoten / Häufigkeit')
                plt.title('Histogramm Bidirektional')

            else:
                max_node_degree = max(degree for node, degree in graph.in_degree())
                print("Max node in-degree: " + str(max_node_degree))

                mean_node_degree = statistics.mean(degree for node, degree in graph.in_degree())
                print("Mean node in-degree: " + str(mean_node_degree))

                mean_node_degree_no_stations = statistics.mean(degree for node, degree in graph.in_degree() if degree > 1)
                print("Mean node in-degree (no stations): " + str(mean_node_degree_no_stations))

                # Define pandas dataframe.
                df_DiG = pd.DataFrame(columns=['number_of_nodes', 'number_of_edges',
                                               'min_node_connectivity', 'mean_node_connectivity',
                                               'min_edge_connectivity', 'mean_edge_connectivity',
                                               'algebraic_connectivity', 'alpha_index',
                                               'beta_index', 'gamma_index',
                                               'max_node_degree', 'mean_node_degree',
                                               'mean_node_degree_no_stations',
                                               'sum_shortest_paths_length', 'mean_shortest_paths_length',
                                               'sum_shortest_paths_nodes', 'mean_shortest_paths_nodes'])
                df_DiG.loc[len(df_DiG)] = [number_of_nodes, number_of_edges,
                                           min_node_connectivity, mean_node_connectivity,
                                           min_edge_connectivity, mean_edge_connectivity,
                                           algebraic_connectivity, alpha_index,
                                           beta_index, gamma_index,
                                           max_node_degree, mean_node_degree,
                                           mean_node_degree_no_stations,
                                           sum_shortest_paths_length, mean_shortest_paths_length,
                                           sum_shortest_paths_nodes, mean_shortest_paths_nodes]

                # Calculate in-degrees and out-degrees
                out_degrees = [degree for node, degree in graph.out_degree()]

                # Count the frequencies of each degree
                unique_out_degrees, out_degree_counts = np.unique(out_degrees, return_counts=True)

                # In-degree and out-degree histograms are the same.
                plt.figure(figsize=(10, 7))
                plt.bar(unique_out_degrees, out_degree_counts)
                plt.xlabel('Anzahl Kanten an Knoten / Vernetzungsgrad')
                plt.ylabel('Anzahl Knoten / Häufigkeit')
                plt.title('Histogramm Mixed-direktional')
                plt.show()

            # nx.adjacency_matrix(graph, weight=None)  # nx.adjacency_matrix(graph).toarray()
            # nx.laplacian_matrix(graph).toarray()
            # nx.degree(graph)  # nx.effective_size(graph)

        return df_G, df_DiG

    def dataframe_G(self):
        # Define the directory where the graph is located.
        directory = 'NodeEdgeNetworkGeneration/output_files/metrices_graph_theory'

        for filename in os.listdir(directory):
            # Iterate over all files in the directory.
            if filename.endswith(".csv"):
                # Load graph.
                path = directory + '/' + filename

                # Directed or undirected.
                if path[-7:-4] == 'DiG' or filename == 'df_G.csv':
                    continue
                else:
                    # Load the general dataframe, add the row of the new created dataframe and save it.
                    df_G = pd.read_csv(path)
                    df_G_general = pd.read_csv('NodeEdgeNetworkGeneration/output_files/metrices_graph_theory/df_G.csv')
                    df_G_general = pd.concat([df_G_general, df_G], ignore_index=True)
                    df_G_general.to_csv('NodeEdgeNetworkGeneration/output_files/metrices_graph_theory/df_G.csv', index=False)

    def edges_count_DiG(self):
        # Define the directory where the graph is located.
        directory = 'NodeEdgeNetworkGeneration/output_files/MAPF_simulation'

        for filename in os.listdir(directory):
            # Iterate over all files in the directory.
            if filename.endswith(".gml"):
                # Load graph.
                path = directory + '/' + filename
                g = nx.read_gml(path, destringizer=int)

                # Directed or undirected.
                if path[-11:-4] == 'digraph':
                    continue
                else:
                    # File name. Used for saving the roadmap, the infile and the outfile.
                    splitted_path = path.split('/')
                    splitted_path = splitted_path[-1].split('.')
                    experiment_name = splitted_path[0]
                    experiment_name = experiment_name[:-11]

                    # Layout name.
                    layout_name = experiment_name.split('_')[0] + '_' + experiment_name.split('_')[1]

                    # Edge count digraph.
                    number_of_edges_di = g.number_of_edges()

                    # Format digraph to graph.
                    g = nx.Graph(g)

                    # Edge count graph.
                    number_of_edges_uni = g.number_of_edges()

                    # Ratio of directed edges to undirected edges. Round to 2 decimal places.
                    edges_ratio = round(number_of_edges_di / number_of_edges_uni, 2)

                    df_G = pd.DataFrame(columns=['number_of_edges_uni', 'number_of_edges_di', 'edges_ratio', 'layout_nr', 'concept'])
                    df_G.loc[len(df_G)] = [number_of_edges_uni, number_of_edges_di, edges_ratio, layout_name, experiment_name]

                    # Load the general dataframe, add the row of the new created dataframe and save it.
                    df_G_general = pd.read_csv('NodeEdgeNetworkGeneration/output_files/metrices_graph_theory/df_edge_count_DiG.csv')
                    df_G_general = pd.concat([df_G_general, df_G], ignore_index=True)
                    df_G_general.to_csv('NodeEdgeNetworkGeneration/output_files/metrices_graph_theory/df_edge_count_DiG.csv', index=False)

    def generate_simulation_dataframe(self):
        # Define the directory where the graph is located.
        directory_graph = 'NodeEdgeNetworkGeneration/output_files/Evaluierung/MAPF_simulation'

        for filename in os.listdir(directory_graph):
            # Iterate over all files in the directory.
            if filename.endswith(".gml"):
                # Load graph.
                path = directory_graph + '/' + filename
                g = nx.read_gml(path, destringizer=int)

                # Experiment name.
                splitted_path = path.split('/')
                splitted_path = splitted_path[-1].split('.')
                experiment_name = splitted_path[0]

                # Concept name. Drop Layout.
                concept_name = '_'.join(experiment_name.split('_')[2:])

                # Layout name.
                layout_nr = experiment_name.split('_')[1]

                for i in [0, 1, 2]:
                    # Experiment transportation name.
                    experiment_transportation_name = experiment_name + '_' + str(i)

                    # Load the simulation result.
                    path = 'NodeEdgeNetworkGeneration/output_files/Evaluierung/MAPF_results/results_new_tasks_combined/' + experiment_transportation_name + '_outfile.yaml'

                    # Check if file exists.
                    if os.path.isfile(path):
                        # Load the simulation result.
                        with open(path, 'r') as file:
                            simulation_result = yaml.safe_load(file)

                        # Load the general dataframe, add the row of the new created dataframe and save it.
                        df_G_general = pd.read_csv('NodeEdgeNetworkGeneration/output_files/Evaluierung/MAPF_results/df_mapf_evaluation.csv')

                        # Define the dataframe.
                        df_G = pd.DataFrame(columns=['makespan', 'makespan_normalized', 'cost', 'cost_normalized', 'total_length_paths', 'average_length_edges', 'steps_waiting', 'runtime', 'layout_nr', 'transportation_task', 'concept'])

                        # Get data from the simulation result.
                        cost = simulation_result['statistics']['cost']
                        makespan = simulation_result['statistics']['makespan']
                        runtime = simulation_result['statistics']['runtime']

                        total_length_paths = 0
                        number_of_edges = 0
                        steps_waiting = 0
                        for agent, path in simulation_result['schedule'].items():
                            for index, node in enumerate(path):
                                if index == 0:
                                    continue
                                node_1 = path[index - 1]['v']
                                node_2 = path[index]['v']
                                if node_1 == node_2:
                                    steps_waiting += 1
                                else:
                                    total_length_paths += g.edges[node_1, node_2]['weight']
                                    number_of_edges += 1

                        average_length_edges = total_length_paths / number_of_edges
                        cost_normalized = cost * average_length_edges
                        makespan_normalized = makespan * average_length_edges

                        # Add the data to the dataframe.
                        df_G.loc[len(df_G)] = [makespan, makespan_normalized, cost, cost_normalized, total_length_paths, average_length_edges, steps_waiting, runtime, layout_nr, i, concept_name]

                        # Add the row of the new created dataframe.
                        df_G_general = pd.concat([df_G_general, df_G], ignore_index=True)

                        # Save the dataframe.
                        df_G_general.to_csv('NodeEdgeNetworkGeneration/output_files/Evaluierung/MAPF_results/df_mapf_evaluation.csv', index=False)

                    else:
                        # Load the general dataframe, add the row of the new created dataframe and save it.
                        df_G_general = pd.read_csv('NodeEdgeNetworkGeneration/output_files/Evaluierung/MAPF_results/df_mapf_evaluation.csv')

                        # Define the dataframe.
                        df_G = pd.DataFrame(columns=['makespan', 'makespan_normalized', 'cost', 'cost_normalized', 'total_length_paths', 'average_length_edges', 'steps_waiting', 'runtime', 'layout_nr', 'transportation_task', 'concept'])

                        # Add the data to the dataframe.
                        df_G.loc[len(df_G)] = [None, None, None, None, None, None, None, None, layout_nr, i, concept_name]

                        # Add the row of the new created dataframe.
                        df_G_general = pd.concat([df_G_general, df_G], ignore_index=True)

                        # Save the dataframe.
                        df_G_general.to_csv('NodeEdgeNetworkGeneration/output_files/Evaluierung/MAPF_results/df_mapf_evaluation.csv', index=False)

    def plot_nx_graph(self, G, sim=False):
        """
        Plot the networkx graph.
        """
        plt.figure(figsize=(13, 13))
        if sim:
            pos = nx.get_node_attributes(G, 'coords')
        else:
            pos = nx.get_node_attributes(G, 'pos')
        # nx.draw(G, pos, with_labels=True, width=2, arrowsize=24)
        nx.draw(G, pos, with_labels=False, width=1, arrowsize=12)
        plt.show()
