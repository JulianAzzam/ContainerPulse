import datetime
import json
import re
import subprocess
import threading
import time
from src.collectors.models import WorkloadState
from src.workload.workload_state import create_workload_state

from src.config import workloads

ANSI_ESCAPE = re.compile(
    r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])'
)

class DockerCollector:
    def __init__(self):
        self.collect()

    def collect(self):
        events_thread = threading.Thread(target=self.events_collector,daemon=True)
        stats_thread = threading.Thread(target=self.stats_collector,daemon=True)

        events_thread.start()
        stats_thread.start()
        print("Threads started")
        events_thread.join()
        stats_thread.join()

    def events_collector(self):
        global workloads
        events_process = subprocess.Popen(
            ["docker", "events", "--filter", "type=container", "--filter", "event=die", "--filter", "event=create", "--filter", "event=oom", "--filter", "event=health_status", "--format", "{{ json . }}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        try:
            for line in events_process.stdout:
                if not line:
                    continue
                if "container create" in line:
                    # TODO: Extract workload_id
                    workload_id = None
                    timestamp = datetime.datetime.now().isoformat(timespec="milliseconds")
                    state :WorkloadState = workloads.get(workload_id)
                    if state is None:
                        create_workload_state(workload_id)
                    sample = {"workload_id": workload_id,
                              "event": "event",
                              "timestamp": timestamp
                              }
                    state.receive_sample(sample)
                print("Anomaly:", line)
        except KeyboardInterrupt:
            events_process.terminate()

    def stats_collector(self):
        global workloads
        stats_process = subprocess.Popen(
            ["docker", "stats", "--format", "{{ json . }}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        try:
            for line in stats_process.stdout:
                line = ANSI_ESCAPE.sub("", line).strip()
                if not line:
                    continue
                stats = json.loads(line)
                network_split = stats["NetIO"].split("/")
                network_rx = network_split[0].strip()
                network_tx = network_split[1].strip()
                timestamp = datetime.datetime.now().isoformat(timespec="milliseconds")
                workload_id = f'{stats["Name"]}-{stats['ID']}'
                sample = {  "workload_id": workload_id,
                            "timestamp": timestamp,
                            "cpu_usage": stats["CPUPerc"],
                            "mem_usage": stats["MemUsage"],
                            "network_tx": network_tx,
                            "network_rx": network_rx,
                            "PID_count": stats["PIDs"]}
                state : WorkloadState = workloads.get(workload_id)
                if state is None:
                    create_workload_state(workload_id)
                    state = workloads.get(workload_id)
                
                state.receive_sample(sample)
        except KeyboardInterrupt:
            stats_process.terminate()