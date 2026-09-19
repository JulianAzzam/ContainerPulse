# ContainerPulse

[![Tests](https://github.com/JulianAzzam/ContainerPulse/actions/workflows/tests.yml/badge.svg)](https://github.com/JulianAzzam/ContainerPulse/actions/workflows/tests.yml)

Lightweight container workload anomaly detection for Docker environments.

ContainerPulse monitors Docker container metrics and runtime events, learns a baseline for each workload, and surfaces abnormal behavior using a combination of machine learning and deterministic resource checks.

## Features

- Per-container anomaly detection
- Isolation Forest based workload modeling
- Warm-up and learning phases before monitoring begins
- Sustained memory anomaly detection through a deterministic ResourceGuard
- Docker runtime event handling
- Webhook notifications
- CLI-based operation
- No application-code changes required
- Unit and Docker integration test support

## How It Works

For each Docker workload, ContainerPulse:

1. Observes the workload during a warm-up period
2. Collects training samples
3. Fits an Isolation Forest model
4. Monitors incoming runtime metrics
5. Applies persistence and severity filtering
6. Applies deterministic resource guards
7. Handles runtime events separately from the ML model
8. Emits anomaly events through the notification pipeline

## Detection Architecture

```text
Docker
  |
  +-- stats
  |     |
  |     v
  |  WorkloadState
  |     +-- IsolationForest
  |     +-- ResourceGuard
  |
  +-- events
        |
        v
   AnomalyEvaluator
        |
        v
    AnomalyEvent
        |
        v
      Notifier
        |
        v
     Webhooks
```

## Installation

> Package publication is still in progress. Until PyPI publication, install from the repository.

```bash
pip install -e .
```

For development dependencies:

```bash
pip install -e ".[dev]"
```

## Quick Start

Start ContainerPulse:

```bash
containerpulse start
```

Enable verbose logging:

```bash
containerpulse start --verbose
```

## Webhook Management

Add a webhook:

```bash
containerpulse webhooks add NAME URL
```

List configured webhooks:

```bash
containerpulse webhooks list
```

Update a webhook:

```bash
containerpulse webhooks update NAME URL
```

Remove a webhook:

```bash
containerpulse webhooks remove NAME
```

## Detection Model

### Isolation Forest

ContainerPulse currently models:

- CPU usage
- Memory usage
- Positive memory growth

The model is trained independently for each workload after the warm-up period.

Raw model predictions are not treated as incidents immediately. ContainerPulse applies persistence and severity logic before emitting an anomaly event.

### ResourceGuard

Some abnormal states are better detected deterministically than through the ML model.

The current ResourceGuard detects sustained memory usage significantly above the learned normal baseline.

### Runtime Events

Docker runtime events can be evaluated directly without passing through the ML model.

Examples include:

- OOM events
- Container death
- Unhealthy container state
- Other deterministic runtime failures supported by the evaluator

## Testing

Run unit tests:

```bash
pytest tests/unit
```

Run all tests:

```bash
pytest
```

Run only Docker integration tests:

```bash
pytest -m integration
```

Docker integration tests require access to a running Docker daemon and should skip cleanly when Docker is unavailable.

## Development

Recommended setup:

```bash
python -m venv .venv
```

Activate the environment, then install the package in editable mode:

```bash
pip install -e ".[dev]"
```

Run tests before committing:

```bash
pytest
```

## Security Considerations

ContainerPulse may require access to the Docker daemon or Docker socket.

Access to `/var/run/docker.sock` is highly privileged and can effectively grant root-level control over the host. Only run ContainerPulse in environments where that level of access is acceptable.

Webhook URLs should be treated as secrets and should not be committed to source control.

## Current Limitations

- Docker-only in the current V1
- Models are trained independently for each workload after startup
- Models are not persisted across process restarts
- No automatic concept-drift retraining yet
- HTTP-level telemetry is not currently supported
- Bursty workloads can still produce isolated raw model outliers, although incident filtering reduces false alerts
- Kubernetes support is not yet implemented

## Roadmap

Planned future work includes:

- Kubernetes collector
- Kubernetes DaemonSet deployment
- HTTP telemetry from existing reverse proxies or ingress layers
- Model persistence
- Safe retraining and concept-drift handling
- Additional deterministic resource guards
- Additional notification channels
- Optional application SDKs for richer contextual events

## License

ContainerPulse is licensed under the MIT License. See [LICENSE](LICENSE).
