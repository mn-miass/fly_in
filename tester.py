import matplotlib.pyplot as plt

def plot_paths(nodes, paths):
    fig, ax = plt.subplots()
    for node in nodes:
        for neighbor in nodes[node].neighbors:
            ax.plot([nodes[node].x, neighbor.node.x], [nodes[node].y, neighbor.node.y], 'lightgray', zorder=1)
        ax.scatter(nodes[node].x, nodes[node].y, c='black', zorder=2)
        ax.annotate(nodes[node].name, (nodes[node].x, nodes[node].y))

    colors = ['red', 'blue', 'green']
    for i, path in enumerate(paths):
        xs = [n.x for n in path.nodes]
        ys = [n.y for n in path.nodes]
        ax.plot(xs, ys, colors[i % len(colors)], linewidth=2, zorder=3)

    plt.show()
