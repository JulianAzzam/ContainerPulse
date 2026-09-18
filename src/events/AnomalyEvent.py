from src.config import settings

class AnomalyEvent:

    def __init__(self, workload_id, timestamp, severity,decision, metrics):
        self.infra = settings["infra"]
        self.title = "Anomaly Detected"
        metric_lines = [
            self.format_metric(name, metric)
            for name, metric in metrics.items()
        ]
        print(metric_lines)
        self.message = (
        f"**Workload:** `{workload_id}`\n"
        f"**Time:** {timestamp}\n"
        f"**Severity:** {severity:.1f}%\n"
        f"**Decision score:** {decision:.4f}\n\n"
        f"**Unusual Metrics**\n"
        + "\n".join(metric_lines)
    )


    def format_metric(self,name, metric):
        value = float(metric["value"])
        median = float(metric["median"])
        p5 = float(metric["5th Percentile"])
        p95 = float(metric["95th Percentile"])
        if name in {"Memory"}:
            value /= 1024 ** 2
            median /= 1024 ** 2
            p5 /= 1024 ** 2
            p95 /= 1024 ** 2
            unit = " MiB"
        elif name in {"memory_rate","receive_rate", "transmit_rate"}:
            value /= 1024
            median /= 1024
            p5 /= 1024
            p95 /= 1024
            unit = " KiB/s"
        elif name == "CPU":
            unit = "%"
        else:
            unit = ""
        return (
            f"**{name}**\n"
            f"  Current: `{value:.2f}{unit}`\n"
            f"  Normal: `{p5:.2f} – {p95:.2f}{unit}`\n"
            f"  Median: `{median:.2f}{unit}`"
        )

    def __str__(self):
        return f"{self.title}\n{self.message}"
        
    
