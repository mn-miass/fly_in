import colorsys
import math
import os
import random
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
RED = (255, 95, 95)
TEXT = (235, 238, 245)
MUTED = (150, 158, 175)
PANEL = (10, 14, 24)
ARRIVAL_MS = 600

HELP = [
    ("PLAYBACK", [
        "SPACE  play / pause (replays when finished)",
        "LEFT / RIGHT  step back / forward",
        "UP / DOWN  change speed",
        "R  restart   |   click or drag the timeline to seek",
    ]),
    ("VIEW", [
        "mouse wheel  zoom   |   drag  pan   |   F  fit view",
        "C  follow the selected drone   |   N  minimap",
        "G  grid   |   T  trails   |   F11  fullscreen",
    ]),
    ("ANALYSIS", [
        "click a drone (or TAB)  select it and show its route",
        "M  traffic heatmap   |   I  analytics   |   L  move log",
        "hover a zone for details",
    ]),
    ("OTHER", ["S  screenshot   |   H  this help   |   ESC  quit"]),
]


def clamp(value, low, high):
    return max(low, min(value, high))


def mix(color, other, t):
    return tuple(int(color[i] + (other[i] - color[i]) * t) for i in range(3))


def heat_color(t):
    t = clamp(t, 0.0, 1.0)
    if t < 0.5:
        return mix((55, 95, 190), (250, 215, 90), t * 2)
    return mix((250, 215, 90), (240, 70, 60), (t - 0.5) * 2)


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
        self.phase = drone_id * 1.7         # desync hover + rotors
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
    """Pygame viewer / analyser for the Fly_in simulation.

    bg_path / drone_path are optional: without them the background and the
    drones are generated in code, so no asset files are needed.
    Zones may expose a capacity (``max_drones``, ``capacity`` or
    ``max_capacity``); when they do, overloads are detected and flagged.
    """

    def __init__(self, nodes, start_node, nb_drones, turns,
                 step_delay=800, auto_play=True, end_node=None,
                 bg_path=None, drone_path=None):
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
        self.width = max(int(info.current_w * 0.7), 1000)
        self.height = max(int(info.current_h * 0.75), 640)
        self.screen = pygame.display.set_mode(
            (self.width, self.height), pygame.RESIZABLE
        )
        pygame.display.set_caption("Fly_in")
        self.bg_src = self._load(bg_path, alpha=False)
        self.drone_src = self._load(drone_path, alpha=True)
        # camera (current values are smoothed towards the targets)
        self.zoom = self.zoom_t = 1.0
        self.pan_x = self.pan_y = 0.0
        self.pan_tx = self.pan_ty = 0.0
        self.follow = False
        # interaction state
        self.dragging = False
        self.map_drag = False
        self.click_start = (0, 0)
        self.click_moved = False
        self.seeking = False
        self.resume_after_seek = False
        # toggles
        self.show_trails = True
        self.show_grid = True
        self.show_help = False
        self.show_stats = True
        self.show_minimap = True
        self.show_log = False
        self.heat = False
        # runtime data
        self.hover_name = None
        self.selected = None                # index of the selected drone
        self.groups = {}
        self.effects = []                   # arrival ripples
        self.finished_at = None
        self._hit = []
        self._mm_rect = None
        self._mm_tf = (0, 0, 1)
        self._path_cache = {}
        rng = random.Random(3)
        self.motes = [[rng.random(), rng.random(), rng.uniform(0.4, 1.4),
                       rng.randint(1, 3), rng.random() * 6.28]
                      for _ in range(70)]
        # caches
        self._texts = {}
        self._pills = {}
        self._sprites = {}
        self._shadows = {}
        self._glows = {}
        self._discs = {}
        self.clock = pygame.time.Clock()
        self.running = True
        self.drones = []
        self._prepare_graph()
        self._build_stats()
        self._build_surfaces()
        self.fit_to_window()
        self.creat_drones()

    @staticmethod
    def _load(path, alpha):
        if not path or not os.path.exists(path):
            return None
        image = pygame.image.load(path)
        return image.convert_alpha() if alpha else image.convert()

    # ------------------------------------------------------------------ #
    # Pre-computed analysis of the whole run
    # ------------------------------------------------------------------ #
    def _prepare_graph(self):
        self.names = {id(n): name for name, n in self.nodes.items()}
        self.start_name = self.names.get(id(self.start), "__start__")
        self.end_name = (self.names.get(id(self.end))
                         if self.end is not None else None)
        self.edges = {}
        for name, node in self.nodes.items():
            for neighbor in node.neighbors.values():
                other = self.names.get(id(neighbor.node))
                if other is None:
                    continue
                key = frozenset((name, other))
                self.edges.setdefault(key, (node, neighbor.node))

    @staticmethod
    def _capacity(node):
        for attr in ("max_drones", "capacity", "max_capacity"):
            value = getattr(node, attr, None)
            if isinstance(value, int) and not isinstance(value, bool):
                return value
        return None

    def _name_at(self, path, t):
        """Where a drone is after t steps (0 = at the start)."""
        if t <= 0 or not path:
            return self.start_name
        return path[min(t, len(path)) - 1]

    def _transition(self, prev, cur):
        """(zone entered, connection used) when a drone goes prev -> cur."""
        if cur in self.nodes:
            edge = None
            if prev in self.nodes:
                edge = frozenset((prev, cur))
            return cur, edge
        if "-" in cur:                       # enters a connection
            a, b = cur.split("-", 1)
            return None, frozenset((a, b))
        return None, None

    def _build_stats(self):
        total = self.total_steps
        self.moves_series = [0] * (total + 1)
        self.delivered_series = [0] * (total + 1)
        self.violations = {}
        visit_inc = {}
        edge_inc = {}
        for t in range(total + 1):
            counts = {}
            for path in self.turns:
                cur = self._name_at(path, t)
                counts[cur] = counts.get(cur, 0) + 1
                if t == 0:
                    continue
                prev = self._name_at(path, t - 1)
                if prev == cur:
                    continue
                self.moves_series[t] += 1
                entered, edge = self._transition(prev, cur)
                if entered is not None:
                    bucket = visit_inc.setdefault(entered, {})
                    bucket[t] = bucket.get(t, 0) + 1
                if edge is not None:
                    bucket = edge_inc.setdefault(edge, {})
                    bucket[t] = bucket.get(t, 0) + 1
            if self.end_name is not None:
                self.delivered_series[t] = counts.get(self.end_name, 0)
            else:
                self.delivered_series[t] = sum(
                    1 for p in self.turns if t >= len(p))
            for name, count in counts.items():
                node = self.nodes.get(name)
                cap = self._capacity(node) if node is not None else None
                if cap is not None and count > cap:
                    self.violations.setdefault(t, []).append(
                        (name, count, cap))

        def prefix(inc):
            arr, run = [0] * (total + 1), 0
            for t in range(total + 1):
                run += inc.get(t, 0)
                arr[t] = run
            return arr

        self.visit_prefix = {k: prefix(v) for k, v in visit_inc.items()}
        self.edge_prefix = {k: prefix(v) for k, v in edge_inc.items()}
        self.max_visits = max(
            (a[-1] for a in self.visit_prefix.values()), default=1) or 1
        self.max_edge = max(
            (a[-1] for a in self.edge_prefix.values()), default=1) or 1

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
            self.update_camera(dt)
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
        self.groups = groups
        for drone in self.drones:
            was_moving = drone.moving
            drone.update(dt)
            if was_moving and not drone.moving and self._on_node(drone):
                self.effects.append([drone.x, drone.y, 0.0, drone.color])
        for effect in self.effects:
            effect[2] += dt
        self.effects = [e for e in self.effects if e[2] < ARRIVAL_MS]
        if self.is_finished():
            if (self.finished_at is None
                    and not any(d.moving for d in self.drones)):
                self.finished_at = self.time
        else:
            self.finished_at = None

    def update_camera(self, dt):
        c_x, c_y = self.width / 2, self.height / 2
        if self.follow and self.selected is not None:
            drone = self.drones[self.selected]
            bx = self.offset_x + drone.x * self.scale
            by = self.offset_y - drone.y * self.scale
            self.pan_tx = -(bx - c_x) * self.zoom_t
            self.pan_ty = -(by - c_y) * self.zoom_t
        k = 1 - math.exp(-dt / 100)
        self.zoom += (self.zoom_t - self.zoom) * k
        self.pan_x += (self.pan_tx - self.pan_x) * k
        self.pan_y += (self.pan_ty - self.pan_y) * k

    def _on_node(self, drone):
        return any(abs(n.x - drone.x) < 0.01 and abs(n.y - drone.y) < 0.01
                   for n in self.nodes.values())

    @staticmethod
    def _spread(i, n):
        """Fan out drones sharing a zone so none is hidden."""
        if n <= 8:
            angle = 2 * math.pi * i / n - math.pi / 2
            radius = 16 + 5 * n
        else:
            angle = i * 2.39996
            radius = 22 * math.sqrt(i + 0.5)
        return (math.cos(angle) * radius, math.sin(angle) * radius)

    def is_finished(self):
        return self.total_steps == 0 or self.turn_index >= self.total_steps

    def update_hover(self):
        self.hover_name = None
        if (self.dragging or self.seeking or self.map_drag
                or not pygame.mouse.get_focused()):
            return
        mouse = pygame.mouse.get_pos()
        if self._timeline_hit(mouse):
            return
        if self._mm_rect is not None and self._mm_rect.collidepoint(mouse):
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
                elif (self._mm_rect is not None
                      and self._mm_rect.collidepoint(event.pos)):
                    self.map_drag = True
                    self._minimap_jump(event.pos)
                else:
                    self.dragging = True
                    self.click_start = event.pos
                    self.click_moved = False
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.seeking:
                    self.seeking = False
                    self.auto_play = self.resume_after_seek
                elif self.dragging and not self.click_moved:
                    self._click(event.pos)
                self.dragging = False
                self.map_drag = False
            elif event.type == pygame.MOUSEMOTION:
                if self.seeking:
                    self._seek(event.pos[0])
                elif self.map_drag:
                    self._minimap_jump(event.pos)
                elif self.dragging:
                    self.pan_x += event.rel[0]
                    self.pan_y += event.rel[1]
                    self.pan_tx += event.rel[0]
                    self.pan_ty += event.rel[1]
                    if math.hypot(event.pos[0] - self.click_start[0],
                                  event.pos[1] - self.click_start[1]) > 4:
                        self.click_moved = True
                        self.follow = False

    def _on_key(self, key):
        if key == pygame.K_ESCAPE:
            if self.show_help:
                self.show_help = False
            else:
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
        elif key == pygame.K_g:
            self.show_grid = not self.show_grid
        elif key == pygame.K_h:
            self.show_help = not self.show_help
        elif key == pygame.K_m:
            self.heat = not self.heat
        elif key == pygame.K_i:
            self.show_stats = not self.show_stats
        elif key == pygame.K_l:
            self.show_log = not self.show_log
        elif key == pygame.K_n:
            self.show_minimap = not self.show_minimap
        elif key == pygame.K_c:
            if self.selected is not None:
                self.follow = not self.follow
        elif key == pygame.K_f:
            self.follow = False
            self.reset_view()
        elif key == pygame.K_TAB and self.drones:
            nxt = 0 if self.selected is None else self.selected + 1
            self.selected = nxt % len(self.drones)
        elif key == pygame.K_s:
            self.save_screenshot()
        elif key == pygame.K_F11:
            self.toggle_fullscreen()

    def _on_resize(self, w, h):
        self.width = max(w, 320)
        self.height = max(h, 240)
        self.screen = pygame.display.get_surface()
        self._build_surfaces()
        self.fit_to_window()

    def toggle_fullscreen(self):
        try:
            pygame.display.toggle_fullscreen()
            width, height = pygame.display.get_surface().get_size()
            self._on_resize(width, height)
        except pygame.error:
            pass

    def _click(self, pos):
        """Select the drone under the cursor (or clear the selection)."""
        self.selected = None
        self.follow = False
        for idx, cx, cy, radius in reversed(self._hit):
            if (pos[0] - cx) ** 2 + (pos[1] - cy) ** 2 <= radius ** 2:
                self.selected = idx
                return

    def _seek(self, mouse_x):
        target = self._turn_at_x(mouse_x)
        if target != self.turn_index:
            self._set_turn(target, 250, clear_trails=True)

    def _turn_at_x(self, mouse_x):
        track = self._timeline_rect()
        frac = clamp((mouse_x - track.left) / max(track.width, 1), 0, 1)
        return round(frac * self.total_steps)

    def save_screenshot(self):
        name = f"fly_in_turn_{max(self.turn_index - 1, 0)}.png"
        pygame.image.save(self.screen, name)

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
        self.effects.clear()
        self._set_turn(0, 0)

    # ------------------------------------------------------------------ #
    # Drawing: the world
    # ------------------------------------------------------------------ #
    def draw(self):
        self.draw_backdrop()
        self.draw_connections()
        self.draw_zones()
        self.draw_overlays()
        self.draw_drones()
        self.draw_left_column()
        bottom = self.draw_legend(16)
        self.draw_analytics(bottom + 10)
        self.draw_minimap()
        self.draw_banner()
        self.draw_timeline()
        self.draw_tooltip()
        if self.show_help:
            self.draw_help()
        pygame.display.flip()

    def draw_backdrop(self):
        self.screen.blit(self.bg_image, (0, 0))
        fx = self.back_fx
        fx.fill((0, 0, 0, 0))
        if self.show_grid:
            self._draw_grid(fx)
        self._draw_motes(fx)
        self.screen.blit(fx, (0, 0))

    def _draw_grid(self, fx):
        step_px = self.scale * self.zoom
        mult = 1
        while step_px * mult < 48:
            mult *= 2
        x_min, y_max = self._to_world(0, 0)
        x_max, y_min = self._to_world(self.width, self.height)
        i0, i1 = math.floor(x_min / mult), math.ceil(x_max / mult)
        j0, j1 = math.floor(y_min / mult), math.ceil(y_max / mult)
        if i1 - i0 > 250 or j1 - j0 > 250:
            return
        for i in range(i0, i1 + 1):
            sx = self._to_screen(i * mult, 0)[0]
            alpha = 40 if i % 5 == 0 else 18
            pygame.draw.line(fx, (150, 190, 255, alpha),
                             (sx, 0), (sx, self.height))
        for j in range(j0, j1 + 1):
            sy = self._to_screen(0, j * mult)[1]
            alpha = 40 if j % 5 == 0 else 18
            pygame.draw.line(fx, (150, 190, 255, alpha),
                             (0, sy), (self.width, sy))

    def _draw_motes(self, fx):
        """Slow floating dust that drifts with a little parallax."""
        for x, y, speed, radius, phase in self.motes:
            px = (x * self.width + self.time * 0.01 * speed
                  + self.pan_x * 0.15) % self.width
            py = (y * self.height - self.time * 0.006 * speed
                  + self.pan_y * 0.15) % self.height
            alpha = int(45 + 35 * math.sin(self.time * 0.002 + phase))
            pygame.draw.circle(fx, (170, 210, 255, alpha),
                               (int(px), int(py)), radius)

    def draw_connections(self):
        base = max(2, int(3 * self.view_factor))
        dot = max(2, int(2.5 * self.view_factor))
        for idx, (key, (node_a, node_b)) in enumerate(self.edges.items()):
            a = self._to_screen(node_a.x, node_a.y)
            b = self._to_screen(node_b.x, node_b.y)
            if self.heat:
                arr = self.edge_prefix.get(key)
                ratio = (arr[self.turn_index] / self.max_edge) if arr else 0
                width = base + int(6 * ratio)
                inner = heat_color(ratio)
                outer = mix(inner, (0, 0, 0), 0.6)
            else:
                width = base
                inner, outer = (150, 175, 215), (70, 90, 125)
            pygame.draw.line(self.screen, (12, 16, 26), a, b, width + 6)
            pygame.draw.line(self.screen, outer, a, b, width + 2)
            pygame.draw.line(self.screen, inner, a, b, width)
            t = (self.time * 0.00035 + idx * 0.37) % 1.0   # light pulse
            pos = (int(a[0] + (b[0] - a[0]) * t),
                   int(a[1] + (b[1] - a[1]) * t))
            pygame.draw.circle(self.screen, (225, 240, 255), pos, dot)

    def draw_zones(self):
        r = self.node_radius
        ring = max(2, int(4 * self.view_factor))
        pulse = (math.sin(self.time * 0.004) + 1) / 2
        over = {v[0] for v in self.violations.get(self.turn_index, ())}
        for name, node in self.nodes.items():
            center = self._to_screen(node.x, node.y)
            zone = node.zone_type
            border = ZONE_COLORS.get(zone, ZONE_COLORS["normal"])
            try:
                parsed = pygame.Color(node.color)
                fill = (parsed.r, parsed.g, parsed.b)
            except (ValueError, TypeError):
                fill = (120, 120, 140)
            visits = 0
            if self.heat:
                arr = self.visit_prefix.get(name)
                visits = arr[self.turn_index] if arr else 0
                fill = heat_color(visits / self.max_visits)
            if zone != "blocked":            # soft light pool under the node
                tint = fill if (zone == "normal" or self.heat) else border
                glow = self._glow(r * 2, tint)
                self.screen.blit(glow, glow.get_rect(center=center))
            if zone == "priority":           # breathing halo
                pygame.draw.circle(
                    self.screen, border, center, r + 5 + int(4 * pulse), 2
                )
            elif zone == "restricted":
                pygame.draw.circle(self.screen, border, center, r + 6, 1)
            if name in over:                 # capacity alarm
                pygame.draw.circle(
                    self.screen, RED, center, r + 10 + int(5 * pulse), 3
                )
            pygame.draw.circle(
                self.screen, (8, 10, 16), (center[0] + 3, center[1] + 4),
                r + 2
            )
            pygame.draw.circle(self.screen, mix(fill, (0, 0, 0), 0.35),
                               center, r)
            pygame.draw.circle(self.screen, fill, center, int(r * 0.86))
            pygame.draw.circle(
                self.screen, mix(fill, (255, 255, 255), 0.45),
                (center[0] - int(r * 0.2), center[1] - int(r * 0.25)),
                int(r * 0.42)
            )
            self._draw_glyph(zone, center, r)
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
            label = f"{name} ({visits})" if (self.heat and visits) else name
            pill = self._pill(label, self.font, TEXT)
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
            self._draw_badge(node, name, center, r, name in over)

    def _draw_glyph(self, zone, center, r):
        """Small icon so zone types are readable without relying on colour."""
        if r < 14:
            return
        cx, cy = center
        if zone == "priority":
            pygame.draw.polygon(
                self.screen, (235, 245, 255),
                self._star_points(cx, cy + 1, r * 0.5, r * 0.22)
            )
        elif zone == "restricted":
            s = r * 0.5
            pts = [(cx, cy - s), (cx - s, cy + s * 0.8),
                   (cx + s, cy + s * 0.8)]
            pygame.draw.polygon(self.screen, (255, 235, 235), pts, 2)
            pygame.draw.line(self.screen, (255, 235, 235),
                             (cx, cy - s * 0.3), (cx, cy + s * 0.2), 2)
            pygame.draw.circle(self.screen, (255, 235, 235),
                               (cx, int(cy + s * 0.5)), 1)

    @staticmethod
    def _star_points(cx, cy, r_out, r_in, n=5):
        pts = []
        for i in range(n * 2):
            radius = r_out if i % 2 == 0 else r_in
            angle = -math.pi / 2 + i * math.pi / n
            pts.append((cx + math.cos(angle) * radius,
                        cy + math.sin(angle) * radius))
        return pts

    def _draw_badge(self, node, name, center, r, overloaded):
        count = len(self.groups.get(
            (round(node.x, 2), round(node.y, 2)), ()))
        cap = self._capacity(node)
        if count < 2 and not overloaded:
            return
        text = f"{count}/{cap}" if cap is not None else str(count)
        color = RED if overloaded else ACCENT
        label = self._text(text, self.font, (8, 12, 24))
        rect = label.get_rect().inflate(12, 6)
        rect.center = (center[0] + int(r * 0.85), center[1] - int(r * 0.85))
        pygame.draw.rect(self.screen, color, rect, border_radius=9)
        pygame.draw.rect(self.screen, (255, 255, 255), rect, 2,
                         border_radius=9)
        self.screen.blit(label, label.get_rect(center=rect.center))

    def draw_overlays(self):
        fx = self.front_fx
        fx.fill((0, 0, 0, 0))
        if self.selected is not None and self.selected < len(self.turns):
            self._draw_selected_path(fx)
        for drone in self.drones:            # live flight lines
            if drone.moving:
                a = self._to_screen(drone.start_x, drone.start_y)
                b = self._to_screen(drone.target_x, drone.target_y)
                pygame.draw.line(fx, (*drone.color, 70), a, b, 5)
        if self.show_trails:
            for drone in self.drones:
                points = [self._to_screen(x, y) for x, y in drone.trail]
                n = len(points)
                for i in range(1, n):
                    pygame.draw.line(
                        fx, (*drone.color, int(200 * i / n)),
                        points[i - 1], points[i], 3
                    )
        for x, y, age, color in self.effects:   # arrival ripples
            t = age / ARRIVAL_MS
            radius = int((12 + 34 * t) * self.view_factor)
            pygame.draw.circle(
                fx, (*color, int(200 * (1 - t))), self._to_screen(x, y),
                radius, 2
            )
        self.screen.blit(fx, (0, 0))

    def _path_world(self, idx):
        pts = self._path_cache.get(idx)
        if pts is None:
            pts = [self._step_pos(s) for s in self.turns[idx]]
            self._path_cache[idx] = pts
        return pts

    def _draw_selected_path(self, fx):
        drone = self.drones[self.selected]
        path = self.turns[self.selected]
        pts = [self._to_screen(x, y) for x, y in self._path_world(
            self.selected)]
        k = max(min(self.turn_index, len(path)) - 1, 0)
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            if a == b:
                continue
            if i < k:                        # already flown: solid
                pygame.draw.line(fx, (*drone.color, 210), a, b, 4)
            else:                            # still to fly: dashed
                self._dashed(fx, (*drone.color, 170), a, b)
        for p in set(pts):
            pygame.draw.circle(fx, (*drone.color, 230), p, 5)
            pygame.draw.circle(fx, (255, 255, 255, 230), p, 5, 1)

    @staticmethod
    def _dashed(surf, color, a, b, width=3, dash=10, gap=8):
        dx, dy = b[0] - a[0], b[1] - a[1]
        dist = math.hypot(dx, dy)
        if dist < 1:
            return
        ux, uy = dx / dist, dy / dist
        pos = 0.0
        while pos < dist:
            end = min(pos + dash, dist)
            pygame.draw.line(
                surf, color, (a[0] + ux * pos, a[1] + uy * pos),
                (a[0] + ux * end, a[1] + uy * end), width
            )
            pos += dash + gap

    def draw_drones(self):
        zf = self.view_factor
        size = max(int(44 * zf), 14)
        show_labels = len(self.drones) <= 30 or self.zoom >= 1.2
        self._hit = []
        order = sorted(range(len(self.drones)),
                       key=lambda i: -self.drones[i].y)
        for idx in order:
            drone = self.drones[idx]
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
            self._hit.append((idx, cx, cy, size * 0.6))
            shadow = self._shadow(size)
            self.screen.blit(
                shadow, shadow.get_rect(center=(cx, cy + size * 0.55))
            )
            sprite = self._sprite(size, angle, drone.color)
            self.screen.blit(sprite, sprite.get_rect(center=(cx, cy + bob)))
            if self.drone_src is None:
                self._draw_rotors(cx, cy + bob, size, angle, drone)
            if idx == self.selected:
                pulse = 3 * math.sin(self.time * 0.008)
                pygame.draw.circle(
                    self.screen, drone.color, (int(cx), int(cy + bob)),
                    int(size * 0.68 + pulse), 2
                )
            if show_labels:
                pill = self._pill(drone.name, self.font, drone.color)
                self.screen.blit(
                    pill,
                    pill.get_rect(midbottom=(cx, cy + bob - size * 0.52))
                )

    def _draw_rotors(self, cx, cy, size, angle, drone):
        offset = size * 0.28
        radius = max(int(size * 0.2), 3)
        theta = math.radians(angle)
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        disc = self._rotor_disc(radius)
        spin = self.time * (0.06 if drone.moving else 0.035) + drone.phase
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            x, y = sx * offset, sy * offset
            rx = cx + x * cos_t + y * sin_t
            ry = cy - x * sin_t + y * cos_t
            self.screen.blit(disc, disc.get_rect(center=(int(rx), int(ry))))
            turn = spin if sx * sy > 0 else -spin
            for extra in (0, math.pi / 2):
                dx = math.cos(turn + extra) * radius * 0.95
                dy = math.sin(turn + extra) * radius * 0.95
                pygame.draw.line(
                    self.screen, (225, 235, 250),
                    (rx - dx, ry - dy), (rx + dx, ry + dy), 1
                )

    # ------------------------------------------------------------------ #
    # Drawing: interface panels
    # ------------------------------------------------------------------ #
    def draw_left_column(self):
        y = 16
        y += self._draw_hud(y)
        y += self._draw_alert(y)
        y += self._draw_selected(y)
        y += self._draw_log(y)

    def _draw_hud(self, y):
        rect = pygame.Rect(16, y, 260, 104)
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
        if self.end is not None:
            done = sum(
                1 for d in self.drones
                if not d.moving and abs(d.x - self.end.x) < 0.01
                and abs(d.y - self.end.y) < 0.01
            )
            word = "delivered"
        else:
            done = sum(
                1 for d, p in zip(self.drones, self.turns)
                if self.turn_index >= len(p) and not d.moving
            )
            word = "paths done"
        info = self._text(
            f"{done}/{self.nb_drones} {word}  |  {self.step_delay} ms/turn",
            self.font, MUTED
        )
        self.screen.blit(info, (rect.left + 16, rect.bottom - 26))
        return rect.height + 10

    def _draw_alert(self, y):
        viol = self.violations.get(self.turn_index)
        if not viol:
            return 0
        rows = viol[:4]
        rect = pygame.Rect(16, y, 260, 40 + len(rows) * 18)
        self._panel(rect, alpha=215, color=(46, 12, 16),
                    border=(255, 95, 95, 140))
        title = self._text("CAPACITY EXCEEDED", self.font, RED)
        self.screen.blit(title, (rect.left + 16, rect.top + 12))
        for i, (name, count, cap) in enumerate(rows):
            line = self._text(f"{name}: {count} drones (max {cap})",
                              self.font, TEXT)
            self.screen.blit(line, (rect.left + 16, rect.top + 34 + i * 18))
        return rect.height + 10

    def _draw_selected(self, y):
        if self.selected is None or self.selected >= len(self.turns):
            return 0
        drone = self.drones[self.selected]
        path = self.turns[self.selected]
        where = self._name_at(path, self.turn_index)
        rect = pygame.Rect(16, y, 260, 96)
        self._panel(rect)
        pygame.draw.circle(
            self.screen, drone.color, (rect.left + 24, rect.top + 22), 7
        )
        title = self._text(f"{drone.name} selected", self.mid_font, TEXT)
        self.screen.blit(title, (rect.left + 40, rect.top + 14))
        lines = [
            f"Now: {where}",
            f"Step {min(self.turn_index, len(path))}/{len(path)}",
            f"Follow: {'ON' if self.follow else 'off'}  (C)",
        ]
        for i, line in enumerate(lines):
            text = self._text(line, self.font, MUTED)
            self.screen.blit(text, (rect.left + 16, rect.top + 38 + i * 17))
        return rect.height + 10

    def _draw_log(self, y):
        if not self.show_log:
            return 0
        t = self.turn_index
        moves = []
        if t > 0:
            for i, path in enumerate(self.turns):
                prev, cur = self._name_at(path, t - 1), self._name_at(path, t)
                if prev != cur:
                    moves.append((i, prev, cur))
        rows = min(len(moves), 10)
        extra = 18 if len(moves) > rows else 0
        rect = pygame.Rect(16, y, 260, 40 + max(rows, 1) * 18 + extra)
        self._panel(rect)
        title = self._text(
            f"MOVES, TURN {max(t - 1, 0)}  ({len(moves)})", self.font, MUTED
        )
        self.screen.blit(title, (rect.left + 16, rect.top + 12))
        if not moves:
            none = self._text("no moves", self.font, MUTED)
            self.screen.blit(none, (rect.left + 16, rect.top + 34))
        for row, (i, prev, cur) in enumerate(moves[:rows]):
            line_y = rect.top + 34 + row * 18
            name = self._text(f"D{i + 1}", self.font, self.drones[i].color)
            self.screen.blit(name, (rect.left + 16, line_y))
            route = self._fit(f"{prev} > {cur}", self.font, 180)
            self.screen.blit(self._text(route, self.font, TEXT),
                             (rect.left + 62, line_y))
        if extra:
            more = self._text(f"+{len(moves) - rows} more", self.font, MUTED)
            self.screen.blit(more, (rect.left + 16, rect.bottom - 24))
        return rect.height + 10

    def _fit(self, text, font, max_w):
        if font.size(text)[0] <= max_w:
            return text
        while len(text) > 1 and font.size(text + "...")[0] > max_w:
            text = text[:-1]
        return text + "..."

    def draw_legend(self, y):
        entries = [("Normal", "normal"), ("Priority", "priority"),
                   ("Restricted", "restricted"), ("Blocked", "blocked"),
                   ("Start", GREEN)]
        if self.end is not None:
            entries.append(("Goal", GOLD))
        rows = (len(entries) + 1) // 2
        height = 16 + rows * 26 + (46 if self.heat else 0)
        rect = pygame.Rect(0, y, 250, height)
        rect.right = self.width - 16
        self._panel(rect)
        for i, (name, kind) in enumerate(entries):
            cx = rect.left + 24 + (i % 2) * 118
            cy = rect.top + 22 + (i // 2) * 26
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
        if self.heat:
            top = rect.top + 16 + rows * 26 + 2
            title = self._text("Traffic (visits so far)", self.font, MUTED)
            self.screen.blit(title, (rect.left + 16, top))
            bar = pygame.Rect(rect.left + 16, top + 20, rect.width - 32, 8)
            for px in range(bar.width):
                pygame.draw.line(self.screen,
                                 heat_color(px / (bar.width - 1)),
                                 (bar.left + px, bar.top),
                                 (bar.left + px, bar.bottom))
        return rect.bottom

    def draw_analytics(self, y):
        if not self.show_stats or self.total_steps == 0:
            return
        rect = pygame.Rect(0, y, 250, 206)
        rect.right = self.width - 16
        if rect.bottom > self.height - 90:      # no room on small windows
            return
        self._panel(rect)
        moves = self.moves_series
        total_turns = max(self.total_steps - 1, 0)
        word = "delivered" if self.end is not None else "paths done"
        lines = [
            (f"{total_turns} turns  |  {sum(moves)} moves  |  "
             f"peak {max(moves)}", MUTED),
            (f"{self.delivered_series[-1]}/{self.nb_drones} {word}", MUTED),
        ]
        if self.violations:
            lines.append((f"{len(self.violations)} turn(s) over capacity",
                          RED))
        for i, (line, color) in enumerate(lines):
            self.screen.blit(self._text(line, self.font, color),
                             (rect.left + 14, rect.top + 10 + i * 17))
        top = rect.top + 10 + max(len(lines), 2) * 17 + 8
        self.screen.blit(self._text("MOVES PER TURN", self.font, MUTED),
                         (rect.left + 14, top))
        self._chart(pygame.Rect(rect.left + 14, top + 16, rect.width - 28, 44),
                    moves, ACCENT, "bars")
        top += 68
        label = "DELIVERED" if self.end is not None else "PATHS COMPLETED"
        self.screen.blit(self._text(label, self.font, MUTED),
                         (rect.left + 14, top))
        self._chart(pygame.Rect(rect.left + 14, top + 16, rect.width - 28, 44),
                    self.delivered_series, GREEN, "line")

    def _chart(self, rect, series, color, kind):
        pygame.draw.rect(self.screen, (18, 24, 38), rect, border_radius=4)
        n = len(series)
        vmax = max(max(series), 1)
        inner = rect.h - 6
        if kind == "bars":
            for px in range(rect.w):
                i0 = int(px * n / rect.w)
                i1 = max(int((px + 1) * n / rect.w), i0 + 1)
                value = max(series[i0:i1])
                bar = int(inner * value / vmax)
                if bar:
                    pygame.draw.line(
                        self.screen, color, (rect.left + px, rect.bottom - 3),
                        (rect.left + px, rect.bottom - 3 - bar)
                    )
        else:
            pts = []
            for px in range(rect.w):
                i = min(int(px * (n - 1) / max(rect.w - 1, 1)), n - 1)
                pts.append((rect.left + px,
                            rect.bottom - 3 - int(inner * series[i] / vmax)))
            if len(pts) >= 2:
                pygame.draw.lines(self.screen, color, False, pts, 2)
        mx = rect.left + int(
            self.turn_index / max(self.total_steps, 1) * (rect.w - 1))
        pygame.draw.line(self.screen, (255, 255, 255),
                         (mx, rect.top), (mx, rect.bottom))

    # ---- minimap ------------------------------------------------------ #
    def _minimap_transform(self, rect):
        inner = rect.inflate(-20, -20)
        min_x, max_x, min_y, max_y = self.bounds
        map_w = max(max_x - min_x, 1)
        map_h = max(max_y - min_y, 1)
        scale = min(inner.w / map_w, inner.h / map_h)
        ox = inner.centerx - (min_x + max_x) / 2 * scale
        oy = inner.centery + (min_y + max_y) / 2 * scale
        return ox, oy, scale

    def draw_minimap(self):
        self._mm_rect = None
        if not self.show_minimap:
            return
        rect = pygame.Rect(0, 0, 210, 140)
        rect.bottomright = (self.width - 16, self.height - 82)
        if self.show_stats and self.total_steps and rect.top < 16 + 180 + 210:
            # keep clear of the analytics panel on small windows
            if rect.top < self._analytics_bottom():
                return
        self._mm_rect = rect
        self._panel(rect)
        ox, oy, scale = self._minimap_transform(rect)
        self._mm_tf = (ox, oy, scale)

        def mp(x, y):
            return (int(ox + x * scale), int(oy - y * scale))

        self.screen.set_clip(rect)
        for node_a, node_b in self.edges.values():
            pygame.draw.line(self.screen, (70, 85, 115),
                             mp(node_a.x, node_a.y), mp(node_b.x, node_b.y))
        for node in self.nodes.values():
            color = ZONE_COLORS.get(node.zone_type, ZONE_COLORS["normal"])
            if sum(color) < 150:
                color = (90, 90, 100)
            pygame.draw.circle(self.screen, color, mp(node.x, node.y), 3)
        for drone in self.drones:
            pygame.draw.circle(self.screen, drone.color,
                               mp(drone.x, drone.y), 2)
        x_min, y_max = self._to_world(0, 0)
        x_max, y_min = self._to_world(self.width, self.height)
        a, b = mp(x_min, y_max), mp(x_max, y_min)
        view = pygame.Rect(a, (max(b[0] - a[0], 4), max(b[1] - a[1], 4)))
        pygame.draw.rect(self.screen, (255, 255, 255), view, 1)
        self.screen.set_clip(None)

    def _analytics_bottom(self):
        legend_rows = 3
        legend_h = 16 + legend_rows * 26 + (46 if self.heat else 0)
        return 16 + legend_h + 10 + 206 + 10

    def _minimap_jump(self, pos):
        ox, oy, scale = self._minimap_transform(self._mm_rect)
        self.follow = False
        self.center_on((pos[0] - ox) / scale, (oy - pos[1]) / scale)

    def center_on(self, wx, wy):
        bx = self.offset_x + wx * self.scale
        by = self.offset_y - wy * self.scale
        self.pan_tx = -(bx - self.width / 2) * self.zoom_t
        self.pan_ty = -(by - self.height / 2) * self.zoom_t

    # ---- banner / timeline / tooltip / help ---------------------------- #
    def draw_banner(self):
        if self.finished_at is None:
            return
        t = clamp((self.time - self.finished_at) / 500, 0.0, 1.0)
        total_turns = max(self.total_steps - 1, 0)
        text = f"COMPLETE  |  {total_turns} turns"
        if self.end is not None:
            text += f"  |  {self.delivered_series[-1]}/{self.nb_drones} " \
                    f"delivered"
        if self.violations:
            text += "  |  capacity violations!"
        pill = self._pill(text, self.mid_font, GREEN)
        pill.set_alpha(int(255 * t))
        rect = pill.get_rect(midtop=(self.width // 2,
                                     16 - int(18 * (1 - t))))
        self.screen.blit(pill, rect)

    def _timeline_rect(self):
        return pygame.Rect(28, self.height - 30, self.width - 56, 8)

    def _timeline_hit(self, pos):
        return self._timeline_rect().inflate(16, 26).collidepoint(pos)

    def draw_timeline(self):
        panel = pygame.Rect(12, self.height - 72, self.width - 24, 62)
        self._panel(panel)
        hint = ("SPACE play/pause  |  LEFT/RIGHT step  |  click a drone to "
                "follow its route  |  H all controls")
        text = self._text(hint, self.font, MUTED)
        self.screen.blit(text, text.get_rect(
            midtop=(panel.centerx, panel.top + 10)))
        track = self._timeline_rect()
        total = max(self.total_steps, 1)
        frac = self.turn_index / total
        pygame.draw.rect(self.screen, (50, 58, 76), track, border_radius=4)
        fill = track.copy()
        fill.width = int(track.width * frac)
        if fill.width > 0:
            pygame.draw.rect(self.screen, ACCENT, fill, border_radius=4)
        for t in self.violations:            # red ticks: overloaded turns
            tx = track.left + int(track.width * t / total)
            pygame.draw.line(self.screen, RED, (tx, track.top - 7),
                             (tx, track.top - 2), 2)
        knob = (track.left + int(track.width * frac), track.centery)
        pygame.draw.circle(self.screen, (255, 255, 255), knob, 8)
        mouse = pygame.mouse.get_pos()
        if (self._timeline_hit(mouse) and pygame.mouse.get_focused()
                and self.total_steps):
            t = self._turn_at_x(mouse[0])
            label = (f"Turn {max(t - 1, 0)}  |  {self.moves_series[t]} moves"
                     f"  |  {self.delivered_series[t]} delivered")
            if t in self.violations:
                label += "  |  over capacity"
            pill = self._pill(label, self.font, TEXT)
            rect = pill.get_rect(midbottom=(mouse[0], track.top - 12))
            rect.clamp_ip(self.screen.get_rect())
            self.screen.blit(pill, rect)

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
        cap = self._capacity(node)
        if cap is not None:
            lines.append((f"Capacity: {cap}", self.font, MUTED))
        arr = self.visit_prefix.get(self.hover_name)
        if arr:
            lines.append((f"Visits so far: {arr[self.turn_index]} "
                          f"(total {arr[-1]})", self.font, MUTED))
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

    def draw_help(self):
        dim = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        dim.fill((0, 0, 8, 150))
        self.screen.blit(dim, (0, 0))
        height = 30 + sum(30 + len(items) * 20 for _, items in HELP)
        rect = pygame.Rect(0, 0, 560, height)
        rect.center = (self.width // 2, self.height // 2)
        self._panel(rect, alpha=240)
        y = rect.top + 20
        for title, items in HELP:
            self.screen.blit(self._text(title, self.font, ACCENT),
                             (rect.left + 24, y))
            y += 24
            for item in items:
                self.screen.blit(self._text(item, self.font, TEXT),
                                 (rect.left + 40, y))
                y += 20
            y += 6

    # ------------------------------------------------------------------ #
    # Background (generated in code, or an image if bg_path was given)
    # ------------------------------------------------------------------ #
    def _build_surfaces(self):
        if self.bg_src is not None:
            bg = pygame.transform.smoothscale(
                self.bg_src, (self.width, self.height)
            )
            dim = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            dim.fill((0, 0, 20, 70))
            bg.blit(dim, (0, 0))
        else:
            bg = self._make_background()
        self.bg_image = bg
        self.back_fx = pygame.Surface(
            (self.width, self.height), pygame.SRCALPHA
        )
        self.front_fx = pygame.Surface(
            (self.width, self.height), pygame.SRCALPHA
        )

    def _make_background(self):
        w, h = self.width, self.height
        bg = pygame.Surface((w, h))
        top, bottom = (8, 14, 32), (12, 46, 60)
        for y in range(h):                   # vertical gradient
            pygame.draw.line(
                bg, mix(top, bottom, y / max(h - 1, 1)), (0, y), (w, y)
            )
        rng = random.Random(42)
        sw, sh = max(w // 8, 8), max(h // 8, 8)
        small = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for _ in range(7):                   # soft coloured light pools
            r = rng.randint(sw // 6, sw // 3)
            color = rng.choice([(40, 110, 210), (30, 180, 165),
                                (120, 70, 210)])
            blob = self._radial_surface(r, color, 70)
            small.blit(blob, (rng.randint(0, sw) - r, rng.randint(0, sh) - r))
        bg.blit(pygame.transform.smoothscale(small, (w, h)), (0, 0))
        for _ in range(max(w * h // 6000, 40)):   # stars
            shade = rng.randint(90, 210)
            pos = (rng.randint(0, w - 1), rng.randint(0, h - 1))
            pygame.draw.circle(bg, (shade, shade, min(shade + 30, 255)),
                               pos, 1 if rng.random() < 0.85 else 2)
        vig = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for yy in range(sh):                 # vignette
            for xx in range(sw):
                d = math.hypot((xx / sw - 0.5) * 2, (yy / sh - 0.5) * 2)
                d = min(d / 1.414, 1.0)
                alpha = int(150 * max(0.0, (d - 0.4) / 0.6) ** 2)
                vig.set_at((xx, yy), (0, 0, 8, alpha))
        bg.blit(pygame.transform.smoothscale(vig, (w, h)), (0, 0))
        return bg

    # ------------------------------------------------------------------ #
    # Drawing helpers (cached so they stay cheap every frame)
    # ------------------------------------------------------------------ #
    def _panel(self, rect, alpha=190, color=PANEL,
               border=(255, 255, 255, 40)):
        surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(
            surf, (*color, alpha), surf.get_rect(), border_radius=10
        )
        pygame.draw.rect(surf, border, surf.get_rect(), 1, border_radius=10)
        self.screen.blit(surf, rect.topleft)

    def _text(self, text, font, color):
        key = (text, id(font), tuple(color))
        surf = self._texts.get(key)
        if surf is None:
            if len(self._texts) > 800:
                self._texts.clear()
            surf = font.render(text, True, color)
            self._texts[key] = surf
        return surf

    def _pill(self, text, font, color):
        key = (text, id(font), tuple(color))
        surf = self._pills.get(key)
        if surf is None:
            if len(self._pills) > 800:
                self._pills.clear()
            label = font.render(text, True, color)
            surf = pygame.Surface(
                (label.get_width() + 12, label.get_height() + 4),
                pygame.SRCALPHA
            )
            pygame.draw.rect(
                surf, (*PANEL, 180), surf.get_rect(), border_radius=8
            )
            surf.blit(label, (6, 2))
            self._pills[key] = surf
        return surf

    @staticmethod
    def _radial_surface(radius, color, max_alpha, steps=16):
        radius = max(int(radius), 2)
        surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        for k in range(steps):
            r = max(int(radius * (1 - k / steps)), 1)
            alpha = int(max_alpha * ((k + 1) / steps) ** 2)
            pygame.draw.circle(surf, (*color, alpha), (radius, radius), r)
        return surf

    def _glow(self, radius, color):
        key = (int(radius), tuple(color))
        surf = self._glows.get(key)
        if surf is None:
            if len(self._glows) > 300:
                self._glows.clear()
            surf = self._radial_surface(radius, color, 85)
            self._glows[key] = surf
        return surf

    def _rotor_disc(self, radius):
        surf = self._discs.get(radius)
        if surf is None:
            surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(
                surf, (205, 225, 255, 55), (radius, radius), radius
            )
            pygame.draw.circle(
                surf, (230, 240, 255, 110), (radius, radius), radius, 1
            )
            self._discs[radius] = surf
        return surf

    def _sprite(self, size, angle, color):
        if self.drone_src is not None:       # user-supplied image
            key = (size, angle, None)
        else:
            key = (size, angle, tuple(color))
        surf = self._sprites.get(key)
        if surf is not None:
            return surf
        if self.drone_src is not None:
            surf = pygame.transform.smoothscale(
                self.drone_src, (size, size)
            )
        else:
            surf = self._draw_drone_body(size, color)
        if angle:
            surf = pygame.transform.rotate(surf, angle)
        self._sprites[key] = surf
        return surf

    @staticmethod
    def _draw_drone_body(size, color):
        """Top-down quadcopter body (the rotors are animated live)."""
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size / 2
        offset = size * 0.28
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            end = (c + sx * offset, c + sy * offset)
            pygame.draw.line(surf, (52, 58, 74), (c, c), end,
                             max(2, int(size * 0.08)))
            pygame.draw.circle(surf, (28, 32, 42), end,
                               max(2, int(size * 0.075)))
        body = int(size * 0.2)
        pygame.draw.circle(surf, (30, 34, 46), (c, c), body)
        pygame.draw.circle(surf, color, (c, c), body, max(2, int(size * 0.05)))
        pygame.draw.circle(surf, color, (c, c), max(2, int(size * 0.08)))
        pygame.draw.circle(
            surf, (255, 255, 255), (c - size * 0.025, c - size * 0.025),
            max(1, int(size * 0.03))
        )
        return surf

    def _shadow(self, size):
        surf = self._shadows.get(size)
        if surf is None:
            surf = pygame.Surface(
                (max(int(size * 0.7), 4), max(int(size * 0.22), 2)),
                pygame.SRCALPHA
            )
            pygame.draw.ellipse(surf, (0, 0, 0, 95), surf.get_rect())
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

    def _to_world(self, sx, sy):
        c_x = self.width / 2
        c_y = self.height / 2
        bx = c_x + (sx - self.pan_x - c_x) / self.zoom
        by = c_y + (sy - self.pan_y - c_y) / self.zoom
        return ((bx - self.offset_x) / self.scale,
                (self.offset_y - by) / self.scale)

    def zoom_at(self, factor, mouse):
        """Zoom (smoothly) while keeping the point under the cursor fixed."""
        new = clamp(self.zoom_t * factor, 0.3, 6)
        c_x = self.width / 2
        c_y = self.height / 2
        ratio = new / self.zoom_t
        self.pan_tx = mouse[0] - c_x - (mouse[0] - self.pan_tx - c_x) * ratio
        self.pan_ty = mouse[1] - c_y - (mouse[1] - self.pan_ty - c_y) * ratio
        self.zoom_t = new

    def reset_view(self):
        self.zoom_t = 1.0
        self.pan_tx = 0.0
        self.pan_ty = 0.0

    def fit_to_window(self):
        margin_x = 90
        margin_y = 140                       # room for the HUD + timeline
        xs = [node.x for node in self.nodes.values()]
        ys = [node.y for node in self.nodes.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        self.bounds = (min_x, max_x, min_y, max_y)

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
        self.zoom = 1.0                      # snap (no animation on fit)
        self.pan_x = self.pan_y = 0.0