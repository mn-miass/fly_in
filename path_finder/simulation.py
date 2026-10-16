from typing import Dict, List
from .drones import Drones, Drone
from .path import Path

from collections import defaultdict
from typing import Any, DefaultDict, List, Set

class Simulation():
    def __init__(self, drones, paths):
        self.drones: List[Drone]  = drones
        self.paths: List[Path] = paths
        self.moves: Dict[Drone, str] = {}
        self._get_capacity() # get number of connections between each zone

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




    def _enter(self, drone: Drone, moves: List[str]) -> None:
        """Move the drone onto the next zone of its path and record it."""
        drone.index += 1
        drone.current_zone = drone.path.nodes[drone.index]
        moves.append(f"{drone.name}-{drone.current_zone.name}")
        if drone.index == len(drone.path.nodes) - 1:
            drone.is_finished = True

    def run(self) -> None:
        """Simulate turn by turn and store each turn in self.moves."""
        self.moves = {}
        end = self.paths[0].nodes[-1]
        zone_count: DefaultDict[Any, int] = defaultdict(int)
        zone_count[self.paths[0].nodes[0]] = len(self.drones)
        turn = 0
        while not self.all_finished():
            turn += 1
            link_usage: DefaultDict[Any, int] = defaultdict(int)
            moves: List[str] = []
            moved: Set[Drone] = set()

            # 1) drones crossing toward a restricted zone must arrive now
            for drone in self.drones:
                if drone.turn_left > 0:
                    drone.turn_left = 0
                    self._enter(drone, moves)
                    moved.add(drone)

            # 2) the others try to move. We repeat the sweep so a space
            #    freed by a drone later in the list is used this turn.
            progress = True
            while progress:
                progress = False
                for drone in self.drones:
                    if drone.is_finished or drone in moved:
                        continue
                    nodes = drone.path.nodes
                    a = nodes[drone.index]
                    b = nodes[drone.index + 1]
                    link = frozenset((a, b))

                    if link_usage[link] >= self.capacities[link]:
                        continue
                    if b is not end and zone_count[b] >= b.max_drones:
                        continue

                    link_usage[link] += 1
                    zone_count[a] -= 1
                    zone_count[b] += 1
                    moved.add(drone)
                    progress = True

                    if b.zone_type == "restricted":
                        drone.turn_left = 1
                        moves.append(f"{drone.name}-{a.name}-{b.name}")
                    else:
                        self._enter(drone, moves)
            if not moves:
                raise RuntimeError("Deadlock: no drone can move")
            self.moves[turn] = moves

    def _get_capacity(self):
        self.capacities = {}
        for path in self.paths:
            for i in range(len(path.nodes) - 1):
                a = path.nodes[i]
                b = path.nodes[i + 1]
                link = frozenset((a, b))
                max_link_capacity = a.neighbors[b.name].max_link_capacity
                self.capacities[link] = max_link_capacity

    def all_finished(self):
        return all(drone.is_finished for drone in self.drones)
