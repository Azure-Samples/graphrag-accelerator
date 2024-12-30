# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from pathlib import Path
from typing import List

from datashaper import WorkflowCallbacks, WorkflowCallbacksManager
from graphrag.index.reporting import FileWorkflowCallbacks

from src.api.azure_clients import AzureClientManager
from src.logger.application_insights_workflow_callbacks import (
    ApplicationInsightsWorkflowCallbacks,
)
from src.logger.blob_workflow_callbacks import BlobWorkflowCallbacks
from src.logger.console_workflow_callbacks import ConsoleWorkflowCallbacks
from src.logger.typing import Reporters


def load_pipeline_logger(
    reporting_dir: str | None,
    reporters: List[Reporters] | None = [],
    index_name: str = "",
    num_workflow_steps: int = 0,
) -> WorkflowCallbacks:
    """Create a callback manager and register a list of loggers.

    Loggers may be configured as generic loggers or associated with a specified indexing job.
    """
    # always register the console logger if no loggers are specified
    if Reporters.CONSOLE not in reporters:
        reporters.append(Reporters.CONSOLE)

    azure_client_manager = AzureClientManager()
    callback_manager = WorkflowCallbacksManager()
    for reporter in reporters:
        match reporter:
            case Reporters.BLOB:
                # create a dedicated container for logs
                container_name = "logs"
                if reporting_dir is not None:
                    container_name = os.path.join(reporting_dir, container_name)
                # ensure the root directory exists; if not, create it
                blob_service_client = azure_client_manager.get_blob_service_client()
                container_root = Path(container_name).parts[0]
                if not blob_service_client.get_container_client(
                    container_root
                ).exists():
                    blob_service_client.create_container(container_root)
                # register the blob reporter
                callback_manager.register(
                    BlobWorkflowCallbacks(
                        blob_service_client=blob_service_client,
                        container_name=container_name,
                        index_name=index_name,
                        num_workflow_steps=num_workflow_steps,
                    )
                )
            case Reporters.FILE:
                callback_manager.register(FileWorkflowCallbacks(dir=reporting_dir))
            case Reporters.APP_INSIGHTS:
                if os.getenv("APP_INSIGHTS_CONNECTION_STRING"):
                    callback_manager.register(
                        ApplicationInsightsWorkflowCallbacks(
                            connection_string=os.environ[
                                "APP_INSIGHTS_CONNECTION_STRING"
                            ],
                            index_name=index_name,
                            num_workflow_steps=num_workflow_steps,
                        )
                    )
            case Reporters.CONSOLE:
                callback_manager.register(
                    ConsoleWorkflowCallbacks(
                        index_name=index_name, num_workflow_steps=num_workflow_steps
                    )
                )
            case _:
                print(f"WARNING: unknown reporter type: {reporter}. Skipping.")
    return callback_manager
