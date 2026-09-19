import datetime
import json
import re
import subprocess
import threading
import logging
from .models import WorkloadState
from ..workload.workload_state import _create_workload_state

from ..config import workloads

ANSI_ESCAPE = re.compile(
    r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])'
)

logger = logging.getLogger(__name__)

class DockerCollector:

    def __init__(self):
        self.collect()

    def collect(self):
        events_thread = threading.Thread(target=self.events_collector,daemon=True)
        stats_thread = threading.Thread(target=self.stats_collector,daemon=True)

        events_thread.start()
        stats_thread.start()
        logger.info("Threads started")
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
                event = json.loads(line)
                container_id = (
                    event.get("id")
                    or event.get("Actor", {}).get("ID")
                )
                if not container_id:
                    logger.warning("Docker event missing container ID: %s", event)
                    continue
                container_name = (
                    event.get("Actor", {})
                    .get("Attributes", {})
                    .get("name")
                )
                event_type = event.get("status")

                if not container_name:
                    logger.warning("Docker event missing container name: %s", event)
                    continue

                workload_id = self._make_workload_id(container_name, container_id)
                timestamp = datetime.datetime.now().isoformat(timespec="milliseconds")
                state: WorkloadState = workloads.get(workload_id)

                if state is None:
                    _create_workload_state(workload_id)
                    state = workloads.get(workload_id)

                sample = {
                    "workload_id": workload_id,
                    "event": event_type,
                    "timestamp": timestamp,
                }

                state.receive_sample(sample)

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
                
                workload_id = self._make_workload_id(stats["Name"], stats["ID"])
                sample = {  "workload_id": workload_id,
                            "timestamp": timestamp,
                            "cpu_usage": stats["CPUPerc"],
                            "mem_usage": stats["MemUsage"],
                            "network_tx": network_tx,
                            "network_rx": network_rx,
                            "PID_count": stats["PIDs"]}
                state : WorkloadState = workloads.get(workload_id)
                if state is None:
                    _create_workload_state(workload_id)
                    state = workloads.get(workload_id)
                
                state.receive_sample(sample)
        except KeyboardInterrupt:
            stats_process.terminate()

    @staticmethod
    def _make_workload_id(name, container_id) -> str:
        """
        Build the canonical workload ID used by both Docker stats and events.

        Docker event IDs may be full-length, so the container ID is normalized
        to the 12-character short form returned by `docker stats`.
        """
        return f"{name}-{container_id[:12]}"
