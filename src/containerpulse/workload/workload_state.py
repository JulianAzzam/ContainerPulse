from ..config import workloads
from ..collectors.models import WorkloadState


def _create_workload_state(workload_id: str):
    """
    Creates a WorkloadState to begin collecting information on newly detected
    workloads.
    """
    global workloads
    workload = workloads.get(workload_id)
    if not workload:
        workload = WorkloadState(workload_id)
        workloads[workload_id] = workload
    return workload
