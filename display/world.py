"""Parser-facing types and the normalised map the display works from.

The display never imports the parser. It only relies on the attributes
listed in the protocols below, so any object shaped like your ``Parsing``,
``Hub`` and ``Connection`` classes can be shown.
"""

from typing import Protocol, Sequence

LinkKey = tuple[str, str]


def link_key(first: str, second: str) -> LinkKey:
    """Return an order-independent key for the connection first-second."""
    return (first, second) if first <= second else (second, first)


class HubLike(Protocol):
    """What the display reads from a parsed zone."""

    @property
    def name(self) -> str:
        """Zone name."""
        ...

    @property
    def x(self) -> int:
        """Horizontal map coordinate."""
        ...

    @property
    def y(self) -> int:
        """Vertical map coordinate."""
        ...

    @property
    def color(self) -> str | None:
        """Value of the color= tag, or None when absent."""
        ...

    @property
    def max_drones(self) -> int:
        """Zone capacity."""
        ...

    @property
    def zone(self) -> str:
        """Zone type: normal, blocked, restricted or priority."""
        ...


class ConnectionLike(Protocol):
    """What the display reads from a parsed connection."""

    @property
    def hub_a(self) -> HubLike:
        """First endpoint."""
        ...

    @property
    def hub_b(self) -> HubLike:
        """Second endpoint."""
        ...

    @property
    def max_link_capacity(self) -> int:
        """How many drones may cross at once."""
        ...


class MapLike(Protocol):
    """What the display reads from the parser's result."""

    @property
    def nb_drones(self) -> int:
        """Fleet size."""
        ...

    @property
    def start_hub(self) -> HubLike:
        """Start zone."""
        ...

    @property
    def end_hub(self) -> HubLike:
        """End zone."""
        ...

    @property
    def hubs(self) -> Sequence[HubLike]:
        """Regular zones (the start and end zones may or may not be here)."""
        ...

    @property
    def connections(self) -> Sequence[ConnectionLike]:
        """All connections."""
        ...


class World:
    """A de-duplicated, dictionary-based view of the parsed map."""

    def __init__(self, source: MapLike) -> None:
        """Index the zones by name and the connections by endpoint pair.

        Args:
            source: The parser result.
        """
        self.drone_count: int = source.nb_drones
        self.start: str = source.start_hub.name
        self.end: str = source.end_hub.name
        self.hubs: dict[str, HubLike] = {}
        self.links: dict[LinkKey, ConnectionLike] = {}
        for hub in (source.start_hub, source.end_hub, *source.hubs):
            self.hubs.setdefault(hub.name, hub)
        for link in source.connections:
            self.hubs.setdefault(link.hub_a.name, link.hub_a)
            self.hubs.setdefault(link.hub_b.name, link.hub_b)
            self.links[link_key(link.hub_a.name, link.hub_b.name)] = link

    def zone_kind(self, name: str) -> str:
        """Return the zone type of a zone, defaulting to normal."""
        return (self.hubs[name].zone or "normal").lower()

    def slots(self, name: str) -> int:
        """Return how many drones a zone must be able to show at once."""
        if name == self.start:
            return max(self.drone_count, 1)
        if name == self.end:
            return 1
        return max(self.hubs[name].max_drones, 1)

    def link_slots(self, key: LinkKey) -> int:
        """Return how many drones a connection must be able to show."""
        return max(self.links[key].max_link_capacity, 1)
