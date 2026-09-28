class Hub():
    def __init__(self, name, x, y, color, max_drones, zone):
        self.name = name
        self.x = x
        self.y = y
        self.color = color
        self.max_drones = max_drones
        self.zone = zone

class Connection():
    def __init__(self, hub_a: Hub, hub_b: Hub, max_link_capacity):
        self.hub_a = hub_a
        self.hub_b = hub_b
        self.max_link_capacity = max_link_capacity


class Line():
    def __init__(self, number, line, key, value):
        self.number = number
        self.line = line
        self.key = key
        self.value = value

class ValidData():
    def __init__(self):
        self.nb_drones = None
        self.start_hub: Hub = None
        self.end_hub: Hub = None
        self.hubs: Hub = []
        self.connections: Connection[Hub] = []

class Data():
    def __init__(self, data: list[str]):
        self.data = data
        self.lines: list[Line] = []
        self.valid_data = ValidData()
        self.names = []
        self.coordinates = []
        self.hub_names = {}
        self.coordinates_names = []
        self._get_valid_lines()
        self._check_no_data()
        self._get_nb_drones()
        self._validate_rest_of_data()

    def _get_valid_lines(self):
        for num, data in enumerate(self.data):
            data = data.split("#")[0].strip()
            num += 1
            if data:
                if ":" not in data: print(f"line {num} is missing ':' invalid_line: {data}"); exit()
                try:
                    key, value = data.split(":")
                except ValueError :
                    print(f"line {num} have more then one ':' invalid_line: {data}"); exit()
                self.lines.append(Line(num, data, key.strip(), value.strip()))

    def _check_no_data(self):
        if not len(self.lines): print(f"The file have no data"); exit()

    def _get_nb_drones(self):
        first_line = self.lines[0]
        if first_line.key != "nb_drones": print(f"line 1 nb_drones should have number as value found {first_line.key}"); exit()
        if not first_line.value: print("line 1 no nb_drones was provided"); exit()
        self.valid_data.nb_drones = self._validate_integer(first_line.value, first_line.number, is_nb_drones=True)

    #be carfull it should be line value 
    def _validate_rest_of_data(self):
        for line in self.lines[1:]:
            if line.key == "hub": self._validate_hub(line)
            elif line.key == "start_hub": self._validate_hub(line, is_start=True)
            elif line.key == "end_hub": self._validate_hub(line, is_end=True)
            elif line.key == "connection": self._validate_connection(line)
            else: print(f"line {line} in valid key should be one of the folowing [<hub> <start_hub> <end_hub> <nb_drones> <connection>]"); exit()

    def _validate_integer(self, number, line, is_nb_drones=False, is_start=False, is_end=False, is_coordinates=False, is_max_drones=False, is_max_link_capacity=False):
        if "_" in number: print(f"line {line} invalid number cant have _"); exit()
        try:
            num = int(number)
            if num <= 0 and is_nb_drones: print(f"nb_drones must be a positive integer"); exit()
            if num <= 0 and is_max_drones and not is_start and not is_end: print(f"hub max drones must be a postive integer"); exit()
            if num <= 0 and is_max_link_capacity: print(f"line {line} max_link_capacity must be a positive integer {num} is invalid"); exit()
            if (is_start or is_end) and is_max_drones: return self.valid_data.nb_drones
            return num
        except ValueError:
            if (is_start or is_end) and is_max_drones: return self.valid_data.nb_drones
            if is_coordinates: print(f"line {line} coordinates  must be a valid integer"); exit()
            if is_max_drones: print(f"line {line} max_drones must be positive integere"); exit()
            if is_nb_drones: print(f"line {line} nb_drones must be valid integer"); exit()
            exit()

    def _validate_hub(self, line, is_start=False, is_end=False):
        value = line.value.split()
        if len(value) < 3: print(f"line {line.number} hub must at least have 3 values <name> <x> <y>"); exit()
        name = self._validate_name(value[0], line.number)
        x = self._validate_integer(value[1], line.number, is_coordinates=True)
        y = self._validate_integer(value[2], line.number, is_coordinates=True)
        self._validate_coordinates(line.number, x, y)
        if len(value) >= 3: metadata = self._validate_metadata(value[3:], line.number, is_start, is_end)
        else: metadata = self._validate_metadata()
        hub = Hub(name, x, y, metadata["color"], metadata["max_drones"], metadata["zone"])
        if is_start:
            if self.valid_data.start_hub: print(f"line {line.number} duplicated start hub"); exit()
            self.valid_data.start_hub = hub
        elif is_end:
            if self.valid_data.end_hub: print(f"line {line.number} duplicated end hub"); exit()
            self.valid_data.end_hub = hub
        else:    
            self.valid_data.hubs.append(hub)
        self.hub_names[name]  = hub

    def _validate_name(self, name, line):
        if name in self.names: print(f"line {line} duplicated name {name}"); exit()
        if "-" in name: print(f"line {line} name {name} cant include '-'"); exit()
        self.names.append(name)
        return name

    def _validate_coordinates(self, line, x, y):
        if (x, y) in self.coordinates: print(f"line {line} cordinates are duplicated"); exit()
    
    def _validate_metadata(self, value=None, line_num=None, is_start=False, is_end=False):
        metadata = {"color": None, "max_drones": 1, "zone": "normal"}
        readed = []
        zone_list = ["normal", "blocked", "restricted", "priority"]
        if not value: return metadata
        value = " ".join(value)
        if not value[0] == "[" or not value[-1] == "]": print(f"line {line_num} metadata must be as the folowing form [metadata] this {value} is wrong"); exit()
        value = value[1:-1].strip()
        if not value: return metadata
        values = value.split()
        for value in values:
            if "=" not in value: print(f"line {line_num}"); exit()
            if len(value.split("=")) != 2: print(f"line {line_num} each metadata must be key=value this {value} invalid"); exit()
            key, value = value.split("=")
            key = key.strip(); value = value.strip()
            if key not in metadata.keys(): print(f"line {line_num} invalid metadata {key}"); exit()
            if key in readed: print(f"line {line_num} duplicated metadata {key}"); exit()
            if key == "max_drones": metadata["max_drones"] = self._validate_integer(value, line_num, is_start, is_end, is_max_drones=True); readed.append("max_drones")
            if key == "color": metadata["color"] = value; readed.append("color")
            if key == "zone":
                if value not in zone_list: print(f"line {line_num} metadata must be in {zone_list}"); exit()
                else: metadata["zone"] = value
        return metadata

    def _validate_connection(self, line):
        values = line.value.split()
        if len(values) > 2: print(f"line {line.number} wrong format it must be <hub1>-<hub2> [metadata]"); exit()
        if "-" not in values[0]: print(f"line {line.number} connection must have the '-'"); exit()
        hub_name_a, hub_name_b = values[0].split("-")
        hub_a = self.hub_names.get(hub_name_a, None); hub_b = self.hub_names.get(hub_name_b, None)
        if not hub_a: print(f"line {line.number} no hub with this name {hub_name_a}"); exit()
        if not hub_b: print(f"line {line.number} no hub with this name {hub_name_b}"); exit()
        if hub_a == hub_b: print(f"line {line.number} hubs are the same"); exit()
        if (hub_a.name, hub_b.name) in self.coordinates_names or (hub_b.name, hub_a.name) in self.coordinates_names:
            print(f"line {line.number} duplicate coonection"); exit()
        if len(values) == 2: metadata = self._metadata_connection(values[1])
        else: metadata = self._metadata_connection()
        connection = Connection(hub_a, hub_b, metadata["max_link_capacity"]); self.coordinates_names.append((hub_name_a, hub_name_b))
        self.valid_data.connections.append(connection)

    def _metadata_connection(self, value=None, line=None):
        metadata = {"max_link_capacity": 1}
        if not value: return metadata
        value = value.strip()
        if value[0] != "[": print(f"line {line} metadata must start with '['"); exit()
        if value[-1] != "]": print(f"line {line} metadata must end with ']'"); exit()
        value = value[1:-1]
        if "=" not in value: print(f"line {line} metadata must be key=value = is missing")
        key, value = value.split("="); key = key.strip(); value = value.strip()
        if key != "max_link_capacity": print(f"line {line} metadata for connection must be max_link_capacity {key} is invalid"); exit()
        value = self._validate_integer(value, line, is_max_link_capacity=True)
        metadata["max_link_capacity"] = value
        return metadata
