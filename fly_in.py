from parsing import Parsing, Hub, Connection
from path_finder import Graph, Node, Neighbor

parsing = Parsing()
graph = Graph()

graph.add_nodes(parsing.hubs)
graph.add_node(parsing.start_hub)
graph.add_node(parsing.end_hub)
graph.get_connection(parsing.connections)

for node in graph.nodes:
    print(f"{node} -> ", end="")
    for neighbor in graph.nodes[node].neighbors:
        print(f"{neighbor.neighbor.name} ", end="")
    print()
