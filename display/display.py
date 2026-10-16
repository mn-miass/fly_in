import pygame
import sys


class DroneDisplay():
    def __init__(self, pos, image):
        self.x = pos[0]
        self.y = pos[1]
        self.image = image

    def move_drone(self, new_coord):
        pass


class Display():
    def __init__(self, nodes, start_node, nb_drones):
        pygame.init()
        self.nb_drones = nb_drones;
        self.nodes = nodes;
        self.start = start_node
        info = pygame.display.Info()
        self.width = info.current_w // 2
        self.height = info.current_h // 2
        bg_image = pygame.image.load("./assets/bg.webp")
        drone_image = pygame.image.load("./assets/drone.png")
        self.bg_image = pygame.transform.scale(bg_image, (self.width, self.height))
        self.drone_image = pygame.transform.scale(drone_image, (40, 40))
        self.zoom = 1.0
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
            self.draw()
        pygame.quit()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if pygame.key == pygame.K_ESCAPE:
                    self.running = False
                    sys.exit()
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
        pygame.display.flip()


    def draw_zones(self):
        border = {
            "normal": pygame.Color("gray"),
            "blocked": pygame.Color("black"),
            "restricted": pygame.Color("red"),
            "priority": pygame.Color("blue")
        }
        for node in self.nodes.values():
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

    def draw_connections(self):
        for node in self.nodes.values():
            for neighbor in node.neighbors.values():
                start_px = self._to_screen(node.x, node.y)
                end_px = self._to_screen(neighbor.node.x, neighbor.node.y)
                pygame.draw.line(
                    self.screen, pygame.Color("black"), start_px, end_px, 2
                )

    def creat_drones(self):
        for _ in range(self.nb_drones):
            self.drones.append(
                DroneDisplay((self.start.x, self.start.y), self.drone_image)
            )


    def draw_drones(self):
        for drone in self.drones:
            center = self._to_screen(drone.x, drone.y)
            rect = drone.image.get_rect(center=center)
            self.screen.blit(drone.image, rect)

    def _to_screen(self, x, y):
        p_x = round(self.offset_x + x * self.scale)
        p_y = round(self.offset_y + y * self.scale)
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

    #     self.nodes = nodes
    #     pygame.init()
    #     info = pygame.display.Info()
    #     self.width = info.current_w / 2
    #     self.height = info.current_h / 2
    #     print(self.width, self.height)
    #     self.caption = "Fly_in"
    #     self.clock = pygame.time.Clock()
    #     self.running = True
    #     self.bg_image = pygame.image.load("./display/bg.webp")
    #     self.bg_image = pygame.transform.scale(self.bg_image, (self.width, self.height))
    #     self.font = pygame.font.Font(None, 22)
    #     self.zoom = 1.0
    #     self.cam_x = 0
    #     self.cam_y = 0
    #     self.dragging = False

    # def run(self):
    #     self.screen = pygame.display.set_mode((self.width, self.height))
    #     pygame.display.set_caption(self.caption)
    #     self.compute_scale()
    #     while self.running:
    #         self.get_event()
    #         self.draw()
    #         pygame.display.flip()
    #         self.clock.tick(60)
    #     pygame.quit()

    # def get_event(self):
    #     for event in pygame.event.get():
    #         if event.type == pygame.QUIT:
    #             self.running = False
    #         elif event.type == pygame.KEYDOWN:
    #             if event.key == pygame.K_ESCAPE:
    #                 self.running = False
    #             elif event.key == pygame.K_r:
    #                 self.zoom = 1.0
    #                 self.cam_x = 0
    #                 self.cam_y = 0
    #         elif event.type == pygame.MOUSEWHEEL:
    #             self.zoom_at(pygame.mouse.get_pos(), event.y)
    #         elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
    #             self.dragging = True
    #         elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
    #             self.dragging = False
    #         elif event.type == pygame.MOUSEMOTION and self.dragging:
    #             self.cam_x += event.rel[0]
    #             self.cam_y += event.rel[1]

    # def compute_scale(self):
    #     xs = [node.x for node in self.nodes.values()]
    #     ys = [node.y for node in self.nodes.values()]
    #     min_x = min(xs)
    #     min_y = min(ys)
    #     range_x = max(max(xs) - min_x, 1)
    #     range_y = max(max(ys) - min_y, 1)
    #     scale = min((self.width - 2 * 120) / range_x,
    #                 (self.height - 2 * 120) / range_y)
    #     offset_x = (self.width - range_x * scale) / 2
    #     offset_y = (self.height - range_y * scale) / 2
    #     self.pos = {}
    #     for node in self.nodes.values():
    #         pos_x = int(offset_x + (node.x - min_x) * scale)
    #         pos_y = int(self.height - offset_y - (node.y - min_y) * scale)
    #         self.pos[node.name] = (pos_x, pos_y)


    # def draw_nodes(self):
    #     radius = max(4, int(20 * self.zoom))
    #     for n in self.nodes.values():
    #         center = self.to_screen(n.name)
    #         pygame.draw.circle(self.screen, (0, 0, 0), center, radius)
    #         label = self.font.render(n.name, True, (0, 0, 0))
    #         x = center[0] - label.get_width() // 2
    #         y = center[1] + radius + 5
    #         self.screen.blit(label, (x, y))


    # def draw(self):
    #     self.screen.blit(self.bg_image, (0, 0))
    #     self.draw_nodes()

    # def to_screen(self, name):
    #     px, py = self.pos[name]
    #     return (int(px * self.zoom + self.cam_x),
    #             int(py * self.zoom + self.cam_y))

    # def zoom_at(self, mouse, direction):
    #     old = self.zoom
    #     self.zoom = max(0.3, min(5.0, self.zoom * (1.1 ** direction)))
    #     ratio = self.zoom / old
    #     self.cam_x = mouse[0] - (mouse[0] - self.cam_x) * ratio
    #     self.cam_y = mouse[1] - (mouse[1] - self.cam_y) * ratio