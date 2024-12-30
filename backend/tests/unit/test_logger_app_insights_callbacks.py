# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
from unittest.mock import MagicMock, patch

import pytest

from src.logger.application_insights_workflow_callbacks import (
    ApplicationInsightsWorkflowCallbacks,
)


@pytest.fixture
def mock_logger():
    with patch(
        "src.logger.application_insights_workflow_callbacks.logging.getLogger"
    ) as mock_get_logger:
        mock_logger_instance = MagicMock(spec=logging.Logger)
        mock_get_logger.return_value = mock_logger_instance
        yield mock_logger_instance


@pytest.fixture
def workflow_callbacks(mock_logger):
    with patch(
        "src.logger.application_insights_workflow_callbacks.ApplicationInsightsWorkflowCallbacks.__init__",
        return_value=None,
    ):
        instance = ApplicationInsightsWorkflowCallbacks()
        instance._connection_string = "mock_connection_string"
        instance._index_name = "mock_index_name"
        instance._num_workflow_steps = 4
        instance._logger = mock_logger
        instance._processed_workflow_steps = []
        instance._properties = {}
        yield instance


def test_on_workflow_start(workflow_callbacks, mock_logger):
    workflow_callbacks.on_workflow_start("test_workflow", object())
    assert mock_logger.info.called


def test_on_workflow_end(workflow_callbacks, mock_logger):
    workflow_callbacks.on_workflow_end("test_workflow", object())
    assert mock_logger.info.called


def test_on_log(workflow_callbacks, mock_logger):
    workflow_callbacks.on_log("test_log_message")
    assert mock_logger.info.called


def test_on_warning(workflow_callbacks, mock_logger):
    workflow_callbacks.on_warning("test_warning")
    assert mock_logger.warning.called


def test_on_error(workflow_callbacks, mock_logger):
    workflow_callbacks.on_error("test_error", Exception("test_exception"))
    assert mock_logger.error.called
