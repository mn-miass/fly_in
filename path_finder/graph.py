from parsing.data import Hub, Connection
from typing import Dict, List
import sys


class Graph():
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.start_node = None

    def add_node(self, node: Hub, is_start=False, is_end=False):
        self.nodes[node.name] = Node(node)
        if is_start:
            self.start_node = self.nodes[node.name]
        if is_end:
            self.end_node = self.nodes[node.name]

    def add_nodes(self, nodes: List[Hub]):
        for node in nodes: self.add_node(node)

    def get_connection(self, connections: List[Connection]):
        for connection in connections:
            node_a = self.nodes[connection.hub_a.name]
            node_b = self.nodes[connection.hub_b.name]
            node_a.neighbors.append(Neighbor(node_b, connection.max_link_capacity))
            node_b.neighbors.append(Neighbor(node_a, connection.max_link_capacity))

class Node():
    def __init__(self, hub: Hub):
        self.name = hub.name
        self.max_drones = hub.max_drones
        self.cost = self._get_cost(hub.zone)
        self.neighbors = []

    @staticmethod
    def _get_cost(zone):
        if zone == "normal":
            return 1 
        if zone == "priority":
            return 0.9
        if zone == "restricted":
            return 2
        if zone == "blocked":
            return sys.maxsize

class Neighbor():
    def __init__(self, node, max_link_capacity):
        self.node = node
        self.max_link_capacity = max_link_capacity