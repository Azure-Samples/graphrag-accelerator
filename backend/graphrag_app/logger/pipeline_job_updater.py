# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from graphrag.callbacks.noop_workflow_callbacks import NoopWorkflowCallbacks

from graphrag_app.typing.pipeline import PipelineJobState
from graphrag_app.utils.pipeline import PipelineJob


class PipelineJobUpdater(NoopWorkflowCallbacks):
    """A callback that records pipeline updates."""

    def __init__(self, pipeline_job: PipelineJob):
        """
        This class defines a set of callback methods that can be used to log the progress of a pipeline job.
        It inherits from the NoopWorkflowCallbacks class, which provides default implementations for all the callback methods.

        Attributes:
            pipeline_job (PipelineJob): The pipeline object associated with the job.

        """
        self._pipeline_job = pipeline_job

    def workflow_start(self, name: str, instance: object) -> None:
        """Execute this callback when a workflow starts."""
        self._pipeline_job.status = PipelineJobState.RUNNING
        self._pipeline_job.progress = f"Workflow {name} started."

    def workflow_end(self, name: str, instance: object) -> None:
        """Execute this callback when a workflow ends."""
        self._pipeline_job.completed_workflows.append(name)
        self._pipeline_job.update_db()
        self._pipeline_job.progress = f"Workflow {name} complete."
        self._pipeline_job.percent_complete = (
            self._pipeline_job.calculate_percent_complete()
        )
