# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from datetime import datetime
from typing import (
    Any,
)

from azure.storage.blob import BlobServiceClient
from devtools import pformat
from graphrag.callbacks.noop_workflow_callbacks import NoopWorkflowCallbacks


class BlobWorkflowCallbacks(NoopWorkflowCallbacks):
    """A reporter that writes to a blob storage."""

    _blob_service_client: BlobServiceClient
    _container_name: str
    _index_name: str
    _num_workflow_steps: int
    _processed_workflow_steps: list[str] = []
    _max_block_count: int = 25000  # 25k blocks per blob
    _num_blocks = 0
    _blob_name: str

    def __init__(
        self,
        blob_service_client: BlobServiceClient,
        container_name: str,
        blob_name: str = "",
        index_name: str = "",
        num_workflow_steps: int = 0,
    ):
        """Create a new instance of the BlobWorkflowCallbacks class.

        Args:
            storage_account_blob_url (str): The URL to the storage account.
            container_name (str): The name of the container.
            blob_name (str, optional): The name of the blob. Defaults to "".
            index_name (str, optional): The name of the index. Defaults to "".
            num_workflow_steps (int): A list of workflow names ordered by their execution. Defaults to [].
        """
        self._blob_service_client = blob_service_client
        self._blob_name = (
            f"{datetime.now().strftime('%Y-%m-%d-%H:%M:%S:%f')}.logs.txt"
            if not blob_name
            else blob_name
        )
        self._container_name = container_name
        self._index_name = index_name
        self._num_workflow_steps = num_workflow_steps
        self._processed_workflow_steps = []  # maintain a running list of workflow steps that get processed
        self._blob_client = self._blob_service_client.get_blob_client(
            self._container_name, self._blob_name
        )
        if not self._blob_client.exists():
            self._blob_client.create_append_blob()
        self._num_blocks = 0  # refresh block counter

    def _write_log(self, log: dict[str, Any]):
        """Write a log message to blob storage."""
        # create a new file when block count is close to 25k
        if self._num_blocks >= self._max_block_count:
            self.__init__(
                blob_service_client=self._blob_service_client,
                container_name=self._container_name,
            )
        blob_client = self._blob_service_client.get_blob_client(
            self._container_name, self._blob_name
        )
        blob_client.append_block(pformat(log, indent=2) + "\n")
        self._num_blocks += 1

    def workflow_start(self, name: str, instance: object) -> None:
        """Execute this callback when a workflow starts."""
        self._workflow_name = name
        self._processed_workflow_steps.append(name)
        message = f"Index: {self._index_name} -- " if self._index_name else ""
        workflow_progress = (
            f" ({len(self._processed_workflow_steps)}/{self._num_workflow_steps})"
            if self._num_workflow_steps
            else ""
        )  # will take the form "(1/4)"
        message += f"Workflow{workflow_progress}: {name} started."
        details = {
            "workflow_name": name,
            # "workflow_instance": str(instance),
        }
        if self._index_name:
            details["index_name"] = self._index_name
        self._write_log({
            "type": "on_workflow_start",
            "data": message,
            "details": details,
        })

    def workflow_end(self, name: str, instance: object) -> None:
        """Execute this callback when a workflow ends."""
        message = f"Index: {self._index_name} -- " if self._index_name else ""
        workflow_progress = (
            f" ({len(self._processed_workflow_steps)}/{self._num_workflow_steps})"
            if self._num_workflow_steps
            else ""
        )  # will take the form "(1/4)"
        message += f"Workflow{workflow_progress}: {name} complete."
        details = {
            "workflow_name": name,
            # "workflow_instance": str(instance),
        }
        if self._index_name:
            details["index_name"] = self._index_name
        self._write_log({
            "type": "on_workflow_end",
            "data": message,
            "details": details,
        })

    def error(
        self,
        message: str,
        cause: BaseException | None = None,
        stack: str | None = None,
        details: dict | None = None,
    ):
        """Report an error."""
        self._write_log({
            "type": "error",
            "data": message,
            "cause": str(cause),
            "stack": stack,
            "details": details,
        })

    def warning(self, message: str, details: dict | None = None):
        """Report a warning."""
        self._write_log({"type": "warning", "data": message, "details": details})

    def log(self, message: str, details: dict | None = None):
        """Report a generic log message."""
        self._write_log({"type": "log", "data": message, "details": details})
