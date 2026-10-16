from collections import defaultdict
import sys



class Planer():
    def __init__(self, network, graph):
        self.graph = graph
        self.network = network
        self.zone_use = defaultdict(int) #key[(zone_q, turn_q)] nb of drone booked zone_q at turn_q
        self.link_use = defaultdict(int) #(link_q, turn_q) drone booked the connection q at turn q

    def plan_all(self):
        self.check_reachable()
        return [self.plane_one() for _ in range(self.network.nb_drones)]

    def check_reachable(self):
        seen = [self.graph.start_node.name]
        for node_name in seen:
            zone = self.graph.nodes[node_name]
            for neighbor_name, neighbor_obj in zone.neighbors.items():
                if neighbor_name in seen:
                    continue
                if neighbor_obj.node.zone_type == "blocked":
                    continue
                seen.append(neighbor_name)
        if self.graph.end_node.name not in seen:
            print("No path was found connected with the end")
            sys.exit()


    def plane_one(self):
        pass
