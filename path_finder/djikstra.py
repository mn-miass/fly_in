from .graph import Graph, Hub, Node, Neighbor
from typing import Dict, List
import sys


class Djikstra():
    def __init__(self, nodes: List[Node], start: Node, end: Node):
        self.nodes = nodes
        self.start = start
        self.end = end

    def get_shortest_path(self):
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
                neighbor_cost = cost + neighbor.node.cost
                if neighbor_cost < dist.get(neighbor.node, float("inf")):
                    dist[neighbor.node] = neighbor_cost
                    self.come_from[neighbor.node] = node
                    heap.append((neighbor_cost, neighbor.node))
            visited.append(node)

    def check_if_end_exit(self):
        return list(self.come_from.keys())[-1] == self.end

    def print_come_from(self):
        for current in self.come_from.keys():
            print(f"{current.name} -> ", end="")

    @staticmethod
    def _get_min(heap):
        min = sys.maxsize
        current = None
        for v, k in heap:
            if v <= min:
                current = k
                min = v
        return (current, min)