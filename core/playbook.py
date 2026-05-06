import json
from config.settings import DEPENDENCIES_PATH

class Playbook:

    def __init__(self):
        with open(DEPENDENCIES_PATH) as f:
            self.data = json.load(f)

    def suggest(self, milestone):
        return self.data.get(milestone, [])