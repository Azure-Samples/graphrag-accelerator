# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from datashaper.workflow.workflow_callbacks import NoopWorkflowCallbacks

from src.models import PipelineJob
from src.typing import PipelineJobState


class PipelineJobWorkflowCallbacks(NoopWorkflowCallbacks):
    """A reporter that writes to a stream (sys.stdout)."""

    def __init__(self, pipeline_job: "PipelineJob"):
        """
        This class defines a set of callback methods that can be used to report the progress and status of a workflow job.
        It inherits from the NoopWorkflowCallbacks class, which provides default implementations for all the callback methods.

        Attributes:
            pipeline_job (PipelineJob): The pipeline object associated with the job.

        """
        self._pipeline_job = pipeline_job

    def on_workflow_start(self, name: str, instance: object) -> None:
        """Execute this callback when a workflow starts."""
        # if we are not already running, set the status to running
        if self._pipeline_job.status != PipelineJobState.RUNNING:
            self._pipeline_job.status = PipelineJobState.RUNNING
        self._pipeline_job.progress = f"Workflow '{name}' started."

    def on_workflow_end(self, name: str, instance: object) -> None:
        """Execute this callback when a workflow ends."""
        self._pipeline_job.completed_workflows.append(name)
        self._pipeline_job.update_db()
        self._pipeline_job.progress = f"Workflow '{name}' complete."
        self._pipeline_job.percent_complete = (
            self._pipeline_job.calculate_percent_complete()
        )
