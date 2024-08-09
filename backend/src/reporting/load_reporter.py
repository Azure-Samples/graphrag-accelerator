# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from datetime import datetime
from pathlib import Path
from typing import List

from datashaper import WorkflowCallbacks, WorkflowCallbacksManager
from graphrag.index.reporting import FileWorkflowCallbacks

from src.api.azure_clients import BlobServiceClientSingleton
from src.reporting.application_insights_workflow_callbacks import (
    ApplicationInsightsWorkflowCallbacks,
)
from src.reporting.blob_workflow_callbacks import BlobWorkflowCallbacks
from src.reporting.console_workflow_callbacks import ConsoleWorkflowCallbacks
from src.reporting.typing import Reporters


# def load_pipeline_reporter_from_list(
def load_pipeline_reporter(
    reporting_dir: str | None,
    reporters: List[Reporters] | None = [],
    index_name: str = "",
    num_workflow_steps: int = 0,
) -> WorkflowCallbacks:
    """Create a callback manager and register a list of reporters.
    Reporters may be configured as generic loggers or associated with a specified indexing job.
    """
    callback_manager = WorkflowCallbacksManager()
    for reporter in reporters:
        match reporter:
            case Reporters.BLOB:
                # create a dedicated container for logs
                container_name = "logs"
                if reporting_dir is not None:
                    container_name = os.path.join(reporting_dir, container_name)
                # ensure the root directory exists; if not, create it
                blob_service_client = BlobServiceClientSingleton.get_instance()
                container_root = Path(container_name).parts[0]
                if not blob_service_client.get_container_client(
                    container_root
                ).exists():
                    blob_service_client.create_container(container_root)
                # register the blob reporter
                callback_manager.register(
                    BlobWorkflowCallbacks(
                        storage_account_blob_url=os.environ["STORAGE_ACCOUNT_BLOB_URL"],
                        container_name=container_name,
                        blob_name=f"{datetime.now().strftime('%Y-%m-%d-%H:%M:%S:%f')}.logs.txt",
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
                pass
            case _:
                print(f"WARNING: unknown reporter type: {reporter}. Skipping.")
    # always register the console reporter as a fallback
    callback_manager.register(
        ConsoleWorkflowCallbacks(
            index_name=index_name, num_workflow_steps=num_workflow_steps
        )
    )
    return callback_manager
