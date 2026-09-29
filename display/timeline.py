"""Replays simulation turns into per-turn snapshots of the whole fleet."""

import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .world import LinkKey, World, link_key

_MOVE = re.compile(r"^D(\d+)-(.+)$")


class ReplayError(ValueError):
    """Raised when a turn refers to a drone, zone or link that is unknown."""


@dataclass(frozen=True)
class Move:
    """One drone movement, written like in the simulation output."""

    drone_id: int
    target: str

    def __str__(self) -> str:
        """Return the movement as D<ID>-<target>."""
        return f"D{self.drone_id}-{self.target}"


def parse_turn(line: str) -> list[Move]:
    """Parse one output line such as ``D1-roof1 D2-corridorA``.

    Args:
        line: Space-separated movements of a single turn.

    Returns:
        The movements, in the order they were written.

    Raises:
        ReplayError: If a token does not look like D<ID>-<target>.
    """
    moves: list[Move] = []
    for token in line.split():
        match = _MOVE.match(token)
        if match is None:
            raise ReplayError(f"bad movement '{token}': expected D<ID>-<zone>")
        moves.append(Move(int(match.group(1)), match.group(2)))
    return moves


def parse_turns(lines: Iterable[str]) -> list[list[Move]]:
    """Parse several output lines, ignoring blank ones."""
    return [parse_turn(line) for line in lines if line.strip()]


@dataclass(frozen=True)
class DroneState:
    """Where one drone is at the end of a turn.

    While a drone crosses a connection toward a restricted zone, ``zone``
    is the zone it left and ``heading_to`` the zone it will reach.
    """

    zone: str
    heading_to: str | None = None
    delivered: bool = False

    @property
    def in_transit(self) -> bool:
        """Whether the drone is on a connection."""
        return self.heading_to is not None

    @property
    def link(self) -> LinkKey | None:
        """The connection being crossed, if any."""
        if self.heading_to is None:
            return None
        return link_key(self.zone, self.heading_to)


@dataclass(frozen=True)
class Snapshot:
    """The whole fleet after a given turn (turn 0 is the initial state)."""

    turn: int
    drones: dict[int, DroneState]
    moves: tuple[Move, ...] = ()
    zone_load: dict[str, int] = field(default_factory=dict)
    link_load: dict[LinkKey, int] = field(default_factory=dict)
    delivered: int = 0
    issues: tuple[str, ...] = ()
    flagged_zones: frozenset[str] = frozenset()
    flagged_links: frozenset[LinkKey] = frozenset()


@dataclass
class _Turn:
    """Scratch space collected while one turn is applied."""

    number: int
    link_load: dict[LinkKey, int] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    zones: set[str] = field(default_factory=set)
    links: set[LinkKey] = field(default_factory=set)

    def flag_zone(self, zone: str, message: str) -> None:
        """Record a rule violation involving a zone."""
        self.zones.add(zone)
        self.issues.append(message)

    def flag_link(self, key: LinkKey, message: str) -> None:
        """Record a rule violation involving a connection."""
        self.links.add(key)
        self.issues.append(message)

    def add_load(self, key: LinkKey) -> None:
        """Count one more drone on a connection."""
        self.link_load[key] = self.link_load.get(key, 0) + 1


class Timeline:
    """Every snapshot of a simulation, built by replaying its turns.

    Structural mistakes (unknown drone, zone or connection) raise
    ``ReplayError``. Rule violations (capacity, blocked zones, waiting on a
    connection) do not stop the replay: they are recorded on the snapshot
    so the display can highlight them.
    """

    def __init__(self, world: World, turns: Sequence[Sequence[Move]]) -> None:
        """Replay all turns.

        Args:
            world: The parsed map.
            turns: One list of movements per simulation turn.
        """
        self.world = world
        first = {
            drone_id: DroneState(world.start)
            for drone_id in range(1, world.drone_count + 1)
        }
        self.snapshots: list[Snapshot] = [self._close(_Turn(0), first, ())]
        for number, moves in enumerate(turns, start=1):
            self.snapshots.append(
                self._step(number, self.snapshots[-1], moves))

    def __len__(self) -> int:
        """Return the number of snapshots (turns + 1)."""
        return len(self.snapshots)

    def __getitem__(self, index: int) -> Snapshot:
        """Return the snapshot after the given turn."""
        return self.snapshots[index]

    @property
    def last(self) -> int:
        """Index of the final snapshot, i.e. the number of turns."""
        return len(self.snapshots) - 1

    def _step(
        self, number: int, previous: Snapshot, moves: Sequence[Move]
    ) -> Snapshot:
        """Apply one turn to the previous snapshot."""
        log = _Turn(number)
        after = dict(previous.drones)
        moved: set[int] = set()
        for move in moves:
            state = previous.drones.get(move.drone_id)
            if state is None:
                raise ReplayError(
                    f"turn {number}: drone D{move.drone_id} does not exist")
            if move.drone_id in moved:
                raise ReplayError(
                    f"turn {number}: D{move.drone_id} moves twice")
            if state.delivered:
                raise ReplayError(
                    f"turn {number}: D{move.drone_id} is already delivered")
            moved.add(move.drone_id)
            after[move.drone_id] = self._resolve(move, state, log)
        for drone_id, before in previous.drones.items():
            link = before.link
            if link is not None and after[drone_id].in_transit:
                log.flag_link(
                    link,
                    f"D{drone_id} waits on connection {link[0]}-{link[1]}: "
                    "it must arrive on the next turn")
        return self._close(log, after, tuple(moves))

    def _resolve(
        self, move: Move, state: DroneState, log: _Turn
    ) -> DroneState:
        """Return the new state of a drone after one movement."""
        world = self.world
        who = f"D{move.drone_id}"
        target = move.target
        if target in world.hubs:
            if state.in_transit:
                if state.heading_to != target:
                    raise ReplayError(
                        f"turn {log.number}: {who} is heading to "
                        f"{state.heading_to}, not {target}")
            else:
                self._need_link(log, who, state.zone, target)
                log.add_load(link_key(state.zone, target))
                if world.zone_kind(target) == "restricted":
                    log.flag_zone(
                        target,
                        f"{who} entered restricted zone {target} without "
                        "first crossing its connection")
            self._check_blocked(log, who, target)
            return DroneState(target, delivered=target == world.end)
        ends = target.split("-")
        if len(ends) == 2 and all(end in world.hubs for end in ends):
            if state.in_transit or state.zone not in ends:
                raise ReplayError(
                    f"turn {log.number}: {who} cannot start crossing "
                    f"{target} from {state.zone}")
            destination = ends[1] if ends[0] == state.zone else ends[0]
            self._need_link(log, who, state.zone, destination)
            self._check_blocked(log, who, destination)
            if world.zone_kind(destination) != "restricted":
                log.flag_link(
                    link_key(state.zone, destination),
                    f"{who} is on a connection toward {destination}, which "
                    "is not a restricted zone")
            return DroneState(state.zone, heading_to=destination)
        raise ReplayError(
            f"turn {log.number}: '{target}' is neither a zone nor a "
            "connection of this map")

    def _need_link(self, log: _Turn, who: str, first: str, last: str) -> None:
        """Make sure two zones are connected."""
        if link_key(first, last) not in self.world.links:
            raise ReplayError(
                f"turn {log.number}: {who} moved {first} -> {last} but "
                "these zones are not connected")

    def _check_blocked(self, log: _Turn, who: str, zone: str) -> None:
        """Flag a drone that enters a blocked zone."""
        if self.world.zone_kind(zone) == "blocked":
            log.flag_zone(zone, f"{who} entered blocked zone {zone}")

    def _close(
        self, log: _Turn, after: dict[int, DroneState],
        moves: tuple[Move, ...],
    ) -> Snapshot:
        """Count occupancy, check capacities and build the snapshot."""
        world = self.world
        zone_load: dict[str, int] = {}
        for state in after.values():
            link = state.link
            if link is not None:
                log.add_load(link)
            elif not state.delivered:
                zone_load[state.zone] = zone_load.get(state.zone, 0) + 1
        for name, load in zone_load.items():
            limit = world.hubs[name].max_drones
            if name not in (world.start, world.end) and load > limit:
                log.flag_zone(
                    name, f"zone {name} holds {load} drones, limit {limit}")
        for key, load in log.link_load.items():
            limit = world.links[key].max_link_capacity
            if load > limit:
                log.flag_link(
                    key,
                    f"connection {key[0]}-{key[1]} carries {load} drones, "
                    f"limit {limit}")
        return Snapshot(
            turn=log.number,
            drones=after,
            moves=moves,
            zone_load=zone_load,
            link_load=dict(log.link_load),
            delivered=sum(1 for s in after.values() if s.delivered),
            issues=tuple(log.issues),
            flagged_zones=frozenset(log.zones),
            flagged_links=frozenset(log.links),
        )
