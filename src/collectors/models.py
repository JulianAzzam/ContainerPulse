import time

import numpy as np
from sklearn.ensemble import IsolationForest
from src.collectors.helper_funcs import parse_data_size
from src.events.AnomalyEvaluator import AnomalyEvaluator
from src.events.AnomalyEvent import AnomalyEvent
from src.events.ResourceGuard import ResourceGuard
from src.workload.WorkloadStatus import WorkloadStatus

class WorkloadState:
    # Use the shared status when available; older WorkloadStatus definitions
    # can still represent this pre-learning phase locally.
    WARMING_UP = getattr(WorkloadStatus, "WARMING_UP", "WARMING_UP")
    WARM_UP_SAMPLES = 120
    row_data_keys = ("Memory", "network_rx", "network_tx", "pid_count",)
    training_feature_names = (
        "CPU",
        "Memory",
        "memory_rate",
        # "receive_rate",
        # "transmit_rate",
        # "pid_count",
        # "pid_rate",
    )
    in_mb = 1024 ** 2
    in_kb = 1024
    def __init__(self, workload_id, warm_up_samples=WARM_UP_SAMPLES):
        self.model = IsolationForest(
            max_samples=0.9, contamination=0.05, random_state=42
        )
        self.workload_id = workload_id
        self.training_samples = []
        if warm_up_samples < 0:
            raise ValueError("warm_up_samples must be non-negative")
        self.warm_up_samples = warm_up_samples
        self.warm_up_count = 0
        self.status = self.WARMING_UP if warm_up_samples else WorkloadStatus.LEARNING
        self.waiting_queue = []
        self.last_signature = None
        self.predict_outputs = []
        self.previous_raw_sample = {}
        self.consecutive_anomalies = 0
        self.evaluator = AnomalyEvaluator(workload_id)
        self.resource_guard = ResourceGuard(workload_id)
        self.warmup_started_at = time.monotonic()

    def receive_sample(self, sample: dict):
        if "event" in sample:
            self.evaluator.evaluate_runtime_event(sample)
            return

        data = self.extract_features(sample)

        signature = (
            data["CPU"],
            data["Memory"],
            data["network_rx"],
            data["network_tx"],
            data["pid_count"],
        )
        if signature == self.last_signature:
            return
        self.last_signature = signature
        self.previous_raw_sample = {
            key: data[key] for key in self.row_data_keys if key in data
        }
        training_sample = [data[key] for key in self.training_feature_names]
        if self.status == self.WARMING_UP:
            self.predict_outputs.append(
                self._unscored_row(sample["timestamp"], "WARMING_UP", training_sample)
            )
            self.warm_up_count += 1
            if time.monotonic() - self.warmup_started_at >= 120:
                self.status = WorkloadStatus.LEARNING
                print("Warm-up complete; learning started")
        elif self.status == WorkloadStatus.LEARNING:
            self.training_samples.append(training_sample)
            self.predict_outputs.append(
                self._unscored_row(sample["timestamp"], "LEARNING", training_sample)
            )
            if len(self.training_samples) == 300:
                self.status = WorkloadStatus.TRAINING
                print("Training started")
                self.fit()
                self.status = WorkloadStatus.READY
                print("Training Complete")
                print("Training samples:", len(self.training_samples))
                print("Training features:", self.training_feature_names)
                print("Memory growth threshold:", self.memory_growth_threshold)
                print("Severe reference:", self.evaluator.severe_reference)
        elif self.status == WorkloadStatus.TRAINING:
            self.waiting_queue.append(
                (sample["timestamp"], training_sample)
            )
            self.predict_outputs.append(
                self._unscored_row(sample["timestamp"], "TRAINING", training_sample)
            )
        elif self.status == WorkloadStatus.READY:

            while len(self.waiting_queue) != 0:
                timestamp, waiting = self.waiting_queue.pop(0)

                result, decision, score, processed_sample = self.predict(
                    waiting
                )

                # Evaluator receives model units / model features
                self.evaluator.evaluate(
                    [timestamp, *processed_sample],
                    decision
                )
                self.resource_guard.evaluate(processed_sample, self.training_feature_names)
                # CSV/debug output is converted separately
                self.predict_outputs.append(
                    self._scored_row(timestamp, waiting, processed_sample,
                                     score, decision, result)
                )

            result, decision, score, processed_sample = self.predict(
                training_sample
            )

            self.evaluator.evaluate(
                [sample["timestamp"], *processed_sample],
                decision
            )
            resource_event = self.resource_guard.evaluate(processed_sample, self.training_feature_names)
            if resource_event is not None:
                print(resource_event)
            self.predict_outputs.append(
                self._scored_row(sample["timestamp"], training_sample,
                                 processed_sample, score, decision, result)
            )

    def _unscored_row(self, timestamp, status, raw_sample):
        # Column 4 is the model-used memory_rate; it is filled after fit,
        # when the learned growth threshold becomes available.
        return [timestamp, status, raw_sample[0],
                round(raw_sample[1] / self.in_mb, 3), None,
                None, None, None,
                raw_sample[2] / self.in_kb]

    def _scored_row(self, timestamp, raw_sample, processed_sample,
                    score, decision, result):
        return [timestamp, "READY", processed_sample[0],
                round(processed_sample[1] / self.in_mb, 3),
                round(processed_sample[2] / self.in_kb, 3),
                round(score, 4), round(decision, 5), result,
                raw_sample[2] / self.in_kb]
            
    def fit(self):
            training_data = np.asarray(
                self.training_samples,
                dtype=np.float64
            )

            memory_rate_index = self.training_feature_names.index(
                "memory_rate"
            )

            memory_rates = training_data[:, memory_rate_index]
            positive_rates = memory_rates[memory_rates > 0]

            if len(positive_rates) > 0:
                self.memory_growth_threshold = np.percentile(
                    positive_rates,
                    99
                )
            else:
                self.memory_growth_threshold = 0

            # The logged model rate now has the same meaning in every phase.
            for row in self.predict_outputs:
                if row[1] in ("WARMING_UP", "LEARNING", "TRAINING"):
                    raw_rate = row[8] * self.in_kb
                    model_rate = (
                        0 if raw_rate < self.memory_growth_threshold else raw_rate
                    )
                    row[4] = round(model_rate / self.in_kb, 3)

            processed_training_data = np.asarray(
                [
                    self.preprocess_features(sample)
                    for sample in self.training_samples
                ],
                dtype=np.float64
            )

            self.model.fit(processed_training_data)

            training_decisions = self.model.decision_function(
                processed_training_data
            )

            self.evaluator.fit_baseline(
                processed_training_data,
                training_decisions,
                self.training_feature_names,
            )

            self.resource_guard.fit(processed_training_data,self.training_feature_names)
            print("Fit complete")


    def predict(self, sample):
        processed_sample = self.preprocess_features(sample)
        model_input = [processed_sample]

        result = self.model.predict(model_input)[0]
        decision = self.model.decision_function(model_input)[0]
        score = self.model.score_samples(model_input)[0]

        return result, decision, score, processed_sample
    
    def extract_features(self, sample: dict):
        CPU = float(sample["cpu_usage"].strip("%"))
        Mem = parse_data_size(sample["mem_usage"].split("/")[0].strip())
        network_rx = parse_data_size(sample["network_rx"])
        network_tx = parse_data_size(sample["network_tx"])
        pid_count = int(sample["PID_count"])
        receive_rate = network_rx
        transmit_rate = network_tx
        memory_rate = 0
        pid_rate = 0
        if self.previous_raw_sample:
            receive_rate -= self.previous_raw_sample["network_rx"]
            transmit_rate -= self.previous_raw_sample["network_tx"]
            memory_rate += max(Mem - self.previous_raw_sample["Memory"],0)
            pid_rate += max((pid_count - self.previous_raw_sample["pid_count"]), 0)
        return {
            "CPU": CPU,
            "Memory": Mem,
            "memory_rate": memory_rate,
            "network_rx": network_rx,
            "network_tx": network_tx,
            "receive_rate": receive_rate,
            "transmit_rate": transmit_rate,
            "pid_count": pid_count,
            "pid_rate": pid_rate,
        }
    def preprocess_features(self, features):
        processed = list(features)

        memory_rate_index = self.training_feature_names.index("memory_rate")

        if processed[memory_rate_index] < self.memory_growth_threshold:
            processed[memory_rate_index] = 0

        return processed
