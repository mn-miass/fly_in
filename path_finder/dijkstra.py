from .graph import Graph, Hub, Node, Neighbor
from .path import Path
from typing import Dict, List
import sys


class Dijkstra():
    def __init__(self, nodes: Dict[str, Node], start: Node, end: Node):
        self.nodes = nodes
        self.start = start
        self.end = end
        self.paths = []

    def get_shortest_path(self):
        heap = [(0, self.start)]
        visited = []
        dist = {self.start: 0}
        come_from = {self.start: None}
        while True:
            if not heap:
                break
            node, cost = self._get_min(heap)
            heap.remove((cost, node))
            for neighbor in node.neighbors:
                if neighbor.node in visited:
                    continue
                if neighbor.node.zone_type == "blocked":
                    continue
                neighbor_cost = cost + neighbor.node.cost
                if neighbor_cost < dist.get(neighbor.node, float("inf")):
                    dist[neighbor.node] = neighbor_cost
                    come_from[neighbor.node] = node
                    heap.append((neighbor_cost, neighbor.node))
                if neighbor.node == self.end:
                    break
            visited.append(node)
        if not self.check_if_end_exit(come_from):
            return None
        return self._get_path(come_from, dist[self.end])        

    def check_if_end_exit(self, come_from):
        return self.end in come_from.keys()

    def get_second_path(self):
        iter_num = 0
        while True:
            self.add_cost(self.paths[0].nodes, 0.1)
            path = self.get_shortest_path()
            if not path or iter_num > 40:
                break
            if self._check_same_paths(self.paths[0].nodes, path.nodes):
                self.paths.append(path)
                break
            iter_num += 1


    def add_cost(self, nodes, value):
        for node in nodes:
            node.cost += value

    def _get_path(self, come_from, dist):
        path_of_nodes = []
        current = self.end
        while True:
            path_of_nodes.append(current)
            next_node = come_from[current]
            if next_node == None:
                break
            current = next_node
        path = Path(path_of_nodes[::-1], dist)
        if not self.paths:
            self.paths.append(path)
        return path
    
    def display_path(self):
        for path in self.paths:
            print("path: ", end="")
            for node in path.nodes:
                print(f"{node.name} ->", end="")
            print()

    @staticmethod
    def _check_same_paths(path_a, path_b):
        index_path = 0
        if len(path_a) != len(path_b):
            return True
        while True:
            if index_path >= len(path_a) or index_path >= len(path_b):
                break
            if path_a[index_path].name != path_b[index_path].name:
                return True
            index_path += 1
        return False

    @staticmethod
    def _get_min(heap):
        min = sys.maxsize
        current = None
        for v, k in heap:
            if v <= min:
                current = k
                min = v
        return (current, min)
