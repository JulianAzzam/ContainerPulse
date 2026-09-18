
from dataclasses import dataclass


@dataclass
class WorkloadEvent:
    workload_id: str
    timestamp: str
    event_type: str

