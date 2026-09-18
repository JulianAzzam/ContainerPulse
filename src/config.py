import json
from pathlib import Path
from queue import Queue


PROJECT_ROOT = Path(__file__).resolve().parent
SETTINGS_PATH = PROJECT_ROOT / "settings.json"
workloads = dict()
webhook_manager = None
with SETTINGS_PATH.open("r") as file:
    settings = json.load(file)
event_queue :Queue = Queue()