from .graph import Graph, Hub, Node, Neighbor
from .path import Path
from typing import Dict, List
import sys


class Dijkstra():
    def __init__(self, nodes: List[Node], start: Node, end: Node):
        self.nodes = nodes
        self.start = start
        self.end = end
        self.paths = []

    def get_shortest_path(self):
        path = []
        heap = [(0, self.start)]
        visited = []
        dist = {self.start: 0}
        self.come_from = {self.start: None}
        while True:
            if not heap:
                break
            node, cost = self._get_min(heap)
            heap.remove((cost, node))
            for neighbor in node.neighbors:
                if neighbor.node in visited:
                    continue
                if neighbor.zone_type == "blocked":
                    continue
                neighbor_cost = cost + neighbor.node.cost
                if neighbor_cost < dist.get(neighbor.node, float("inf")):
                    dist[neighbor.node] = neighbor_cost
                    self.come_from[neighbor.node] = node
                    heap.append((neighbor_cost, neighbor.node))
                if neighbor.node == self.end:
                    break
            visited.append(node)
        

    def check_if_end_exit(self):
        return self.end in self.come_from.keys()

    def print_come_from(self):
        list_path = []
        current = self.end
        list_path.append(current)
        while current:
            current = self.come_from[current]
            if current:
                list_path.insert(0, current)
        for path in list_path:
            print(f"{path.name} -> ", end="")

    @staticmethod
    def _get_min(heap):
        min = sys.maxsize
        current = None
        for v, k in heap:
            if v <= min:
                current = k
                min = v
        return (current, min)
