from typing import Dict, List
from .drones import Drones, Drone
from .path import Path


class Simulation():
    def __init__(self, drones, paths):
        self.drones: List[Drones]  = drones
        self.paths: List[Path] = paths
        self.moves: Dict[Drone, str] = {}

    def path_capacity(self, path):
        max_capacity = float("inf")
        for i, node in enumerate(path.nodes):
            max_capacity = min(max_capacity, node.max_drones)
            if i < len(path.nodes) - 1:
                next_node = path.nodes[i + 1]
                connection = self.get_connection(node, next_node)
                max_capacity = min(max_capacity, connection)
        return max_capacity

    def get_connection(self, node, next_node):
        id = None
        for i, neighbor in enumerate(node.neighbors):
            if neighbor.node.name == next_node.name:
                id = i
                break
        return node.neighbors[i].max_link_capacity

    def has_capacity(self, path):
        return path.drones < self.path_capacity(path)

    def get_next_zone(self, current_zone):
        possible_paths = self.get_possible_paths(current_zone)
        for path in possible_paths:
            if self.has_capacity(path):
                return "somthing"

    def get_possible_paths(self, current_zone):
        possible_paths = []
        for path in self.paths:
            for node in path.nodes:
                if node == current_zone:
                    possible_paths.append(path)
                    break
        return possible_paths

    def get_drone_moves(self):
        for i, drone in enumerate(self.drones):
            pass