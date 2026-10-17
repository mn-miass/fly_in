from collections import defaultdict
import sys

class Planer():
    def __init__(self, network, graph):
        self.graph = graph
        self.network = network
        self.zone_use = defaultdict(int)  # (zone, turn) -> drones booked
        self.link_use = defaultdict(int)  # (link, turn) -> departures booked

    def plan_all(self):
        self.check_reachable()
        return [self.plane_one() for _ in range(self.network.nb_drones)]


    def check_reachable(self):
        seen = [self.graph.start_node]
        for node in seen:
            for neighbor in node.neighbors.values():
                neighbor = neighbor.node
                if neighbor.zone_type == "blocked" or neighbor in seen:
                    continue
                if self.graph.end_node == neighbor:
                    return
                seen.append(neighbor)
        print("No path was found connected with the end")
        sys.exit()


    def plane_one(self):
        end = self.graph.end_node.name
        horizon = 4 * (len(self.graph.nodes) + self.network.nb_drones) + 20
        reached = [{} for _ in range(horizon + 3)]
        reached[0][self.graph.start_node.name] = (0, 0, None, [])
        #priority, nb_moves, come_frome, positions_added
        for turn in range(horizon + 1):
            if end in reached[turn]:
                return self.build(reached, turn)
            for zone_name, (prio, moves, _, _) in reached[turn].items():
                if self.zone_free(zone_name, turn + 1):
                    self.offer(reached, turn + 1, zone_name, prio, moves,
                               (zone_name, turn), [zone_name])
                node = self.graph.nodes[zone_name]
                for next_name, neighbor in node.neighbors.items():
                    target = self.graph.nodes[next_name]
                    if next_name == self.graph.start_node.name:
                        continue
                    if target.zone_type == "blocked":
                        continue
                    link = frozenset((zone_name, next_name))
                    if (self.link_use[(link, turn + 1)] == neighbor.max_link_capacity):
                        continue
                    if target.zone_type == "restricted":
                        arrive = turn + 2
                        link_name = self.graph.link_names[link]
                        positions = [link_name, next_name]
                    else:
                        arrive = turn + 1
                        positions = [next_name]
                    if not self.zone_free(next_name, arrive):
                        continue
                    new_prio = prio
                    if target.zone_type == "priority":
                        new_prio += 1
                    self.offer(reached, arrive, next_name, new_prio,
                               moves + 1, (zone_name, turn), positions)
        raise ValueError("Could not schedule a drone within the turn limit")

    def offer(self, reached, turn, zone, prio, moves, prev, added):
        # same zone, same turn: fewer moves wins, then more priority zones
        old = reached[turn].get(zone)
        if old is None or (-moves, prio) > (-old[1], old[0]):
            reached[turn][zone] = (prio, moves, prev, added)

    def build(self, reached, turn):
        zone = self.graph.end_node.name
        parts = []
        while reached[turn][zone][2] is not None:
            _, _, prev, added = reached[turn][zone]
            parts.append(added)
            zone, turn = prev
        path = [self.graph.start_node.name]
        for part in reversed(parts):
            path.extend(part)
        self.reserve(path)
        return path

    def reserve(self, path):
        for turn in range(1, len(path)):
            prev = path[turn - 1]
            cur = path[turn]
            if cur in self.graph.nodes:
                self.zone_use[(cur, turn)] += 1
            if prev in self.graph.nodes and cur != prev:
                if cur in self.graph.nodes:
                    link = frozenset((prev, cur))
                else:
                    a, b = cur.split("-")
                    link = frozenset((a, b))
                self.link_use[(link, turn)] += 1

    def zone_free(self, name, turn):
        if name in (self.graph.start_node.name, self.graph.end_node.name):
            return True
        zone = self.graph.nodes[name]
        return self.zone_use[(name, turn)] < zone.max_drones

    def print_moves(self, paths):
        total_turns = max(len(path) for path in paths) - 1
        for turn in range(1, total_turns + 1):
            tokens = []
            for number, path in enumerate(paths, 1):
                if turn >= len(path):
                    continue
                if path[turn] != path[turn - 1]:
                    tokens.append(f"D{number}-{path[turn]}")
            print(" ".join(tokens))
        print(total_turns, file=sys.stderr)