import pygame


class DroneDisplay():
    def __init__(self, pos, image, drone_id):
        self.name = f"D{drone_id}"
        self.x = pos[0]
        self.y = pos[1]
        self.start_x = pos[0]
        self.start_y = pos[1]
        self.target_x = pos[0]
        self.target_y = pos[1]
        self.image = image
        self.progress = 1.0
        self.duration = 1.0

    def move_drone(self, new_coord, duration_ms):
        self.start_x = self.x
        self.start_y = self.y
        self.target_x = new_coord[0]
        self.target_y = new_coord[1]
        self.duration = max(duration_ms, 1)
        self.progress = 0.0

    def reset(self, pos):
        self.x = self.start_x = self.target_x = pos[0]
        self.y = self.start_y = self.target_y = pos[1]
        self.progress = 1.0

    def update(self, dt_ms):
        if self.progress >= 1.0:
            return
        self.progress = min(self.progress + dt_ms / self.duration, 1.0)
        # smoothstep easing: slow start, slow end
        t = self.progress * self.progress * (3 - 2 * self.progress)
        self.x = self.start_x + (self.target_x - self.start_x) * t
        self.y = self.start_y + (self.target_y - self.start_y) * t


class Display():
    def __init__(self, nodes, start_node, nb_drones, turns,
                 step_delay=800, auto_play=True):
        self.turns = turns
        self.turn_index = 0
        self.step_delay = step_delay      # ms between two turns
        self.auto_play = auto_play
        self.step_timer = 0
        pygame.init()
        self.font = pygame.font.Font(None, 20)
        self.big_font = pygame.font.Font(None, 36)
        self.nb_drones = nb_drones
        self.nodes = nodes
        self.start = start_node
        info = pygame.display.Info()
        self.width = info.current_w // 2
        self.height = info.current_h // 2
        bg_image = pygame.image.load("./assets/bg.webp")
        drone_image = pygame.image.load("./assets/drone.png")
        self.bg_image = pygame.transform.scale(
            bg_image, (self.width, self.height)
        )
        self.drone_image = pygame.transform.scale(drone_image, (40, 40))
        self.zoom = 1.0
        self.clock = pygame.time.Clock()
        self.running = True
        self.drones = []
        self.fit_to_window()
        self.creat_drones()

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #
    def run(self):
        pygame.display.set_caption("Fly_in")
        self.screen = pygame.display.set_mode((self.width, self.height))
        while self.running:
            dt = self.clock.tick(60)
            self.handle_events()
            self.auto_advance(dt)
            self.update_drones(dt)
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
        for drone in self.drones:
            drone.update(dt)

    def is_finished(self):
        if not self.turns:
            return True
        return self.turn_index >= max(len(path) for path in self.turns)

    # ------------------------------------------------------------------ #
    # Events
    # ------------------------------------------------------------------ #
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    self.auto_play = not self.auto_play      # pause / resume
                elif event.key == pygame.K_RIGHT and not self.auto_play:
                    self.next_step()                         # manual step
                elif event.key == pygame.K_UP:
                    self.step_delay = max(100, self.step_delay - 100)
                elif event.key == pygame.K_DOWN:
                    self.step_delay = min(3000, self.step_delay + 100)
                elif event.key == pygame.K_r:
                    self.restart()
            if event.type == pygame.MOUSEWHEEL:
                self.zoom = max(0.3, min(self.zoom * 1.1 ** event.y, 5))
            if event.type == pygame.MOUSEMOTION and event.buttons[0]:
                self.offset_x += event.rel[0] / self.zoom
                self.offset_y += event.rel[1] / self.zoom

    def restart(self):
        self.turn_index = 0
        self.step_timer = 0
        for drone in self.drones:
            drone.reset((self.start.x, self.start.y))

    # ------------------------------------------------------------------ #
    # Drawing
    # ------------------------------------------------------------------ #
    def draw(self):
        self.screen.blit(self.bg_image, (0, 0))
        self.draw_connections()
        self.draw_zones()
        self.draw_drones()
        self.draw_turn()
        self.draw_status()
        pygame.display.flip()

    def draw_turn(self):
        turn = max(self.turn_index - 1, 0)
        text = f"Turn: {turn}"
        label = self.big_font.render(text, True, pygame.Color("white"))
        rect = label.get_rect(topleft=(20, 20))
        pygame.draw.rect(
            self.screen, pygame.Color("black"), rect.inflate(20, 10)
        )
        self.screen.blit(label, rect)

    def draw_status(self):
        if self.is_finished():
            state = "Finished (R: restart)"
        elif self.auto_play:
            state = "Playing"
        else:
            state = "Paused (RIGHT: next turn)"
        text = (f"{state} | {self.step_delay} ms/turn | "
                f"SPACE: pause  UP/DOWN: speed")
        label = self.font.render(text, True, pygame.Color("white"))
        rect = label.get_rect(bottomleft=(20, self.height - 15))
        pygame.draw.rect(
            self.screen, pygame.Color("black"), rect.inflate(16, 8)
        )
        self.screen.blit(label, rect)

    def draw_zones(self):
        border = {
            "normal": pygame.Color("gray"),
            "blocked": pygame.Color("black"),
            "restricted": pygame.Color("red"),
            "priority": pygame.Color("blue")
        }
        for name, node in self.nodes.items():
            center = self._to_screen(node.x, node.y)
            try:
                fill_color = pygame.Color(node.color)
            except (ValueError, TypeError):
                fill_color = (120, 120, 140)
            pygame.draw.circle(self.screen, fill_color, center, 22)
            pygame.draw.circle(
                self.screen, border[node.zone_type], center, 22, 4
            )
            label = self.font.render(name, True, pygame.Color("black"))
            rect = label.get_rect(midtop=(center[0], center[1] + 28))
            self.screen.blit(label, rect)

    def draw_connections(self):
        for node in self.nodes.values():
            for neighbor in node.neighbors.values():
                start_px = self._to_screen(node.x, node.y)
                end_px = self._to_screen(neighbor.node.x, neighbor.node.y)
                pygame.draw.line(
                    self.screen, pygame.Color("black"), start_px, end_px, 2
                )

    def creat_drones(self):
        for i in range(self.nb_drones):
            self.drones.append(
                DroneDisplay(
                    (self.start.x, self.start.y), self.drone_image, i + 1
                )
            )

    def draw_drones(self):
        for drone in self.drones:
            center = self._to_screen(drone.x, drone.y)
            rect = drone.image.get_rect(center=center)
            self.screen.blit(drone.image, rect)
            label = self.font.render(drone.name, True, pygame.Color("black"))
            label_rect = label.get_rect(midbottom=(center[0], center[1] - 22))
            self.screen.blit(label, label_rect)

    # ------------------------------------------------------------------ #
    # Simulation steps
    # ------------------------------------------------------------------ #
    def apply_step(self, drone, step):
        if "-" in step:
            start_name, end_name = step.split("-", 1)
            x = (self.nodes[start_name].x + self.nodes[end_name].x) / 2
            y = (self.nodes[start_name].y + self.nodes[end_name].y) / 2
        else:
            x = self.nodes[step].x
            y = self.nodes[step].y
        # the move takes ~90% of a turn so drones arrive before the next one
        drone.move_drone((x, y), self.step_delay * 0.9)

    def next_step(self):
        if self.is_finished():
            return
        for drone, path in zip(self.drones, self.turns):
            if self.turn_index < len(path):
                self.apply_step(drone, path[self.turn_index])
        self.turn_index += 1

    # ------------------------------------------------------------------ #
    # Coordinates
    # ------------------------------------------------------------------ #
    def _to_screen(self, x, y):
        p_x = round(self.offset_x + x * self.scale)
        p_y = round(self.offset_y - y * self.scale)
        c_x = self.width / 2
        c_y = self.height / 2
        p_x = round(c_x + (p_x - c_x) * self.zoom)
        p_y = round(c_y + (p_y - c_y) * self.zoom)
        return (p_x, p_y)

    def fit_to_window(self):
        margin = 80
        max_x = max([node.x for node in self.nodes.values()])
        max_y = max([node.y for node in self.nodes.values()])
        min_x = min([node.x for node in self.nodes.values()])
        min_y = min([node.y for node in self.nodes.values()])

        map_w = max(max_x - min_x, 1)
        map_h = max(max_y - min_y, 1)
        avail_w = self.width - 2 * margin
        avail_h = self.height - 2 * margin

        self.scale = min(avail_w / map_w, avail_h / map_h)
        extra_x = avail_w - map_w * self.scale
        extra_y = avail_h - map_h * self.scale
        self.offset_x = margin + extra_x / 2 - min_x * self.scale
        # y is flipped in _to_screen, so anchor on max_y (not min_y)
        self.offset_y = margin + extra_y / 2 + max_y * self.scale