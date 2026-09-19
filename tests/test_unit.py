import json
from queue import Empty
from types import SimpleNamespace

import numpy as np
import pytest

from containerpulse.collectors.docker_collector import DockerCollector
from containerpulse.collectors.helper_funcs import parse_data_size
from containerpulse.collectors.models import WorkloadState
from containerpulse.config import event_queue
from containerpulse import config
from containerpulse.events.anomaly_evaluator import AnomalyEvaluator
from containerpulse.events.resource_guard import ResourceGuard
from containerpulse.workload.workload_status import WorkloadStatus


@pytest.fixture(autouse=True)
def event_settings(monkeypatch):
    monkeypatch.setitem(config.settings, "infra", "test")


@pytest.mark.parametrize("text,expected", [
    ("1 B", 1), ("1.5 kB", 1500), ("2 MB", 2_000_000),
    ("1 MiB", 1048576), ("2.5 GiB", 2.5 * 1024**3),
    ("1e3 B", 1000),
])
def test_parse_data_size(text, expected):
    assert parse_data_size(text) == expected


@pytest.mark.parametrize("text", ["", "12", "-1 MB", "1 TB", "1 mb", "abc MiB"])
def test_parse_data_size_rejects_invalid_values(text):
    with pytest.raises(ValueError):
        parse_data_size(text)


def test_resource_guard_persistence_and_rearm():
    guard = ResourceGuard("demo")
    guard.fit(np.array([[1, 100], [2, 100], [3, 100]]), ["CPU", "Memory"])
    assert guard.memory_threshold == 100
    assert all(guard.evaluate([0, 101], ["CPU", "Memory"]) is None for _ in range(4))
    event = guard.evaluate([0, 101], ["CPU", "Memory"])
    assert event["type"] == "sustained_memory_anomaly"
    assert event["consecutive_samples"] == 5
    assert guard.evaluate([0, 101], ["CPU", "Memory"]) is None
    assert guard.evaluate([0, 100], ["CPU", "Memory"]) is None
    assert all(guard.evaluate([0, 102], ["CPU", "Memory"]) is None for _ in range(4))
    assert guard.evaluate([0, 102], ["CPU", "Memory"])["memory"] == 102


def test_evaluator_emits_only_persistent_high_feature():
    while not event_queue.empty():
        event_queue.get_nowait()
    evaluator = AnomalyEvaluator("demo")
    evaluator.fit_baseline(np.array([[10, 100], [20, 200]]), np.array([-0.1, 0.1]), ["CPU", "Memory"])
    for index in range(3):
        evaluator.evaluate([str(index), 30, 50], -0.2)
    event = event_queue.get_nowait()
    assert "demo" in event.message
    assert "**CPU**" in event.message and "**Memory**" not in event.message
    evaluator.evaluate(["later", 31, 40], -0.2)
    with pytest.raises(Empty):
        event_queue.get_nowait()
    evaluator.evaluate(["normal", 10, 100], 0.1)
    assert evaluator.consecutive_anomalies == 0


def test_evaluator_ignores_low_only():
    while not event_queue.empty():
        event_queue.get_nowait()
    evaluator = AnomalyEvaluator("demo")
    evaluator.fit_baseline(np.array([[10, 100], [20, 200]]), np.array([-0.1, 0.1]), ["CPU", "Memory"])
    for index in range(3):
        evaluator.evaluate([str(index), 1, 1], -0.2)
    with pytest.raises(Empty):
        event_queue.get_nowait()


def test_workload_preprocessing_and_transition(monkeypatch):
    state = WorkloadState("demo", warm_up_seconds=0)
    state.memory_growth_threshold = 10
    original = [4, 100, 9]
    assert state.preprocess_features(original) == [4, 100, 0]
    assert original == [4, 100, 9]
    assert state.preprocess_features([4, 100, 10]) == [4, 100, 10]
    sample = {"timestamp": "now", "cpu_usage": "10%", "mem_usage": "1 MiB / 2 MiB",
              "network_rx": "1 kB", "network_tx": "2 kB", "PID_count": "3"}
    state.receive_sample(sample)
    assert state.status == WorkloadStatus.LEARNING
    assert len(state.training_samples) == 1
    state.receive_sample(sample)
    assert len(state.training_samples) == 1
    changed = dict(sample, mem_usage="2 MiB / 2 MiB")
    state.receive_sample(changed)
    assert state.training_samples[-1][2] == 1024**2


def test_docker_workload_id_and_stats_parsing(monkeypatch):
    import containerpulse.collectors.docker_collector as module
    full_id = "a" * 64
    assert DockerCollector._make_workload_id("demo", full_id) == "demo-" + "a" * 12
    assert DockerCollector._make_workload_id("demo", full_id[:12]) == "demo-" + "a" * 12
    received = []
    monkeypatch.setattr(module, "workloads", {"demo-" + "a" * 12: SimpleNamespace(receive_sample=received.append)})
    line = json.dumps({"Name": "demo", "ID": full_id[:12], "NetIO": "1 kB / 2 kB",
                       "CPUPerc": "1%", "MemUsage": "1 MiB / 2 MiB", "PIDs": "2"})
    monkeypatch.setattr(module.subprocess, "Popen", lambda *a, **k: SimpleNamespace(stdout=[line]))
    DockerCollector.__new__(DockerCollector).stats_collector()
    assert received[0]["workload_id"] == "demo-" + "a" * 12
    assert received[0]["network_rx"] == "1 kB"
    assert received[0]["network_tx"] == "2 kB"


def test_docker_event_parsing_uses_same_id(monkeypatch):
    import containerpulse.collectors.docker_collector as module
    full_id = "b" * 64
    received = []
    monkeypatch.setattr(module, "workloads", {"demo-" + "b" * 12: SimpleNamespace(receive_sample=received.append)})
    line = json.dumps({"id": full_id, "status": "oom", "Actor": {"Attributes": {"name": "demo"}}})
    monkeypatch.setattr(module.subprocess, "Popen", lambda *a, **k: SimpleNamespace(stdout=[line]))
    DockerCollector.__new__(DockerCollector).events_collector()
    assert received[0]["workload_id"] == "demo-" + "b" * 12
    assert received[0]["event"] == "oom"
