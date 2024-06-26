# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from enum import Enum


class PipelineJobState(Enum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    FAILED = "failed"
    COMPLETE = "complete"
