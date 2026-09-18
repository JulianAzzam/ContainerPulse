

from enum import Enum


class WorkloadStatus(Enum):
    LEARNING = 1
    TRAINING = 2
    READY = 3
