"""Run with a reachable Docker daemon and a locally cached Alpine image."""

import json
import shutil
import subprocess
import uuid

import pytest

from containerpulse.collectors.docker_collector import DockerCollector
from containerpulse.collectors.helper_funcs import parse_data_size


@pytest.mark.docker
def test_live_docker_container_stats():
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is unavailable")
    daemon = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"],
                            capture_output=True, text=True, timeout=10)
    if daemon.returncode:
        pytest.skip("Docker daemon is unavailable")
    image = "alpine:3.20"
    cached = subprocess.run(["docker", "image", "inspect", image],
                            capture_output=True, timeout=10)
    if cached.returncode:
        pytest.skip(f"{image} is not cached locally")

    name = "containerpulse-test-" + uuid.uuid4().hex[:10]
    container_id = None
    try:
        started = subprocess.run(["docker", "run", "--rm", "-d", "--name", name,
                                  image, "sleep", "60"], capture_output=True,
                                 text=True, timeout=20, check=True)
        container_id = started.stdout.strip()
        stats = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{ json . }}", name],
                               capture_output=True, text=True, timeout=20, check=True)
        row = json.loads(stats.stdout.strip().splitlines()[0])
        assert row["Name"] == name
        assert DockerCollector._make_workload_id(row["Name"], row["ID"]) == \
            DockerCollector._make_workload_id(name, container_id)
        assert parse_data_size(row["MemUsage"].split("/")[0].strip()) >= 0
        assert all(parse_data_size(part.strip()) >= 0 for part in row["NetIO"].split("/"))
    finally:
        if container_id:
            subprocess.run(["docker", "rm", "-f", container_id],
                           capture_output=True, timeout=10, check=False)
