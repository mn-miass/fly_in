class File():
    def __init__(self, name):
        self.name = name
        self.data = None
        self._validate_file()

    def _validate_file(self):
        try:
            with open(self.name, "r") as file:
                self.data = file.readlines()
        except Exception as e:
            print(e)
            exit()
    