"""Run the display on the subject's example map: python -m display.demo"""

from dataclasses import dataclass, field

from . import Viewer, parse_turns


@dataclass(frozen=True)
class DemoHub:
    """Stand-in for the parser's Hub class."""

    name: str
    x: int
    y: int
    color: str | None = None
    max_drones: int = 1
    zone: str = "normal"


@dataclass(frozen=True)
class DemoConnection:
    """Stand-in for the parser's Connection class."""

    hub_a: DemoHub
    hub_b: DemoHub
    max_link_capacity: int = 1


@dataclass(frozen=True)
class DemoMap:
    """Stand-in for the parser's Parsing class."""

    nb_drones: int
    start_hub: DemoHub
    end_hub: DemoHub
    hubs: list[DemoHub] = field(default_factory=list)
    connections: list[DemoConnection] = field(default_factory=list)


# The example map from chapter VI of the subject.
HUB = DemoHub("hub", 0, 0, "green")
GOAL = DemoHub("goal", 10, 10, "yellow")
ROOF1 = DemoHub("roof1", 3, 4, "red", zone="restricted")
ROOF2 = DemoHub("roof2", 6, 2, "blue")
CORRIDOR = DemoHub("corridorA", 4, 3, "green", max_drones=2, zone="priority")
TUNNEL = DemoHub("tunnelB", 7, 4, "red")
OBSTACLE = DemoHub("obstacleX", 5, 5, "gray", zone="blocked")

MAP = DemoMap(
    nb_drones=5,
    start_hub=HUB,
    end_hub=GOAL,
    hubs=[ROOF1, ROOF2, CORRIDOR, TUNNEL, OBSTACLE],
    connections=[
        DemoConnection(HUB, ROOF1),
        DemoConnection(HUB, CORRIDOR),
        DemoConnection(ROOF1, ROOF2),
        DemoConnection(ROOF2, GOAL),
        DemoConnection(CORRIDOR, TUNNEL, 2),
        DemoConnection(TUNNEL, GOAL),
    ],
)

# Hand-written turns, in the exact output format of the subject.
# "hub-roof1" is a drone in flight on the connection toward a restricted zone.
TURNS = parse_turns([
    "D1-corridorA D2-hub-roof1",
    "D1-tunnelB D2-roof1 D3-corridorA D4-hub-roof1",
    "D1-goal D2-roof2 D3-tunnelB D4-roof1 D5-corridorA",
    "D2-goal D3-goal D4-roof2 D5-tunnelB",
    "D4-goal D5-goal",
])

if __name__ == "__main__":
    Viewer(MAP, TURNS).run()
