# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json

# from dataclasses import asdict
from datetime import datetime
from typing import (
    Any,
    Optional,
)

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from datashaper import NoopWorkflowCallbacks


class BlobWorkflowCallbacks(NoopWorkflowCallbacks):
    """A reporter that writes to a blob storage."""

    _blob_service_client: BlobServiceClient
    _container_name: str
    _max_block_count: int = 25000  # 25k blocks per blob

    def __init__(
        self, storage_account_blob_url: str, container_name: str, blob_name: str = ""
    ):  # type: ignore
        """Create a new instance of the BlobStorageReporter class."""
        self._storage_account_blob_url = storage_account_blob_url
        credential = DefaultAzureCredential()
        self._blob_service_client = BlobServiceClient(
            storage_account_blob_url, credential=credential
        )

        if blob_name == "":
            blob_name = (
                f"report/{datetime.now().strftime('%Y-%m-%d-%H:%M:%S:%f')}.logs.json"
            )

        self._blob_name = blob_name
        self._container_name = container_name
        self._blob_client = self._blob_service_client.get_blob_client(
            self._container_name, self._blob_name
        )
        if not self._blob_client.exists():
            self._blob_client.create_append_blob()

        self._num_blocks = 0  # refresh block counter

    def _write_log(self, log: dict[str, Any]):
        # create a new file when block count hits close 25k
        if (
            self._num_blocks >= self._max_block_count
        ):  # Check if block count exceeds 25k
            self.__init__(self._storage_account_blob_url, self._container_name)

        blob_client = self._blob_service_client.get_blob_client(
            self._container_name, self._blob_name
        )
        blob_client.append_block(json.dumps(log) + "\n")

        # update the blob's block count
        self._num_blocks += 1

    def on_error(
        self,
        message: str,
        cause: BaseException | None = None,
        stack: str | None = None,
        details: dict | None = None,
    ):
        """Report an error."""
        self._write_log(
            {
                "type": "error",
                "data": message,
                "cause": str(cause),
                "stack": stack,
                "details": details,
            }
        )

    def on_workflow_start(self, name: str, instance: object) -> None:
        """Execute this callback when a workflow starts."""
        self._workflow_name = name

        message = f"Workflow {name} started."
        details = {
            "workflow_name": name,
            "workflow_instance": str(instance),
        }
        self._write_log(
            {"type": "on_workflow_start", "data": message, "details": details}
        )

    def on_workflow_end(self, name: str, instance: object) -> None:
        """Execute this callback when a workflow ends."""
        message = f"Workflow {name} completed."
        details = {
            "workflow_name": name,
            "workflow_instance": str(instance),
        }
        self._write_log(
            {"type": "on_workflow_end", "data": message, "details": details}
        )

    def on_warning(self, message: str, details: dict | None = None):
        """Report a warning."""
        self._write_log({"type": "warning", "data": message, "details": details})

    def on_log(self, message: str, details: dict | None = None):
        """Report a generic log message."""
        self._write_log({"type": "log", "data": message, "details": details})

    def on_measure(
        self, name: str, value: float, details: Optional[dict] = None
    ) -> None:
        """A call back handler for when a measurement occurs."""
        pass
