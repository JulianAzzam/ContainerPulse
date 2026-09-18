

from src.collectors.helper_funcs import write_anomaly
from src.config import event_queue
from src.events.AnomalyEvent import AnomalyEvent
import numpy as np

class AnomalyEvaluator:

    def __init__(self,workload_id):
        self.workload_id = workload_id
        self.consecutive_anomalies = 0
        self.metrics = {}
        self.anomaly_active = False
        self.current_anomalies = []

    def fit_baseline(self, training_samples, training_decisions, training_columns):
        self.training_features = training_samples
        self.training_decisions = training_decisions
        self.training_columns = training_columns
        matrix = np.array(training_samples)
        medians = np.round(np.median(matrix,axis=0),decimals=3)
        lower_range = np.round(np.percentile(matrix, 5, axis=0),decimals=3)
        upper_range = np.round(np.percentile(matrix, 95, axis=0),decimals=3)
        for ind, value in enumerate(training_columns):
            self.metrics[value] = {"median":medians[ind],
                                "p5": lower_range[ind],
                                "p95": upper_range[ind]}
        self.severe_reference = np.percentile(training_decisions, 1)

    def evaluate(self, feature_vector, decision):
        timestamp = feature_vector[0]
        features = feature_vector[1:]

        decision = float(decision)

        if decision < 0:
            self.consecutive_anomalies += 1

            self.current_anomalies.append({
                "timestamp": timestamp,
                "decision": decision,
                "features": features,
            })

        else:
            self.consecutive_anomalies = 0
            self.current_anomalies.clear()
            self.anomaly_active = False
            return
            
        if self.consecutive_anomalies >= 3 and not self.anomaly_active:
            worst_anomaly = min(
                self.current_anomalies,
                key=lambda anomaly: anomaly["decision"]
            )

            severity = self.calculate_severity(
                worst_anomaly["decision"]
            )

            if severity < 50:
                return

            unusual_features = {}

            for name, value in zip(
                self.training_columns,
                worst_anomaly["features"]
            ):
                bounds = self.metrics[name]

                if value < bounds["p5"] or value > bounds["p95"]:
                    unusual_features[name] = {
                        "value": float(value),
                        "median": bounds["median"],
                        "5th Percentile": bounds["p5"],
                        "95th Percentile": bounds["p95"],
                    }
            if len(unusual_features) == 0:
                return 
            self.anomaly_active = True
            write_anomaly(
                worst_anomaly["timestamp"],
                self.workload_id,
                severity,
                worst_anomaly["decision"],
                unusual_features,
            )
            # event_queue.put(
            #     AnomalyEvent(
            #         self.workload_id,
            #         worst_anomaly["timestamp"],
            #         severity,
            #         worst_anomaly["decision"],
            #         unusual_features,
            #     )
            # )

    def calculate_severity(self, decision):
        if decision >= 0:
            return 0.0

        severity = abs(decision) / abs(self.severe_reference) * 100
        return min(severity, 100.0)

    def evaluate_runtime_event(self, sample):
        event = sample["event"]

        if event == "oom":
            return self._create_runtime_event(
                sample,
                event_type="oom",
                severity=100,
                message="Container ran out of memory",
            )

        if event == "die":
            return self._create_runtime_event(
                sample,
                event_type="die",
                severity=60,
                message="Container stopped",
            )

        if event == "restart":
            return self._create_runtime_event(
                sample,
                event_type="restart",
                severity=80,
                message="Container restarted",
            )

        if event == "health_status: unhealthy":
            return self._create_runtime_event(
                sample,
                event_type="unhealthy",
                severity=80,
                message="Container became unhealthy",
            )

        return None



    def _create_runtime_event(
    self,
    sample,
    event_type,
    severity,
    message,):
        event = AnomalyEvent(
            workload_id=self.workload_id,
            timestamp=sample["timestamp"],
            severity=severity,
            decision=None,
            unusual_features={
                "runtime_event": {
                    "type": event_type,
                    "message": message,
                }
            },
        )

        event_queue.put(event)

        return event