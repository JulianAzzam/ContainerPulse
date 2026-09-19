import json
from pathlib import Path
from queue import Queue
import os

PROJECT_ROOT = Path(__file__).resolve().parent
SETTINGS_PATH = PROJECT_ROOT / "settings.json"
workloads = dict()
webhook_manager = None
with SETTINGS_PATH.open("a+") as file:
    settings = {}
    if not os.path.getsize(SETTINGS_PATH) == 0:
        file.seek(0)
        settings = json.load(file)
event_queue :Queue = Queue()
