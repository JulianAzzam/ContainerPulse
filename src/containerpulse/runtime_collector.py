import json
from .config import SETTINGS_PATH, settings
from .collectors.docker_collector import DockerCollector

class RuntimeCollector:

    instance = None
    _engines = {"docker": DockerCollector, "kubernetes":None}
    def __init__(self, kwargs):
        try:
            if "engine" in kwargs:
                engine = kwargs["engine"]
                self.update_infra(engine)
                self._engines[engine]()
            else:
                self.update_infra("docker")
                self._engines["docker"]()
        except KeyboardInterrupt:
            exit()
    
    def update_infra(self, engine):
        settings["infra"] = engine
        with open(SETTINGS_PATH, "w") as file:
                json.dump(settings, file)
        

