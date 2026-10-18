import pygame
import sys


class DroneDisplay():
    def __init__(self, pos, image, drone_id):
        self.name = f"D{drone_id}"
        self.x = pos[0]
        self.y = pos[1]
        self.target_x = pos[0]
        self.target_y = pos[1]
        self.image = image

    def move_drone(self, new_coord):
        self.target_x = new_coord[0]
        self.target_y = new_coord[1]

    def update(self):
        self.x += (self.target_x - self.x) * 0.1
        self.y += (self.target_y - self.y) * 0.1
        if abs(self.target_x - self.x) < 0.01:
            self.x = self.target_x
        if abs(self.target_y - self.y) < 0.01:
            self.y = self.target_y


class Display():
    def __init__(self, nodes, start_node, nb_drones, turns):
        self.turns = turns
        self.turn_index = 0
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

    def run(self):
        pygame.display.set_caption("Fly_in")
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.screen.blit(self.bg_image, (0, 0))
        while self.running:
            self.handle_events()
            self.update_drones()
            self.draw()
            self.clock.tick(60)
        pygame.quit()

    def update_drones(self):
        for drone in self.drones:
            drone.update()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                    sys.exit()
                if event.key == pygame.K_SPACE:
                    self.next_step()
            if event.type == pygame.MOUSEWHEEL:
                self.zoom = max(0.3, min(self.zoom * 1.1 ** event.y, 5))
            if event.type == pygame.MOUSEMOTION and event.buttons[0]:
                self.offset_x += event.rel[0] / self.zoom
                self.offset_y += event.rel[1] / self.zoom

    def draw(self):
        self.screen.blit(self.bg_image, (0, 0))
        self.draw_connections()
        self.draw_zones()
        self.draw_drones()
        self.draw_turn()
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
            pygame.draw.circle(
                self.screen, fill_color, center, 22
            )
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

    def apply_step(self, drone, step):
        if "-" in step:
            start_name, end_name = step.split("-", 1)
            x = (self.nodes[start_name].x + self.nodes[end_name].x) / 2
            y = (self.nodes[start_name].y + self.nodes[end_name].y) / 2
        else:
            x = self.nodes[step].x
            y = self.nodes[step].y
        drone.move_drone((x, y))

    def next_step(self):
        for drone, path in zip(self.drones, self.turns):
            if self.turn_index < len(path):
                self.apply_step(drone, path[self.turn_index])
        self.turn_index += 1

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
        self.offset_y = margin + extra_y / 2 - min_y * self.scale