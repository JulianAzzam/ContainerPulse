import time
import logging
import numpy as np
from sklearn.ensemble import IsolationForest
from .helper_funcs import parse_data_size
from ..events.anomaly_evaluator import AnomalyEvaluator
from ..events.resource_guard import ResourceGuard
from ..workload.workload_status import WorkloadStatus

logger = logging.getLogger(__name__)
class WorkloadState:
    
    WARMING_UP = getattr(WorkloadStatus, "WARMING_UP", "WARMING_UP")
    WARM_UP_SECONDS = 120
    row_data_keys = ("Memory", "network_rx", "network_tx", "pid_count",)
    training_feature_names = (
        "CPU",
        "Memory",
        "memory_rate",
    )
    def __init__(self, workload_id, warm_up_seconds=WARM_UP_SECONDS):
        self.model = IsolationForest(
            max_samples=0.9, contamination=0.05, random_state=42
        )
        self.workload_id = workload_id
        logger.info("Created collector for: %s", self.workload_id)
        self.training_samples = []
        if warm_up_seconds < 0:
            raise ValueError("warm_up_seconds must be non-negative")
        self.warm_up_seconds = warm_up_seconds
        self.status = self.WARMING_UP if warm_up_seconds else WorkloadStatus.LEARNING
        self.waiting_queue = []
        self.last_signature = None
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
            if time.monotonic() - self.warmup_started_at >= self.warm_up_seconds:
                self.status = WorkloadStatus.LEARNING
                logger.info(
                    "Warm-up complete for workload %s; learning started",
                    self.workload_id,
                )
        elif self.status == WorkloadStatus.LEARNING:
            self.training_samples.append(training_sample)
            if len(self.training_samples) == 300:
                self.status = WorkloadStatus.TRAINING
                logger.info(
                    "Training model for workload %s",
                    self.workload_id,
                )
                self.fit()
                self.status = WorkloadStatus.READY
                logger.info(
                    "Model ready for workload %s",
                    self.workload_id,
                )
        elif self.status == WorkloadStatus.TRAINING:
            self.waiting_queue.append(
                (sample["timestamp"], training_sample)
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
                resource_event = self.resource_guard.evaluate(processed_sample, self.training_feature_names)
                self.evaluator.evaluate_resource_event(
                    resource_event,
                    timestamp,
                )

            result, decision, score, processed_sample = self.predict(
                training_sample
            )

            self.evaluator.evaluate(
                [sample["timestamp"], *processed_sample],
                decision
            )
            resource_event = self.resource_guard.evaluate(processed_sample, self.training_feature_names)
            self.evaluator.evaluate_resource_event( resource_event, sample["timestamp"],)
            
    def fit(self):
        """
        Learn preprocessing thresholds, fit the Isolation Forest,
        and initialize the anomaly evaluator and resource guard baselines.
        """
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
        """
        Apply the same feature preprocessing used during both training
        and inference.

        Small positive memory-growth values below the learned threshold
        are treated as noise and set to zero.
        """
        processed = list(features)

        memory_rate_index = self.training_feature_names.index("memory_rate")

        if processed[memory_rate_index] < self.memory_growth_threshold:
            processed[memory_rate_index] = 0

        return processed

