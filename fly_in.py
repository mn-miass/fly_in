from parsing import Parsing, Hub, Connection      
from path_finder import Graph, Node, Neighbor, Planer
from display import Display


parsing = Parsing()
graph = Graph()



print(parsing.hubs[0].max_drones)
print(parsing.connections[1].max_link_capacity)


graph.add_nodes(parsing.hubs)
graph.add_node(parsing.start_hub, is_start=True)
graph.add_node(parsing.end_hub, is_end=True)
graph.get_connection(parsing.connections)

planer = Planer(parsing, graph)
moves = planer.plan_all()
planer.print_moves(moves)

display = Display(graph.nodes, graph.start_node, parsing.nb_drones, moves)
display.run()
