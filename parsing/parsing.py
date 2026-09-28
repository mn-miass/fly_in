from .file import File
from .data import Data, ValidData
import sys


class Parsing():
    def __init__(self):
        self.file_path = self._get_path()
        self.file: File = File(self.file_path)
        self.data = Data(self.file.data)
        self.nb_drones = self.data.valid_data.nb_drones
        self.start_hub = self.data.valid_data.start_hub
        self.end_hub = self.data.valid_data.end_hub
        self.hubs = self.data.valid_data.hubs
        self.connections = self.data.valid_data.connections

    def _get_path(self):
        if len(sys.argv) != 2: print("Number of argument should not be more then 2 <project_name> <file_path>"); exit()
        return sys.argv[1]