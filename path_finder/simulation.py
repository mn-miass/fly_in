from typing import Dict, List
from .drones import Drones, Drone
from .path import Path


class Simulation():
    def __init__(self, drones, paths):
        self.drones: List[Drone]  = drones
        self.paths: List[Path] = paths
        self.moves: Dict[Drone, str] = {}
        self._get_capacity()

    def assign_path(self):
        count = 0
        for drone in self.drones:
            drone.path = self.paths[count % len(self.paths)]
            count += 1 

    def display_drones(self):
        for drone in self.drones:
            print(f"{drone.name} {drone.current_zone.name} {drone.index} {drone.turn_left} {drone.is_finished} ", end="")
            for node in drone.path.nodes:
                print(f"{node.name} ", end="")
            print()

    def run(self):
        turn = 0
        moves = []
        self.moves = {}
        while not self.all_finished():
            print(self.all_finished, turn, flush=True)
            link_usage = {}
            turn += 1
            moves = []
            for drone in self.drones:
                if drone.is_finished:
                    continue
                a = drone.path.nodes[drone.index]
                b = drone.path.nodes[drone.index + 1]
                link = frozenset((a, b))
                if link_usage.get(link, 0) < self.capacities[link]:
                    link_usage[link] = link_usage.get(link, 0) + 1
                    drone.index += 1
                    drone.current_zone = b
                    moves.append(f"{drone.name}-{drone.current_zone.name}")
                if drone.index == len(drone.path.nodes) - 1:
                    drone.is_finished = True
            self.moves[turn] = moves

    def _get_capacity(self):
        self.capacities = {}
        for path in self.paths:
            for i in range(len(path.nodes) - 1):
                a = path.nodes[i]
                b = path.nodes[i + 1]
                link = frozenset((a, b))
                for node in a.neighbors:
                    if node.node.name == b.name:
                        max_link_capacity = node.max_link_capacity
                        break
                self.capacities[link] = max_link_capacity

    def all_finished(self):
        return all(drone.is_finished for drone in self.drones)
