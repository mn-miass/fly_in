class Drone():
    def __init__(self, start, name, color):
        self.current_zone = start
        self.name = name
        self.target_zone = None
        self.current_x = start.x
        self.current_y = start.y
        self.is_finished = False
        self.color = color

class Drones():
    def __init__(self, start, nb_drones):
        self.start = start
        self.nb_drones = nb_drones
        self.drones: list[Drone] = self._create_drones()

    def _create_drones(self):
        for i in range(self.nb_drones):
            drone = Drone(self.start, f'D{i+1}', "None")
            self.drones.append(drone)
