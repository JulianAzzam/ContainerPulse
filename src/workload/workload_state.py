from src.config import workloads
from src.collectors.models import WorkloadState


def create_workload_state(workload_id: str):
    global workloads
    workload = workloads.get(workload_id)
    if not workload:
        workload = WorkloadState(workload_id)
        workloads[workload_id] = workload
    return workload