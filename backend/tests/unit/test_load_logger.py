from unittest.mock import patch

import pytest

from graphrag_app.logger.load_logger import load_pipeline_logger


@pytest.fixture
def mock_app_insights_workflow_callbacks():
    with patch(
        "graphrag_app.logger.application_insights_workflow_callbacks.ApplicationInsightsWorkflowCallbacks"
    ) as mock_app_insights_workflow_callbacks:
        yield mock_app_insights_workflow_callbacks


@pytest.fixture
def mock_file_workflow_callbacks():
    with patch(
        "graphrag.index.reporting.file_workflow_callbacks.FileWorkflowCallbacks"
    ) as mock_file_workflow_callbacks:
        yield mock_file_workflow_callbacks


@pytest.fixture
def mock_blob_workflow_callbacks():
    with patch(
        "graphrag_app.logger.blob_workflow_callbacks.BlobWorkflowCallbacks"
    ) as mock_blob_workflow_callbacks:
        yield mock_blob_workflow_callbacks


@pytest.fixture
def mock_console_workflow_callbacks():
    with patch(
        "graphrag_app.logger.console_workflow_callbacks.ConsoleWorkflowCallbacks"
    ) as mock_console_workflow_callbacks:
        yield mock_console_workflow_callbacks


@pytest.mark.skip(reason="This test is currently not complete")
def test_load_pipeline_logger_with_console(
    mock_app_insights_workflow_callbacks,
    mock_blob_workflow_callbacks,
    mock_console_workflow_callbacks,
    mock_file_workflow_callbacks,
):
    """Test load_pipeline_logger."""
    loggers = load_pipeline_logger(
        logging_dir="logs",
        loggers=["app_insights", "blob", "console", "file"],
        index_name="test-index",
        num_workflow_steps=4,
    )
    assert len(loggers._callbacks) == 4
