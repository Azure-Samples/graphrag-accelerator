# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from enum import Enum


class PipelineJobState(str, Enum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    FAILED = "failed"
    COMPLETE = "complete"

    def __repr__(self):
        """Get a string representation."""
        return f'"{self.value}"'
