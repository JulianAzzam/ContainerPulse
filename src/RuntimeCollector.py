


import csv
import json
from src.config import SETTINGS_PATH, settings
from src.collectors import DockerCollector
from src.config import workloads
from src.collectors.models import WorkloadState

class RuntimeCollector:

    instance = None
    _engines = {"docker": DockerCollector, "kubernetes":None}
    def __init__(self, kwargs):
        try:
            if "engine" in kwargs:
                engine = kwargs["engine"]
                self.update_infra(engine)
                collector = self._engines[engine]()
            else:
                self.update_infra("docker")
                collector = self._engines["docker"]()
        except KeyboardInterrupt:
            with open('docker_data.csv', mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([ "timestamp", "status", "cpu", "memory", "memory_rate", "score", "decision", "predict",])
                for key in workloads:
                    model: WorkloadState = workloads.get(key)
                    writer.writerows(model.predict_outputs)
            exit()
    def update_infra(self, engine):
        settings["infra"] = engine
        with open(SETTINGS_PATH, "w") as file:
                json.dump(settings, file)
        

