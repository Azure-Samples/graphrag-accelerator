# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from unittest.mock import patch

import pytest

from graphrag_app.logger.blob_workflow_callbacks import BlobWorkflowCallbacks


@pytest.fixture
def mock_blob_service_client():
    with patch(
        "graphrag_app.logger.blob_workflow_callbacks.BlobServiceClient"
    ) as mock_blob_service_client:
        yield mock_blob_service_client


@pytest.fixture
def workflow_callbacks(mock_blob_service_client):
    with patch(
        "graphrag_app.logger.blob_workflow_callbacks.BlobWorkflowCallbacks.__init__",
        return_value=None,
    ):
        instance = BlobWorkflowCallbacks()
        instance._blob_service_client = mock_blob_service_client
        instance._index_name = "mock_index_name"
        instance._container_name = "logs"
        instance._blob_name = "logs/logs.txt"
        instance._num_workflow_steps = 4
        instance._processed_workflow_steps = []
        instance._workflow_name = ""
        yield instance


def test_on_workflow_start(workflow_callbacks):
    workflow_callbacks.workflow_start("test_workflow", object())
    # check if blob workflow callbacks _write_log() method was called
    assert workflow_callbacks._blob_service_client.get_blob_client().append_block.called


def test_on_workflow_end(workflow_callbacks):
    workflow_callbacks.workflow_end("test_workflow", object())
    assert workflow_callbacks._blob_service_client.get_blob_client().append_block.called


def test_on_error(workflow_callbacks):
    workflow_callbacks.error("test_error", Exception("test_exception"))
    assert workflow_callbacks._blob_service_client.get_blob_client().append_block.called
