from parsing import Parsing, Hub, Connection      
from path_finder import Graph, Node, Neighbor, Dijkstra, Simulation, Drones, Planer
from display import Display


parsing = Parsing()
graph = Graph()

graph.add_nodes(parsing.hubs)
graph.add_node(parsing.start_hub, is_start=True)
graph.add_node(parsing.end_hub, is_end=True)
graph.get_connection(parsing.connections)

# display = Display(graph.nodes, graph.start_node, parsing.nb_drones)
# display.run()
# path_finder = Dijkstra(graph.nodes, graph.start_node, graph.end_node)
# path_finder.get_shortest_path()
# path_finder.get_second_path()

# path_finder._print_paths()

# if not path_finder.check_if_end_exit:
#     print("No Path between start and end zone")
#     exit()
planer = Planer([], graph)
planer.check_reachable()

# drones = Drones(parsing.start_hub, parsing.nb_drones)
# simulation = Simulation(drones.drones, path_finder.paths)


# simulation.assign_path()
# # print("run", flush=True)
# simulation.run()
# for move in simulation.moves:
#     for move in simulation.moves[move]:
#         print(move, end = " ")
#     print()
# for turn, move in simulation.moves.items():
#     for m in move:
#         print(m + " ", end="")
#     print()
