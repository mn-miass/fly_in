from parsing import Parsing, Hub, Connection      
from path_finder import Graph, Node, Neighbor, Dijkstra, Simulation, Drones
from tester import plot_paths

parsing = Parsing()
graph = Graph()

graph.add_nodes(parsing.hubs)
graph.add_node(parsing.start_hub, is_start=True)
graph.add_node(parsing.end_hub, is_end=True)
graph.get_connection(parsing.connections)


path_finder = Dijkstra(graph.nodes, graph.start_node, graph.end_node)
path_finder.get_shortest_path()
path_finder.get_second_path()

drones = Drones(parsing.start_hub, parsing.nb_drones)
simulation = Simulation(drones.drones, path_finder.paths)

if not path_finder.check_if_end_exit:
    print("No Path between start and end zone")
    exit()

simulation.assign_path()
print("run", flush=True)
simulation.run()
for turn, move in simulation.moves.items(git status):
    print(turn, move)