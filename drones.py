class Drone():
    def __init__(self, start, color):
        self.current_zone = start
        self.target_zone = None
        self.current_x = start.x
        self.current_y = start.y
        self.path = [()]
        self.fis_finished = False


class Drones():
    def __init__(self, start, nb_drones):
        self.start = start
        self.nb_drones = nb_drones
        self.drones: list[Drone] = self._create_drones()

    def _create_drones(self):
        for i in range(self.nb_drones):
            drone = Drone(self.start, "None")
            self.drones.append(drone)