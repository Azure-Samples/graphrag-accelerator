# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from pathlib import Path
from typing import List

from graphrag.callbacks.file_workflow_callbacks import FileWorkflowCallbacks
from graphrag.callbacks.workflow_callbacks import WorkflowCallbacks
from graphrag.callbacks.workflow_callbacks_manager import WorkflowCallbacksManager

from src.api.azure_clients import AzureClientManager
from src.logger.application_insights_workflow_callbacks import (
    ApplicationInsightsWorkflowCallbacks,
)
from src.logger.blob_workflow_callbacks import BlobWorkflowCallbacks
from src.logger.console_workflow_callbacks import ConsoleWorkflowCallbacks
from src.logger.typing import Logger


def load_pipeline_logger(
    logging_dir: str | None,
    index_name: str = "",
    num_workflow_steps: int = 0,
    loggers: List[Logger] = [],
) -> WorkflowCallbacks:
    """Create and load a list of loggers.

    Loggers may be configured as generic loggers or associated with a specified indexing job.
    """
    # always register the console logger as a fallback option
    if Logger.CONSOLE not in loggers:
        loggers.append(Logger.CONSOLE)

    azure_client_manager = AzureClientManager()
    callback_manager = WorkflowCallbacksManager()
    for logger in loggers:
        match logger:
            case Logger.BLOB:
                # create a dedicated container for logs
                container_name = "logs"
                if logging_dir is not None:
                    container_name = os.path.join(logging_dir, container_name)
                # ensure the root directory exists; if not, create it
                blob_service_client = azure_client_manager.get_blob_service_client()
                container_root = Path(container_name).parts[0]
                if not blob_service_client.get_container_client(
                    container_root
                ).exists():
                    blob_service_client.create_container(container_root)
                callback_manager.register(
                    BlobWorkflowCallbacks(
                        blob_service_client=blob_service_client,
                        container_name=container_name,
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
                            connection_string=os.environ[
                                "APPLICATIONINSIGHTS_CONNECTION_STRING"
                            ],
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
