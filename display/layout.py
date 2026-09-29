"""Places zones and drones on screen."""

import math
from functools import lru_cache

import pygame
from pygame.math import Vector2

from .timeline import Snapshot
from .world import LinkKey, World, link_key

DRONE_RADIUS = 9
SPOT = 2 * DRONE_RADIUS + 3  # distance between two drones in a small zone
SUNFLOWER_STEP = 12.5  # spacing used when a zone holds many drones
GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))
RING_PADDING = 7
MAX_SPREAD = 110.0
MIN_LATTICE_GAP = 14.0


@lru_cache(maxsize=None)
def slot_offsets(count: int) -> tuple[tuple[float, float], ...]:
    """Return fixed drone positions relative to a zone centre.

    Up to seven drones sit on a circle (one drone sits in the middle); larger
    groups are packed in a sunflower spiral. The positions depend only on
    ``count`` so a zone always looks the same.
    """
    if count <= 1:
        return ((0.0, 0.0),)
    spots: list[tuple[float, float]] = []
    if count <= 7:
        radius = SPOT / (2.0 * math.sin(math.pi / count))
        first = math.pi if count == 2 else -math.pi / 2.0
        for i in range(count):
            angle = first + 2.0 * math.pi * i / count
            spots.append((radius * math.cos(angle), radius * math.sin(angle)))
    else:
        for i in range(count):
            radius = SUNFLOWER_STEP * math.sqrt(i + 0.5)
            angle = i * GOLDEN_ANGLE
            spots.append((radius * math.cos(angle), radius * math.sin(angle)))
    reach = max(math.hypot(x, y) for x, y in spots)
    if reach > MAX_SPREAD:
        shrink = MAX_SPREAD / reach
        spots = [(x * shrink, y * shrink) for x, y in spots]
    return tuple(spots)


def zone_extent(count: int) -> float:
    """Return the ring radius needed to hold count drones."""
    reach = max(math.hypot(x, y) for x, y in slot_offsets(count))
    return reach + DRONE_RADIUS + RING_PADDING


class Layout:
    """Maps map coordinates to pixels and sizes the zones."""

    def __init__(self, world: World, flip_y: bool = True) -> None:
        """Prepare the layout; call ``fit`` before using it.

        Args:
            world: The parsed map.
            flip_y: Draw larger y values higher up, like a graph.
        """
        self.world = world
        self.flip_y = flip_y
        self.scale = 1.0
        hubs = world.hubs.values()
        self._min_x = min(hub.x for hub in hubs)
        self._max_x = max(hub.x for hub in hubs)
        self._min_y = min(hub.y for hub in hubs)
        self._max_y = max(hub.y for hub in hubs)
        self._anchor = Vector2()
        self._extent = {n: zone_extent(world.slots(n)) for n in world.hubs}
        self._centers: dict[str, Vector2] = {}
        self._radii: dict[str, float] = {}

    def fit(self, area: pygame.Rect) -> None:
        """Scale and centre the map so that it fills the given area."""
        span_x = max(self._max_x - self._min_x, 1)
        span_y = max(self._max_y - self._min_y, 1)
        pad = max(self._extent.values()) + 44.0
        scale_x = max(area.width - 2 * pad, 1.0) / span_x
        scale_y = max(area.height - 2 * pad, 1.0) / span_y
        self.scale = min(scale_x, scale_y)
        self._anchor = Vector2(area.center)
        self._centers = {
            name: self.project(hub.x, hub.y)
            for name, hub in self.world.hubs.items()
        }
        base = min(30.0, max(16.0, 0.34 * self.scale * self._closest_pair()))
        self._radii = {
            name: max(base, self._extent[name]) for name in self.world.hubs
        }

    def _closest_pair(self) -> float:
        """Return the smallest distance between two zones, in map units."""
        points = [(h.x, h.y) for h in self.world.hubs.values()]
        best = math.inf
        for i, first in enumerate(points):
            for second in points[i + 1:]:
                gap = math.dist(first, second)
                if 0.0 < gap < best:
                    best = gap
        return 1.0 if math.isinf(best) else best

    def project(self, x: float, y: float) -> Vector2:
        """Convert map coordinates to screen coordinates."""
        mid_x = (self._min_x + self._max_x) / 2.0
        mid_y = (self._min_y + self._max_y) / 2.0
        sign = -1.0 if self.flip_y else 1.0
        return self._anchor + Vector2(
            (x - mid_x) * self.scale, sign * (y - mid_y) * self.scale)

    def lattice(self) -> list[Vector2]:
        """Return screen positions of every integer map coordinate."""
        if self.scale < MIN_LATTICE_GAP:
            return []
        return [
            self.project(x, y)
            for x in range(self._min_x, self._max_x + 1)
            for y in range(self._min_y, self._max_y + 1)
        ]

    def center(self, name: str) -> Vector2:
        """Return the screen position of a zone."""
        return self._centers[name]

    def radius(self, name: str) -> float:
        """Return the ring radius of a zone in pixels."""
        return self._radii[name]

    def edge_points(self, first: str, last: str) -> tuple[Vector2, Vector2]:
        """Return where a connection leaves one ring and meets the other."""
        start, end = self.center(first), self.center(last)
        gap = end - start
        if gap.length() <= self.radius(first) + self.radius(last):
            return start, end
        direction = gap.normalize()
        return (
            start + direction * self.radius(first),
            end - direction * self.radius(last),
        )

    def place_drones(self, snapshot: Snapshot) -> dict[int, Vector2]:
        """Return the screen position of every drone in a snapshot."""
        world = self.world
        resting: dict[str, list[int]] = {}
        crossing: dict[LinkKey, list[int]] = {}
        for drone_id in sorted(snapshot.drones):
            state = snapshot.drones[drone_id]
            link = state.link
            if link is not None:
                crossing.setdefault(link, []).append(drone_id)
            else:
                resting.setdefault(state.zone, []).append(drone_id)
        spots: dict[int, Vector2] = {}
        for zone, ids in resting.items():
            offsets = slot_offsets(max(world.slots(zone), len(ids)))
            for rank, drone_id in enumerate(ids):
                slot = drone_id - 1 if zone == world.start else rank
                dx, dy = offsets[slot % len(offsets)]
                spots[drone_id] = self.center(zone) + Vector2(dx, dy)
        for key, ids in crossing.items():
            middle = (self.center(key[0]) + self.center(key[1])) / 2.0
            offsets = slot_offsets(max(world.link_slots(key), len(ids)))
            for rank, drone_id in enumerate(ids):
                dx, dy = offsets[rank % len(offsets)]
                spots[drone_id] = middle + Vector2(dx, dy)
        return spots

    def link_middle(self, first: str, last: str) -> Vector2:
        """Return the midpoint of the connection between two zones."""
        key = link_key(first, last)
        return (self.center(key[0]) + self.center(key[1])) / 2.0
