from parsing import Parsing, Hub, Connection
from path_finder import Graph, Node, Neighbor, Djikstra

parsing = Parsing()
graph = Graph()

graph.add_nodes(parsing.hubs)
graph.add_node(parsing.start_hub, is_start=True)
graph.add_node(parsing.end_hub, is_end=True)
graph.get_connection(parsing.connections)


path_finder = Djikstra(graph.nodes, graph.start_node, graph.end_node)
path_finder.get_shortest_path()
path_finder.print_come_from()
print(path_finder.check_if_end_exit())