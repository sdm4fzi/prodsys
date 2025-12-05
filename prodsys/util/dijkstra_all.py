from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import heapq
from pathfinding.core.graph import GraphNode


class DijkstraAllPaths:
    """
    Efficient Dijkstra implementation that explores all nodes from an origin
    and caches all shortest paths. This allows O(1) path retrieval after the
    initial exploration.
    """
    
    def __init__(self):
        """
        Initializes the Dijkstra path finder with empty caches.
        """
        # Cache: (process_id, origin_id) -> Dict[target_id, List[GraphNode]]
        self._path_cache: Dict[Tuple[str, str], Dict[str, List[GraphNode]]] = {}
        # Cache: (process_id, origin_id) -> adjacency list representation
        self._graph_cache: Dict[Tuple[str, str], Dict[str, List[Tuple[str, float]]]] = {}
    
    def get_all_paths_from_origin(
        self,
        origin: GraphNode,
        edges: List[Tuple[GraphNode, GraphNode, float]],
        process_id: str,
    ) -> Dict[str, List[GraphNode]]:
        """
        Explores all nodes from the origin using Dijkstra's algorithm and returns
        all shortest paths. Results are cached for efficient subsequent lookups.
        
        Args:
            origin (GraphNode): The origin node to start exploration from.
            edges (List[Tuple[GraphNode, GraphNode, float]]): List of edges as
                (from_node, to_node, cost) tuples.
            process_id (str): The process ID for caching purposes.
            
        Returns:
            Dict[str, List[GraphNode]]: Dictionary mapping target node IDs to
                their shortest paths from origin.
        """
        origin_id = origin.node_id
        cache_key = (process_id, origin_id)
        
        # Check if we already have paths cached for this origin
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]
        
        # Build adjacency list from edges and collect all nodes
        adjacency_list, node_map = self._build_adjacency_list(edges)
        # Ensure origin is in node_map
        node_map[origin_id] = origin
        
        # Run Dijkstra's algorithm to find all shortest paths
        paths = self._dijkstra_explore_all(origin, adjacency_list, node_map)
        
        # Cache the results
        self._path_cache[cache_key] = paths
        self._graph_cache[cache_key] = adjacency_list
        
        return paths
    
    def _build_adjacency_list(
        self, edges: List[Tuple[GraphNode, GraphNode, float]]
    ) -> Tuple[Dict[str, List[Tuple[str, float]]], Dict[str, GraphNode]]:
        """
        Builds an adjacency list representation from edges and collects all nodes.
        
        Args:
            edges (List[Tuple[GraphNode, GraphNode, float]]): List of edges.
            
        Returns:
            Tuple[Dict[str, List[Tuple[str, float]]], Dict[str, GraphNode]]: 
                A tuple containing:
                - Adjacency list mapping node_id to list of (neighbor_id, cost) tuples.
                - Dictionary mapping node_id to GraphNode objects.
        """
        adjacency_list: Dict[str, List[Tuple[str, float]]] = {}
        node_map: Dict[str, GraphNode] = {}
        
        for from_node, to_node, cost in edges:
            from_id = from_node.node_id
            to_id = to_node.node_id
            
            # Store nodes in node_map
            node_map[from_id] = from_node
            node_map[to_id] = to_node
            
            # Add forward edge
            if from_id not in adjacency_list:
                adjacency_list[from_id] = []
            adjacency_list[from_id].append((to_id, cost))
            
            # Add backward edge (bi-directional graph)
            if to_id not in adjacency_list:
                adjacency_list[to_id] = []
            adjacency_list[to_id].append((from_id, cost))
        
        return adjacency_list, node_map
    
    def _dijkstra_explore_all(
        self,
        origin: GraphNode,
        adjacency_list: Dict[str, List[Tuple[str, float]]],
        node_map: Dict[str, GraphNode],
    ) -> Dict[str, List[GraphNode]]:
        """
        Runs Dijkstra's algorithm to explore all reachable nodes from origin
        and returns all shortest paths.
        
        Args:
            origin (GraphNode): The origin node.
            adjacency_list (Dict[str, List[Tuple[str, float]]]): Adjacency list.
            node_map (Dict[str, GraphNode]): Mapping from node IDs to GraphNodes.
            
        Returns:
            Dict[str, List[GraphNode]]: Dictionary mapping target node IDs to
                their shortest paths from origin.
        """
        origin_id = origin.node_id
        
        # Initialize distances and previous nodes
        distances: Dict[str, float] = {origin_id: 0.0}
        previous: Dict[str, Optional[str]] = {origin_id: None}
        
        # Priority queue: (distance, node_id)
        pq: List[Tuple[float, str]] = [(0.0, origin_id)]
        visited: set[str] = set()
        
        # Ensure origin is in node_map
        node_map[origin_id] = origin
        
        while pq:
            current_dist, current_id = heapq.heappop(pq)
            
            if current_id in visited:
                continue
            
            visited.add(current_id)
            
            # Explore neighbors
            if current_id in adjacency_list:
                for neighbor_id, edge_cost in adjacency_list[current_id]:
                    if neighbor_id in visited:
                        continue
                    
                    new_dist = current_dist + edge_cost
                    
                    # Update if we found a shorter path
                    if neighbor_id not in distances or new_dist < distances[neighbor_id]:
                        distances[neighbor_id] = new_dist
                        previous[neighbor_id] = current_id
                        heapq.heappush(pq, (new_dist, neighbor_id))
                        
                        # Create GraphNode if not exists (shouldn't happen if edges are complete)
                        if neighbor_id not in node_map:
                            node_map[neighbor_id] = GraphNode(node_id=neighbor_id)
        
        # Reconstruct all paths
        paths: Dict[str, List[GraphNode]] = {}
        
        for target_id in visited:
            path = self._reconstruct_path(origin_id, target_id, previous, node_map)
            if path:
                paths[target_id] = path
        
        return paths
    
    def _reconstruct_path(
        self,
        origin_id: str,
        target_id: str,
        previous: Dict[str, Optional[str]],
        node_map: Dict[str, GraphNode],
    ) -> List[GraphNode]:
        """
        Reconstructs the shortest path from origin to target.
        
        Args:
            origin_id (str): Origin node ID.
            target_id (str): Target node ID.
            previous (Dict[str, Optional[str]]): Dictionary mapping node IDs to
                their previous node IDs in the shortest path.
            node_map (Dict[str, GraphNode]): Mapping from node IDs to GraphNodes.
            
        Returns:
            List[GraphNode]: The shortest path as a list of GraphNodes.
        """
        if target_id not in previous:
            return []
        
        path = []
        current_id = target_id
        
        # Reconstruct path backwards
        while current_id is not None:
            if current_id not in node_map:
                # Create GraphNode if missing
                node_map[current_id] = GraphNode(node_id=current_id)
            path.append(node_map[current_id])
            current_id = previous.get(current_id)
        
        # Reverse to get path from origin to target
        path.reverse()
        return path
    
    def get_path(
        self,
        origin: GraphNode,
        target: GraphNode,
        edges: List[Tuple[GraphNode, GraphNode, float]],
        process_id: str,
    ) -> Optional[List[GraphNode]]:
        """
        Gets the shortest path from origin to target, using cached results
        if available.
        
        Args:
            origin (GraphNode): Origin node.
            target (GraphNode): Target node.
            edges (List[Tuple[GraphNode, GraphNode, float]]): List of edges.
            process_id (str): Process ID for caching.
            
        Returns:
            Optional[List[GraphNode]]: The shortest path, or None if no path exists.
        """
        # Early termination if origin and target are the same
        if origin.node_id == target.node_id:
            return [origin]
        
        # Get all paths from origin (will use cache if available)
        all_paths = self.get_all_paths_from_origin(origin, edges, process_id)
        
        # Return the path to target if it exists
        return all_paths.get(target.node_id)
