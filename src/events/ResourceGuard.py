

import numpy as np


class ResourceGuard:
    def __init__(self,workload_id):
        self.workload_id = workload_id
        self.memory_p99 = None
        self.above_threshhold_timer = 0

    def fit(self, training_samples, columns):
        memory_index = columns.index("Memory")
        memory = training_samples[:, memory_index]

        self.memory_p99 = np.percentile(memory, 99)

        memory_p25 = np.percentile(memory, 25)
        memory_p75 = np.percentile(memory, 75)

        iqr = memory_p75 - memory_p25

        self.memory_threshold = self.memory_p99 + (3 * iqr)

    def evaluate(self, sample, columns):
        memory_index = columns.index("Memory")
        memory = sample[memory_index]
        if memory > self.memory_threshold:
            self.consecutive_memory_violations += 1
        else:
            self.consecutive_memory_violations = 0
            self.memory_incident_active = False
            return None

        if (
            self.consecutive_memory_violations >= 5
            and not self.memory_incident_active
        ):
            self.memory_incident_active = True

            return {
                "type": "sustained_memory_anomaly",
                "memory": float(memory),
                "threshold": float(self.memory_threshold),
                "ratio": float(memory / self.memory_threshold),
                "consecutive_samples": self.consecutive_memory_violations,
            }

        return None