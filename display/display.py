import colorsys
import math
from collections import deque

import pygame

ZONE_COLORS = {
    "normal": (150, 155, 165),
    "priority": (70, 130, 255),
    "restricted": (235, 70, 70),
    "blocked": (15, 15, 15),
}
ACCENT = (90, 170, 255)
GREEN = (110, 220, 140)
AMBER = (255, 200, 90)
GOLD = (255, 210, 80)
TEXT = (235, 238, 245)
MUTED = (150, 158, 175)
PANEL = (12, 15, 22)


def clamp(value, low, high):
    return max(low, min(value, high))


class DroneDisplay():
    TRAIL_LEN = 36

    def __init__(self, pos, image, drone_id):
        self.name = f"D{drone_id}"
        self.x = self.start_x = self.target_x = float(pos[0])
        self.y = self.start_y = self.target_y = float(pos[1])
        self.image = image
        self.progress = 1.0
        self.duration = 1.0
        self.vx = 0.0                       # smoothed horizontal speed
        self.offset = [0.0, 0.0]            # spread when sharing a zone
        self.want_offset = (0.0, 0.0)
        self.trail = deque(maxlen=self.TRAIL_LEN)
        self.phase = drone_id * 1.7         # desync the hover animation
        hue = (drone_id * 0.618033) % 1.0   # a distinct colour per drone
        r, g, b = colorsys.hsv_to_rgb(hue, 0.6, 1.0)
        self.color = (int(r * 255), int(g * 255), int(b * 255))

    @property
    def moving(self):
        return self.progress < 1.0

    def move_drone(self, new_coord, duration_ms):
        if (abs(new_coord[0] - self.x) < 1e-9
                and abs(new_coord[1] - self.y) < 1e-9):
            self.progress = 1.0
            return
        self.start_x = self.x
        self.start_y = self.y
        self.target_x = new_coord[0]
        self.target_y = new_coord[1]
        self.duration = max(duration_ms, 1)
        self.progress = 0.0

    def reset(self, pos):
        self.x = self.start_x = self.target_x = float(pos[0])
        self.y = self.start_y = self.target_y = float(pos[1])
        self.progress = 1.0
        self.vx = 0.0
        self.trail.clear()

    def update(self, dt_ms):
        old_x = self.x
        if self.progress < 1.0:
            self.progress = min(self.progress + dt_ms / self.duration, 1.0)
            t = self.progress * self.progress * (3 - 2 * self.progress)
            self.x = self.start_x + (self.target_x - self.start_x) * t
            self.y = self.start_y + (self.target_y - self.start_y) * t
            self.trail.append((self.x, self.y))
        elif self.trail:
            self.trail.popleft()            # the trail fades once parked
        self.vx += ((self.x - old_x) / max(dt_ms, 1) - self.vx) * 0.2
        k = 1 - math.exp(-dt_ms / 80)
        self.offset[0] += (self.want_offset[0] - self.offset[0]) * k
        self.offset[1] += (self.want_offset[1] - self.offset[1]) * k


class Display():
    def __init__(self, nodes, start_node, nb_drones, turns,
                 step_delay=800, auto_play=True, end_node=None):
        self.turns = turns
        self.turn_index = 0
        self.total_steps = max((len(p) for p in turns), default=0)
        self.step_delay = step_delay
        self.auto_play = auto_play
        self.step_timer = 0
        self.time = 0
        pygame.init()
        self.font = pygame.font.Font(None, 20)
        self.mid_font = pygame.font.Font(None, 24)
        self.big_font = pygame.font.Font(None, 46)
        self.nb_drones = nb_drones
        self.nodes = nodes
        self.start = start_node
        self.end = end_node
        info = pygame.display.Info()
        self.width = max(info.current_w // 2, 800)
        self.height = max(info.current_h // 2, 560)
        self.screen = pygame.display.set_mode(
            (self.width, self.height), pygame.RESIZABLE
        )
        pygame.display.set_caption("Fly_in")
        self.bg_src = pygame.image.load("./assets/bg.webp").convert()
        self.drone_src = pygame.image.load(
            "./assets/drone.png"
        ).convert_alpha()
        # view state
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.dragging = False
        self.seeking = False
        self.resume_after_seek = False
        self.show_trails = True
        self.show_help = True
        self.hover_name = None
        # caches
        self._texts = {}
        self._pills = {}
        self._sprites = {}
        self._shadows = {}
        self.clock = pygame.time.Clock()
        self.running = True
        self.drones = []
        self._build_surfaces()
        self.fit_to_window()
        self.creat_drones()

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #
    def run(self):
        while self.running:
            dt = min(self.clock.tick(60), 100)
            self.time += dt
            self.handle_events()
            self.auto_advance(dt)
            self.update_drones(dt)
            self.update_hover()
            self.draw()
        pygame.quit()

    def auto_advance(self, dt):
        if not self.auto_play or self.is_finished():
            return
        self.step_timer += dt
        if self.step_timer >= self.step_delay:
            self.step_timer = 0
            self.next_step()

    def update_drones(self, dt):
        groups = {}
        for drone in self.drones:
            drone.want_offset = (0.0, 0.0)
            if not drone.moving:
                key = (round(drone.x, 2), round(drone.y, 2))
                groups.setdefault(key, []).append(drone)
        for members in groups.values():
            if len(members) > 1:
                for i, drone in enumerate(members):
                    drone.want_offset = self._spread(i, len(members))
        for drone in self.drones:
            drone.update(dt)

    @staticmethod
    def _spread(i, n):
        """Fan out drones sharing a zone so none is hidden."""
        if n <= 8:
            angle = 2 * math.pi * i / n - math.pi / 2
            radius = 12 + 2 * n
        else:
            angle = i * 2.39996
            radius = 8 * math.sqrt(i + 1)
        return (math.cos(angle) * radius, math.sin(angle) * radius)

    def is_finished(self):
        return self.total_steps == 0 or self.turn_index >= self.total_steps

    def update_hover(self):
        self.hover_name = None
        if self.dragging or self.seeking or not pygame.mouse.get_focused():
            return
        mouse = pygame.mouse.get_pos()
        if self._timeline_hit(mouse):
            return
        radius = self.node_radius + 4
        for name, node in self.nodes.items():
            cx, cy = self._to_screen(node.x, node.y)
            if (mouse[0] - cx) ** 2 + (mouse[1] - cy) ** 2 <= radius ** 2:
                self.hover_name = name
                return

    # ------------------------------------------------------------------ #
    # Events
    # ------------------------------------------------------------------ #
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE:
                self._on_resize(event.w, event.h)
            elif event.type == pygame.KEYDOWN:
                self._on_key(event.key)
            elif event.type == pygame.MOUSEWHEEL:
                self.zoom_at(1.1 ** event.y, pygame.mouse.get_pos())
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._timeline_hit(event.pos):
                    self.seeking = True
                    self.resume_after_seek = self.auto_play
                    self.auto_play = False
                    self._seek(event.pos[0])
                else:
                    self.dragging = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.seeking:
                    self.seeking = False
                    self.auto_play = self.resume_after_seek
                self.dragging = False
            elif event.type == pygame.MOUSEMOTION:
                if self.seeking:
                    self._seek(event.pos[0])
                elif self.dragging:
                    self.pan_x += event.rel[0]
                    self.pan_y += event.rel[1]

    def _on_key(self, key):
        if key == pygame.K_ESCAPE:
            self.running = False
        elif key == pygame.K_SPACE:
            if self.is_finished():
                self.restart()
                self.auto_play = True
            else:
                self.auto_play = not self.auto_play
        elif key == pygame.K_RIGHT:
            self.auto_play = False
            self.next_step()
        elif key == pygame.K_LEFT:
            self.auto_play = False
            self.previous_step()
        elif key == pygame.K_UP:
            self.step_delay = max(100, self.step_delay - 100)
        elif key == pygame.K_DOWN:
            self.step_delay = min(3000, self.step_delay + 100)
        elif key == pygame.K_r:
            self.restart()
        elif key == pygame.K_t:
            self.show_trails = not self.show_trails
        elif key == pygame.K_h:
            self.show_help = not self.show_help
        elif key == pygame.K_f:
            self.reset_view()

    def _on_resize(self, w, h):
        self.width = max(w, 320)
        self.height = max(h, 240)
        self.screen = pygame.display.get_surface()
        self._build_surfaces()
        self.fit_to_window()

    def _seek(self, mouse_x):
        track = self._timeline_rect()
        frac = clamp((mouse_x - track.left) / max(track.width, 1), 0, 1)
        target = round(frac * self.total_steps)
        if target != self.turn_index:
            self._set_turn(target, 250, clear_trails=True)

    # ------------------------------------------------------------------ #
    # Simulation steps
    # ------------------------------------------------------------------ #
    def _step_pos(self, step):
        if step in self.nodes:
            node = self.nodes[step]
            return (node.x, node.y)
        if "-" in step:                      # drone is on a connection
            a, b = step.split("-", 1)
            return ((self.nodes[a].x + self.nodes[b].x) / 2,
                    (self.nodes[a].y + self.nodes[b].y) / 2)
        node = self.nodes[step]
        return (node.x, node.y)

    def _set_turn(self, n, duration, clear_trails=False):
        """Put every drone where it is after n steps (0 = at the start)."""
        self.turn_index = clamp(n, 0, self.total_steps)
        self.step_timer = 0
        for drone, path in zip(self.drones, self.turns):
            if self.turn_index == 0 or not path:
                pos = (self.start.x, self.start.y)
            else:
                pos = self._step_pos(path[min(self.turn_index, len(path)) - 1])
            if duration <= 0:
                drone.reset(pos)
            else:
                if clear_trails:
                    drone.trail.clear()
                drone.move_drone(pos, duration)

    def next_step(self):
        if not self.is_finished():
            # the move takes ~90% of a turn so drones arrive before the next
            self._set_turn(self.turn_index + 1, self.step_delay * 0.9)

    def previous_step(self):
        if self.turn_index > 0:
            self._set_turn(self.turn_index - 1, 350, clear_trails=True)

    def restart(self):
        self._set_turn(0, 0)

    # ------------------------------------------------------------------ #
    # Drawing
    # ------------------------------------------------------------------ #
    def draw(self):
        self.screen.blit(self.bg_image, (0, 0))
        self.draw_connections()
        self.draw_zones()
        if self.show_trails:
            self.draw_trails()
        self.draw_drones()
        self.draw_hud()
        self.draw_legend()
        self.draw_timeline()
        self.draw_tooltip()
        pygame.display.flip()

    def draw_connections(self):
        seen = set()
        for node in self.nodes.values():
            for neighbor in node.neighbors.values():
                key = frozenset((id(node), id(neighbor.node)))
                if key in seen:
                    continue
                seen.add(key)
                a = self._to_screen(node.x, node.y)
                b = self._to_screen(neighbor.node.x, neighbor.node.y)
                width = max(2, int(3 * self.view_factor))
                pygame.draw.line(self.screen, (20, 22, 30), a, b, width + 5)
                pygame.draw.line(self.screen, (135, 145, 165), a, b, width)

    def draw_zones(self):
        r = self.node_radius
        ring = max(2, int(4 * self.view_factor))
        pulse = (math.sin(self.time * 0.004) + 1) / 2
        for name, node in self.nodes.items():
            center = self._to_screen(node.x, node.y)
            zone = node.zone_type
            border = ZONE_COLORS.get(zone, ZONE_COLORS["normal"])
            try:
                fill = pygame.Color(node.color)
            except (ValueError, TypeError):
                fill = pygame.Color(120, 120, 140)
            if zone == "priority":           # breathing halo
                pygame.draw.circle(
                    self.screen, border, center, r + 5 + int(4 * pulse), 2
                )
            elif zone == "restricted":
                pygame.draw.circle(self.screen, border, center, r + 6, 1)
            pygame.draw.circle(
                self.screen, (10, 12, 18), (center[0] + 3, center[1] + 4),
                r + 2
            )
            pygame.draw.circle(self.screen, fill, center, r)
            pygame.draw.circle(self.screen, border, center, r, ring)
            if zone == "blocked":
                d = int(r * 0.45)
                for sx, sy in ((-1, -1), (-1, 1)):
                    pygame.draw.line(
                        self.screen, (235, 235, 235),
                        (center[0] + sx * d, center[1] + sy * d),
                        (center[0] - sx * d, center[1] - sy * d), 3
                    )
            if name == self.hover_name:
                pygame.draw.circle(
                    self.screen, (255, 255, 255), center, r + 8, 2
                )
            pill = self._pill(name, self.font, TEXT)
            self.screen.blit(
                pill, pill.get_rect(midtop=(center[0], center[1] + r + 4))
            )
            tag = None
            if node is self.start:
                tag = ("START", GREEN)
            elif self.end is not None and node is self.end:
                tag = ("GOAL", GOLD)
            if tag:
                pill = self._pill(tag[0], self.font, tag[1])
                self.screen.blit(
                    pill,
                    pill.get_rect(midbottom=(center[0], center[1] - r - 6))
                )

    def draw_trails(self):
        overlay = self.trail_surface
        overlay.fill((0, 0, 0, 0))
        for drone in self.drones:
            points = [self._to_screen(x, y) for x, y in drone.trail]
            n = len(points)
            for i in range(1, n):
                alpha = int(200 * i / n)
                pygame.draw.line(
                    overlay, (*drone.color, alpha),
                    points[i - 1], points[i], 3
                )
        self.screen.blit(overlay, (0, 0))

    def draw_drones(self):
        zf = self.view_factor
        size = max(int(40 * zf), 12)
        show_labels = len(self.drones) <= 30 or self.zoom >= 1.2
        for drone in sorted(self.drones, key=lambda d: -d.y):
            cx, cy = self._to_screen(drone.x, drone.y)
            cx += drone.offset[0] * zf
            cy += drone.offset[1] * zf
            bob = 0.0
            angle = 0
            if drone.moving:                 # lean into the movement
                speed = drone.vx * self.scale * self.zoom
                angle = 3 * round(clamp(-speed * 110, -18, 18) / 3)
            else:                            # idle hover
                bob = math.sin(self.time * 0.004 + drone.phase) * 3 * zf
            shadow = self._shadow(size)
            self.screen.blit(
                shadow, shadow.get_rect(center=(cx, cy + size * 0.55))
            )
            sprite = self._sprite(size, angle)
            self.screen.blit(sprite, sprite.get_rect(center=(cx, cy + bob)))
            if show_labels:
                pill = self._pill(drone.name, self.font, drone.color)
                self.screen.blit(
                    pill,
                    pill.get_rect(midbottom=(cx, cy + bob - size * 0.5))
                )

    def draw_hud(self):
        rect = pygame.Rect(16, 16, 260, 104)
        self._panel(rect)
        turn = max(self.turn_index - 1, 0)
        total = max(self.total_steps - 1, 0)
        if self.is_finished():
            state, color = "FINISHED", ACCENT
        elif self.auto_play:
            state, color = "PLAYING", GREEN
        else:
            state, color = "PAUSED", AMBER
        label = self._text("TURN", self.font, MUTED)
        self.screen.blit(label, (rect.left + 16, rect.top + 12))
        chip = self._text(state, self.font, color)
        self.screen.blit(
            chip, chip.get_rect(topright=(rect.right - 16, rect.top + 12))
        )
        big = self._text(f"{turn} / {total}", self.big_font, TEXT)
        self.screen.blit(big, (rect.left + 16, rect.top + 30))
        done = sum(
            1 for d, p in zip(self.drones, self.turns)
            if self.turn_index >= len(p) and not d.moving
        )
        info = self._text(
            f"{done}/{self.nb_drones} paths done  |  "
            f"{self.step_delay} ms/turn",
            self.font, MUTED
        )
        self.screen.blit(info, (rect.left + 16, rect.bottom - 26))

    def draw_legend(self):
        rows = [("Normal", "normal"), ("Priority", "priority"),
                ("Restricted", "restricted"), ("Blocked", "blocked"),
                ("Start", GREEN)]
        if self.end is not None:
            rows.append(("Goal", GOLD))
        rect = pygame.Rect(0, 16, 150, 20 + 26 * len(rows))
        rect.right = self.width - 16
        self._panel(rect)
        for i, (name, kind) in enumerate(rows):
            cy = rect.top + 24 + i * 26
            cx = rect.left + 24
            if isinstance(kind, str):
                pygame.draw.circle(self.screen, (70, 75, 90), (cx, cy), 8)
                pygame.draw.circle(
                    self.screen, (200, 200, 205), (cx, cy), 10, 1
                )
                pygame.draw.circle(self.screen, ZONE_COLORS[kind],
                                   (cx, cy), 8, 3)
            else:
                pygame.draw.circle(self.screen, kind, (cx, cy), 8)
            text = self._text(name, self.font, TEXT)
            self.screen.blit(text, text.get_rect(midleft=(cx + 20, cy)))

    def _timeline_rect(self):
        return pygame.Rect(28, self.height - 30, self.width - 56, 8)

    def _timeline_hit(self, pos):
        return self._timeline_rect().inflate(16, 26).collidepoint(pos)

    def draw_timeline(self):
        panel_h = 66 if self.show_help else 40
        panel = pygame.Rect(
            12, self.height - 10 - panel_h, self.width - 24, panel_h
        )
        self._panel(panel)
        if self.show_help:
            help_text = (
                "SPACE play/pause | LEFT/RIGHT step | UP/DOWN speed | "
                "R restart | T trails | F fit view | H hide help | "
                "wheel zoom, drag pan"
            )
            text = self._text(help_text, self.font, MUTED)
            self.screen.blit(
                text, text.get_rect(midtop=(panel.centerx, panel.top + 10))
            )
        track = self._timeline_rect()
        frac = (self.turn_index / self.total_steps) if self.total_steps else 0
        pygame.draw.rect(self.screen, (60, 66, 82), track, border_radius=4)
        fill = track.copy()
        fill.width = int(track.width * frac)
        if fill.width > 0:
            pygame.draw.rect(self.screen, ACCENT, fill, border_radius=4)
        knob = (track.left + int(track.width * frac), track.centery)
        pygame.draw.circle(self.screen, (255, 255, 255), knob, 8)

    def draw_tooltip(self):
        if not self.hover_name:
            return
        node = self.nodes[self.hover_name]
        here = [
            d.name for d in self.drones
            if not d.moving and abs(d.x - node.x) < 0.01
            and abs(d.y - node.y) < 0.01
        ]
        zone_color = ZONE_COLORS.get(node.zone_type, MUTED)
        if sum(zone_color) < 150:
            zone_color = MUTED
        lines = [
            (self.hover_name, self.mid_font, TEXT),
            (f"Zone: {node.zone_type}", self.font, zone_color),
            (f"Position: ({node.x}, {node.y})", self.font, MUTED),
        ]
        if here:
            shown = ", ".join(here[:6])
            if len(here) > 6:
                shown += f" +{len(here) - 6}"
            lines.append((f"Drones ({len(here)}): {shown}", self.font, TEXT))
        else:
            lines.append(("No drones", self.font, MUTED))
        surfs = [self._text(t, f, c) for t, f, c in lines]
        w = max(s.get_width() for s in surfs) + 24
        h = sum(s.get_height() + 3 for s in surfs) + 18
        mx, my = pygame.mouse.get_pos()
        rect = pygame.Rect(mx + 16, my + 16, w, h)
        rect.clamp_ip(self.screen.get_rect())
        self._panel(rect, alpha=230)
        y = rect.top + 9
        for surf in surfs:
            self.screen.blit(surf, (rect.left + 12, y))
            y += surf.get_height() + 3

    # ------------------------------------------------------------------ #
    # Drawing helpers (cached so they stay cheap every frame)
    # ------------------------------------------------------------------ #
    def _build_surfaces(self):
        bg = pygame.transform.smoothscale(
            self.bg_src, (self.width, self.height)
        )
        dim = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        dim.fill((0, 0, 20, 70))             # slight dim for contrast
        bg.blit(dim, (0, 0))
        self.bg_image = bg
        self.trail_surface = pygame.Surface(
            (self.width, self.height), pygame.SRCALPHA
        )

    def _panel(self, rect, alpha=185):
        surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(
            surf, (*PANEL, alpha), surf.get_rect(), border_radius=10
        )
        pygame.draw.rect(
            surf, (255, 255, 255, 40), surf.get_rect(), 1, border_radius=10
        )
        self.screen.blit(surf, rect.topleft)

    def _text(self, text, font, color):
        key = (text, id(font), tuple(color))
        surf = self._texts.get(key)
        if surf is None:
            if len(self._texts) > 600:
                self._texts.clear()
            surf = font.render(text, True, color)
            self._texts[key] = surf
        return surf

    def _pill(self, text, font, color):
        key = (text, id(font), tuple(color))
        surf = self._pills.get(key)
        if surf is None:
            label = font.render(text, True, color)
            surf = pygame.Surface(
                (label.get_width() + 12, label.get_height() + 4),
                pygame.SRCALPHA
            )
            pygame.draw.rect(
                surf, (*PANEL, 175), surf.get_rect(), border_radius=8
            )
            surf.blit(label, (6, 2))
            self._pills[key] = surf
        return surf

    def _sprite(self, size, angle):
        key = (size, angle)
        surf = self._sprites.get(key)
        if surf is None:
            surf = pygame.transform.smoothscale(
                self.drone_src, (size, size)
            )
            if angle:
                surf = pygame.transform.rotate(surf, angle)
            self._sprites[key] = surf
        return surf

    def _shadow(self, size):
        surf = self._shadows.get(size)
        if surf is None:
            surf = pygame.Surface(
                (max(int(size * 0.7), 4), max(int(size * 0.22), 2)),
                pygame.SRCALPHA
            )
            pygame.draw.ellipse(surf, (0, 0, 0, 90), surf.get_rect())
            self._shadows[size] = surf
        return surf

    # ------------------------------------------------------------------ #
    # Drones / coordinates / camera
    # ------------------------------------------------------------------ #
    def creat_drones(self):
        for i in range(self.nb_drones):
            self.drones.append(
                DroneDisplay(
                    (self.start.x, self.start.y), self.drone_src, i + 1
                )
            )

    @property
    def view_factor(self):
        """Size multiplier for drones and lines (clamped, so they stay
        readable when zooming far in or out)."""
        return clamp(self.zoom, 0.6, 1.6)

    @property
    def node_radius(self):
        return int(22 * clamp(self.zoom, 0.6, 2.0))

    def _to_screen(self, x, y):
        p_x = self.offset_x + x * self.scale
        p_y = self.offset_y - y * self.scale
        c_x = self.width / 2
        c_y = self.height / 2
        return (round(c_x + (p_x - c_x) * self.zoom + self.pan_x),
                round(c_y + (p_y - c_y) * self.zoom + self.pan_y))

    def zoom_at(self, factor, mouse):
        """Zoom while keeping the point under the cursor fixed."""
        new = clamp(self.zoom * factor, 0.3, 5)
        c_x = self.width / 2
        c_y = self.height / 2
        ratio = new / self.zoom
        self.pan_x = mouse[0] - c_x - (mouse[0] - self.pan_x - c_x) * ratio
        self.pan_y = mouse[1] - c_y - (mouse[1] - self.pan_y - c_y) * ratio
        self.zoom = new

    def reset_view(self):
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0

    def fit_to_window(self):
        margin_x = 90
        margin_y = 130                       # room for the HUD + timeline
        xs = [node.x for node in self.nodes.values()]
        ys = [node.y for node in self.nodes.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        map_w = max(max_x - min_x, 1)
        map_h = max(max_y - min_y, 1)
        avail_w = max(self.width - 2 * margin_x, 50)
        avail_h = max(self.height - 2 * margin_y, 50)

        self.scale = min(avail_w / map_w, avail_h / map_h)
        extra_x = avail_w - map_w * self.scale
        extra_y = avail_h - map_h * self.scale
        self.offset_x = margin_x + extra_x / 2 - min_x * self.scale
        # y is flipped in _to_screen, so anchor on max_y
        self.offset_y = margin_y + extra_y / 2 + max_y * self.scale
        self.reset_view()