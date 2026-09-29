"""Draws the network, the drones and the control panel with pygame."""

import math

import pygame
from pygame import gfxdraw
from pygame.math import Vector2

from . import palette
from .layout import DRONE_RADIUS, Layout
from .palette import Color
from .playback import Playback
from .timeline import Snapshot, Timeline
from .world import World

HUD_HEIGHT = 132
MARGIN = 24
ZONE_KINDS = ("normal", "priority", "restricted", "blocked")


def disc(
    surface: pygame.Surface, center: Vector2 | tuple[float, float],
    radius: float, color: Color,
) -> None:
    """Draw a smooth filled circle."""
    x, y, r = round(center[0]), round(center[1]), max(1, round(radius))
    gfxdraw.aacircle(surface, x, y, r, color)
    gfxdraw.filled_circle(surface, x, y, r, color)


def thick_line(
    surface: pygame.Surface, first: Vector2, last: Vector2,
    width: float, color: Color,
) -> None:
    """Draw a smooth straight line with a given thickness."""
    gap = last - first
    if gap.length() == 0:
        return
    side = Vector2(-gap.y, gap.x).normalize() * (width / 2.0)
    corners = [first + side, last + side, last - side, first - side]
    points = [(round(p.x), round(p.y)) for p in corners]
    gfxdraw.aapolygon(surface, points, color)
    gfxdraw.filled_polygon(surface, points, color)


def ring_thickness(radius: float) -> float:
    """Return the outline thickness used for a zone of this radius."""
    return max(2.0, radius * 0.14)


def halo(radius: float, kind: str) -> float:
    """Return how far a zone's decoration extends past its ring."""
    return ring_thickness(radius) + 2.5 if kind == "priority" else 0.0


def zone_glyph(
    surface: pygame.Surface, center: Vector2 | tuple[float, float],
    radius: float, color: Color, kind: str,
) -> None:
    """Draw a zone; its outline style tells the zone type.

    normal: solid ring, priority: double ring, restricted: dotted ring,
    blocked: dim disc crossed out.
    """
    thick = ring_thickness(radius)
    x, y = center
    if kind == "blocked":
        muted = palette.mix(palette.BACKGROUND, color, 0.5)
        disc(surface, center, radius, muted)
        disc(surface, center, radius - thick,
             palette.mix(palette.BACKGROUND, color, 0.1))
        reach = radius * 0.42
        for sign in (-1.0, 1.0):
            thick_line(
                surface, Vector2(x - reach, y - sign * reach),
                Vector2(x + reach, y + sign * reach), thick, muted)
        return
    interior = palette.mix(palette.INTERIOR, color, 0.14)
    if kind == "priority":
        outer = radius + halo(radius, kind)
        disc(surface, center, outer, color)
        disc(surface, center, outer - 1.5, palette.BACKGROUND)
    if kind == "restricted":
        disc(surface, center, radius, interior)
        ring = radius - thick / 2.0
        dots = max(10, round(2.0 * math.pi * ring / (thick * 1.7)))
        for i in range(dots):
            angle = 2.0 * math.pi * i / dots
            disc(surface, (x + ring * math.cos(angle),
                           y + ring * math.sin(angle)), thick / 2.0, color)
        return
    disc(surface, center, radius, color)
    disc(surface, center, radius - thick, interior)


class TextPainter:
    """Renders text and remembers the result so labels cost nothing."""

    def __init__(self) -> None:
        """Create empty font and text caches."""
        self._fonts: dict[tuple[int, bool], pygame.font.Font] = {}
        self._cache: dict[tuple[str, int, bool, Color], pygame.Surface] = {}

    def _font(self, size: int, bold: bool) -> pygame.font.Font:
        """Return a cached system font."""
        key = (size, bold)
        if key not in self._fonts:
            self._fonts[key] = pygame.font.SysFont(
                "dejavusans,arial,helvetica", size, bold=bold)
        return self._fonts[key]

    def width(self, text: str, size: int, bold: bool = False) -> int:
        """Return the pixel width of a piece of text."""
        return int(self._font(size, bold).size(text)[0])

    def render(
        self, text: str, size: int, color: Color, bold: bool = False
    ) -> pygame.Surface:
        """Return the rendered text surface."""
        key = (text, size, bold, color)
        surface = self._cache.get(key)
        if surface is None:
            if len(self._cache) > 600:
                self._cache.clear()
            surface = self._font(size, bold).render(text, True, color)
            self._cache[key] = surface
        return surface

    def draw(
        self, target: pygame.Surface, text: str, size: int, color: Color,
        pos: Vector2 | tuple[float, float], anchor: str = "topleft",
        bold: bool = False,
    ) -> pygame.Rect:
        """Draw text so that the given anchor of its box sits at pos."""
        surface = self.render(text, size, color, bold)
        rect = surface.get_rect(**{anchor: (round(pos[0]), round(pos[1]))})
        target.blit(surface, rect)
        return rect


class DroneSprites:
    """Pre-rendered drone dots, one per drone id."""

    def __init__(self, text: TextPainter) -> None:
        """Create an empty sprite cache."""
        self._text = text
        self._cache: dict[int, pygame.Surface] = {}

    def get(self, drone_id: int) -> pygame.Surface:
        """Return the sprite of a drone."""
        sprite = self._cache.get(drone_id)
        if sprite is None:
            sprite = self._build(drone_id)
            self._cache[drone_id] = sprite
        return sprite

    def _build(self, drone_id: int) -> pygame.Surface:
        """Draw a drone: a hue-coded disc with its number."""
        size = DRONE_RADIUS * 2 + 4
        middle = size // 2
        sprite = pygame.Surface((size, size), pygame.SRCALPHA)
        sprite.fill((*palette.TEXT, 0))
        disc(sprite, (middle, middle), DRONE_RADIUS, palette.TEXT)
        disc(sprite, (middle, middle), DRONE_RADIUS - 2,
             palette.drone_color(drone_id))
        label = self._text.render(
            str(drone_id), 11 if drone_id < 100 else 9,
            palette.BACKGROUND, bold=True)
        sprite.blit(label, label.get_rect(center=(middle, middle)))
        return sprite


class Renderer:
    """Paints one frame of the simulation onto a pygame surface."""

    def __init__(
        self, world: World, timeline: Timeline, layout: Layout
    ) -> None:
        """Create a renderer; the first ``draw`` call sizes everything."""
        self.world = world
        self.timeline = timeline
        self.layout = layout
        self.text = TextPainter()
        self.sprites = DroneSprites(self.text)
        self.size = (0, 0)
        self.bar = pygame.Rect(0, 0, 1, 1)
        self._static = pygame.Surface((1, 1))
        self._places: dict[int, dict[int, Vector2]] = {}

    def resize(self, size: tuple[int, int]) -> None:
        """Refit the map and rebuild the cached background."""
        self.size = size
        width, height = size
        self.layout.fit(pygame.Rect(0, 0, width, max(height - HUD_HEIGHT, 1)))
        self._places.clear()
        top = height - HUD_HEIGHT
        self.bar = pygame.Rect(MARGIN, top + 50, max(width - 2 * MARGIN, 1), 8)
        self._static = self._paint_static(size)

    def refresh(self) -> None:
        """Rebuild everything, e.g. after the layout changed."""
        self.resize(self.size)

    def draw(self, surface: pygame.Surface, playback: Playback) -> None:
        """Paint the current frame."""
        if surface.get_size() != self.size:
            self.resize(surface.get_size())
        surface.blit(self._static, (0, 0))
        nearest = (playback.to_index if playback.progress >= 0.5
                   else playback.from_index)
        shown = self.timeline[nearest]
        self._paint_flags(surface, shown)
        self._paint_drones(surface, playback)
        self._paint_badges(surface, shown)
        self._paint_hud(surface, playback, shown)

    # ------------------------------------------------------------------
    # Static layer: everything that only changes when the window does.
    # ------------------------------------------------------------------

    def _paint_static(self, size: tuple[int, int]) -> pygame.Surface:
        """Paint background, connections, zones and the legend."""
        surface = pygame.Surface(size)
        surface.fill(palette.BACKGROUND)
        for point in self.layout.lattice():
            disc(surface, point, 1.5, palette.GRID)
        self._paint_links(surface)
        self._paint_zones(surface)
        top = size[1] - HUD_HEIGHT
        surface.fill(palette.PANEL, (0, top, size[0], HUD_HEIGHT))
        pygame.draw.line(surface, palette.GRID, (0, top), (size[0], top))
        legend_left = self._paint_legend(surface, size[0] - MARGIN, top + 118)
        hints = ("Space play/pause    \u2190 \u2192 step    "
                 "\u2191 \u2193 speed    R restart    F flip y    "
                 "S screenshot    Esc quit")
        if MARGIN + self.text.width(hints, 12) + 2 * MARGIN < legend_left:
            self.text.draw(surface, hints, 12, palette.DIM,
                           (MARGIN, top + 111))
        return surface

    def _paint_links(self, surface: pygame.Surface) -> None:
        """Draw connections, capacity labels and restricted waypoints."""
        for key, link in self.world.links.items():
            first = self.layout.center(key[0])
            last = self.layout.center(key[1])
            capacity = link.max_link_capacity
            thick_line(surface, first, last, min(2 + capacity - 1, 7),
                       palette.LINK)
            middle = (first + last) / 2.0
            kinds = (self.world.zone_kind(key[0]),
                     self.world.zone_kind(key[1]))
            if "restricted" in kinds:
                disc(surface, middle, 6, palette.LINK)
                disc(surface, middle, 4, palette.BACKGROUND)
            if capacity > 1 and (last - first).length() > 0:
                gap = (last - first).normalize()
                spot = middle + Vector2(-gap.y, gap.x) * 14.0
                self.text.draw(surface, f"\u00d7{capacity}", 12, palette.DIM,
                               spot, "center")

    def _paint_zones(self, surface: pygame.Surface) -> None:
        """Draw every zone, then its name where it collides with nothing."""
        for name in self.world.hubs:
            hub = self.world.hubs[name]
            zone_glyph(
                surface, self.layout.center(name), self.layout.radius(name),
                palette.resolve(hub.color), self.world.zone_kind(name))
        caption = {self.world.start: "start", self.world.end: "end"}
        for name, box in self._place_labels().items():
            tint = (palette.DIM if self.world.zone_kind(name) == "blocked"
                    else palette.TEXT)
            title = self.text.draw(surface, name, 14, tint, box.midtop,
                                   "midtop")
            if name in caption:
                self.text.draw(surface, caption[name], 11, palette.DIM,
                               title.midbottom, "midtop")

    def _reach(self, name: str) -> float:
        """Return how far a zone's decoration extends from its centre."""
        radius = self.layout.radius(name)
        return radius + halo(radius, self.world.zone_kind(name))

    def _label_size(self, name: str) -> tuple[int, int]:
        """Return the box size of a zone's name (and start/end caption)."""
        width = self.text.width(name, 14)
        height = self.text.render(name, 14, palette.TEXT).get_height()
        if name in (self.world.start, self.world.end):
            height += 13
        return width, height

    def _place_labels(self) -> dict[str, pygame.Rect]:
        """Choose, for each zone, the side where its name is least in the way.

        Candidates are tried below, above, right and left. A candidate is
        penalised for touching another zone, another label, the window edge
        and (mildly) a connection line; ties keep the earlier side.
        """
        taken: dict[str, pygame.Rect] = {}
        area = pygame.Rect(0, 0, self.size[0], self.size[1] - HUD_HEIGHT)
        reserved = []
        for name in self.world.hubs:
            if self._has_badge(name):
                pill = pygame.Rect(0, 0, 40, 20)
                pill.center = self._badge_spot(name)
                reserved.append(pill)
        for name in self.world.hubs:
            width, height = self._label_size(name)
            center = self.layout.center(name)
            gap = self._reach(name) + 5
            sides = (
                pygame.Rect(center.x - width / 2, center.y + gap,
                            width, height),
                pygame.Rect(center.x - width / 2, center.y - gap - height,
                            width, height),
                pygame.Rect(center.x + gap, center.y - height / 2,
                            width, height),
                pygame.Rect(center.x - gap - width, center.y - height / 2,
                            width, height),
            )
            scores = [
                self._label_cost(name, box, taken, reserved, area) + 2 * order
                for order, box in enumerate(sides)]
            taken[name] = sides[scores.index(min(scores))]
        return taken

    def _label_cost(
        self, owner: str, box: pygame.Rect,
        taken: dict[str, pygame.Rect], reserved: list[pygame.Rect],
        area: pygame.Rect,
    ) -> int:
        """Score how badly a label box collides with its surroundings."""
        cost = 0 if area.contains(box) else 100
        for other in self.world.hubs:
            if other == owner:
                continue
            spot = self.layout.center(other)
            near_x = max(box.left - spot.x, 0.0, spot.x - box.right)
            near_y = max(box.top - spot.y, 0.0, spot.y - box.bottom)
            if math.hypot(near_x, near_y) < self._reach(other) + 2:
                cost += 100
        padded = box.inflate(4, 2)
        cost += 100 * sum(1 for done in (*taken.values(), *reserved)
                          if padded.colliderect(done))
        for first, last in self.world.links:
            crossing = box.clipline(
                self.layout.center(first), self.layout.center(last))
            cost += 8 if crossing else 0
        return cost

    def _paint_legend(self, surface: pygame.Surface, right: int,
                      middle: int) -> int:
        """Explain ring styles and capacity labels, right-aligned.

        Returns the x coordinate where the legend starts.
        """
        entries = [("link capacity", None)] + [(k, k) for k in
                                               reversed(ZONE_KINDS)]
        x = right
        for label, kind in entries:
            words = self.text.render(label, 12, palette.DIM)
            x -= words.get_width()
            surface.blit(words, (x, middle - words.get_height() // 2))
            x -= 10
            if kind is None:
                mark = self.text.render("\u00d7n", 12, palette.DIM)
                x -= mark.get_width()
                surface.blit(mark, (x, middle - mark.get_height() // 2))
                x -= 24
            else:
                x -= 11
                zone_glyph(surface, (x, middle), 5.5, palette.NEUTRAL, kind)
                x -= 24
        return x + 24

    # ------------------------------------------------------------------
    # Dynamic layer: redrawn each frame.
    # ------------------------------------------------------------------

    def _paint_flags(self, surface: pygame.Surface, shown: Snapshot) -> None:
        """Highlight zones and connections that break a rule."""
        for key in shown.flagged_links:
            first, last = self.layout.edge_points(*key)
            thick_line(surface, first, last, 5, palette.ISSUE)
        for name in shown.flagged_zones:
            center = self.layout.center(name)
            radius = self.layout.radius(name)
            outer = radius + halo(radius, self.world.zone_kind(name)) + 6
            disc_ring(surface, center, outer, palette.ISSUE)

    def _badge_text(self, name: str, shown: Snapshot) -> str | None:
        """Return the occupancy text of a zone, if it deserves one."""
        world = self.world
        load = shown.zone_load.get(name, 0)
        if name == world.start:
            return f"{load}/{world.drone_count}"
        if name == world.end:
            return f"{shown.delivered}/{world.drone_count}"
        if world.zone_kind(name) == "blocked":
            return None
        limit = world.hubs[name].max_drones
        return f"{load}/{limit}" if limit > 1 or load > limit else None

    def _has_badge(self, name: str) -> bool:
        """Whether a zone normally carries an occupancy pill."""
        world = self.world
        if name in (world.start, world.end):
            return True
        return (world.zone_kind(name) != "blocked"
                and world.hubs[name].max_drones > 1)

    def _badge_spot(self, name: str) -> tuple[int, int]:
        """Return the centre of a zone's occupancy pill."""
        center = self.layout.center(name)
        reach = self.layout.radius(name) * 0.8
        return round(center.x + reach), round(center.y - reach)

    def _paint_badges(self, surface: pygame.Surface, shown: Snapshot) -> None:
        """Draw 'drones/capacity' pills next to zones."""
        for name in self.world.hubs:
            content = self._badge_text(name, shown)
            if content is None:
                continue
            color = palette.ISSUE if name in shown.flagged_zones \
                else palette.TEXT
            words = self.text.render(content, 12, color, bold=True)
            box = words.get_rect(center=self._badge_spot(name))
            pill = box.inflate(10, 4)
            pygame.draw.rect(surface, palette.BACKGROUND, pill,
                             border_radius=pill.height // 2)
            pygame.draw.rect(surface, palette.LINK, pill, width=1,
                             border_radius=pill.height // 2)
            surface.blit(words, box)

    def _places_at(self, index: int) -> dict[int, Vector2]:
        """Return (and cache) drone positions for one snapshot."""
        if index not in self._places:
            self._places[index] = self.layout.place_drones(
                self.timeline[index])
        return self._places[index]

    def _paint_drones(self, surface: pygame.Surface,
                      playback: Playback) -> None:
        """Draw drones between two snapshots; delivered ones fade out."""
        before = self._places_at(playback.from_index)
        after = self._places_at(playback.to_index)
        first = self.timeline[playback.from_index].drones
        second = self.timeline[playback.to_index].drones
        t = playback.eased
        for drone_id in sorted(before):
            was = 0.0 if first[drone_id].delivered else 1.0
            will = 0.0 if second[drone_id].delivered else 1.0
            opacity = was + (will - was) * t
            if opacity < 0.02:
                continue
            spot = before[drone_id].lerp(after[drone_id], t)
            sprite = self.sprites.get(drone_id)
            sprite.set_alpha(round(255 * opacity))
            surface.blit(sprite, sprite.get_rect(
                center=(round(spot.x), round(spot.y))))

    def _paint_hud(self, surface: pygame.Surface, playback: Playback,
                   shown: Snapshot) -> None:
        """Draw counters, progress bar, movement log and key hints."""
        width, height = surface.get_size()
        top = height - HUD_HEIGHT
        text = self.text
        last = self.timeline.last
        head = text.draw(surface, f"Turn {shown.turn} of {last}", 20,
                         palette.TEXT, (MARGIN, top + 14), bold=True)
        text.draw(surface,
                  f"{shown.delivered} of {self.world.drone_count} delivered",
                  16, palette.DIM, (head.right + 28, top + 17))
        if playback.finished:
            status = "finished"
        else:
            status = "playing" if playback.playing else "paused"
        text.draw(surface, f"{status}   {playback.speed:.2f}\u00d7", 16,
                  palette.DIM, (width - MARGIN, top + 17), "topright")
        self._paint_bar(surface, playback)
        if shown.turn == 0:
            log = (f"{self.world.drone_count} drones waiting at "
                   f"{self.world.start}")
        else:
            log = " ".join(str(move) for move in shown.moves)
        text.draw(surface, self._clip(log, 14, width - 2 * MARGIN), 14,
                  palette.TEXT, (MARGIN, top + 70))
        if shown.issues:
            extra = len(shown.issues) - 1
            note = shown.issues[0] + (f"  (+{extra} more)" if extra else "")
            text.draw(surface, self._clip(note, 14, width - 2 * MARGIN), 14,
                      palette.ISSUE, (MARGIN, top + 91), bold=True)

    def _paint_bar(self, surface: pygame.Surface,
                   playback: Playback) -> None:
        """Draw the clickable timeline with a tick for every turn."""
        bar = self.bar
        last = max(self.timeline.last, 1)
        pygame.draw.rect(surface, palette.TRACK, bar,
                         border_radius=bar.height // 2)
        reach = round(bar.width * playback.position / last)
        if reach > 0:
            done = pygame.Rect(bar.left, bar.top, reach, bar.height)
            pygame.draw.rect(surface, palette.TEXT, done,
                             border_radius=bar.height // 2)
        for index in range(self.timeline.last + 1):
            x = bar.left + round(bar.width * index / last)
            bad = bool(self.timeline[index].issues)
            color = palette.ISSUE if bad else palette.DIM
            length = 8 if bad else 5
            pygame.draw.line(surface, color, (x, bar.bottom + 2),
                             (x, bar.bottom + 2 + length), 2 if bad else 1)
        disc(surface, (bar.left + reach, bar.centery), 7, palette.TEXT)
        disc(surface, (bar.left + reach, bar.centery), 3, palette.PANEL)

    def _clip(self, content: str, size: int, limit: int) -> str:
        """Shorten a line of words so that it fits in limit pixels."""
        if self.text.width(content, size) <= limit:
            return content
        words = content.split(" ")
        while words and self.text.width(" ".join(words) + " \u2026",
                                        size) > limit:
            words.pop()
        return " ".join(words) + " \u2026"


def disc_ring(surface: pygame.Surface, center: Vector2, radius: float,
              color: Color) -> None:
    """Draw a smooth two-pixel outline circle."""
    x, y = round(center.x), round(center.y)
    for r in (round(radius), round(radius) + 1):
        gfxdraw.aacircle(surface, x, y, r, color)
