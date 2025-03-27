# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from pathlib import PurePosixPath
from typing import List

from graphrag.callbacks.file_workflow_callbacks import FileWorkflowCallbacks
from graphrag.callbacks.workflow_callbacks import WorkflowCallbacks
from graphrag.callbacks.workflow_callbacks_manager import WorkflowCallbacksManager

from graphrag_app.logger.application_insights_workflow_callbacks import (
    ApplicationInsightsWorkflowCallbacks,
)
from graphrag_app.logger.blob_workflow_callbacks import BlobWorkflowCallbacks
from graphrag_app.logger.console_workflow_callbacks import ConsoleWorkflowCallbacks
from graphrag_app.logger.typing import Logger
from graphrag_app.utils.azure_clients import AzureClientManager


def load_pipeline_logger(
    logging_dir: str = "",
    index_name: str = "",
    num_workflow_steps: int = 0,
) -> WorkflowCallbacks:
    """Create and load a list of loggers.

    This function creates loggers for two different scenarios. Loggers can be instantiated as generic loggers or associated with a specified indexing job.
    1. When an indexing job is running, custom index-specific loggers are created to log the job activity
    2. When the fastapi app is running, generic loggers are used to log the app's activities.
    """
    loggers: List[Logger] = []
    for logger_type in ["BLOB", "CONSOLE", "APP_INSIGHTS"]:
        loggers.append(Logger[logger_type])

    azure_client_manager = AzureClientManager()
    callback_manager = WorkflowCallbacksManager()
    for logger in loggers:
        match logger:
            case Logger.BLOB:
                # create a dedicated container for logs
                log_blob_name = "logs"
                if logging_dir:
                    log_blob_name = os.path.join(logging_dir, log_blob_name)
                # ensure the root directory exists; if not, create it
                blob_service_client = azure_client_manager.get_blob_service_client()
                container_root = PurePosixPath(log_blob_name).parts[0]
                if not blob_service_client.get_container_client(
                    container_root
                ).exists():
                    blob_service_client.create_container(container_root)
                callback_manager.register(
                    BlobWorkflowCallbacks(
                        blob_service_client=blob_service_client,
                        container_name=log_blob_name,
                        index_name=index_name,
                        num_workflow_steps=num_workflow_steps,
                    )
                )
            case Logger.FILE:
                callback_manager.register(FileWorkflowCallbacks(dir=logging_dir))
            case Logger.APP_INSIGHTS:
                if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
                    callback_manager.register(
                        ApplicationInsightsWorkflowCallbacks(
                            index_name=index_name,
                            num_workflow_steps=num_workflow_steps,
                        )
                    )
            case Logger.CONSOLE:
                callback_manager.register(
                    ConsoleWorkflowCallbacks(
                        index_name=index_name, num_workflow_steps=num_workflow_steps
                    )
                )
            case _:
                print(f"WARNING: unknown logger type: {logger}. Skipping.")
    return callback_manager
