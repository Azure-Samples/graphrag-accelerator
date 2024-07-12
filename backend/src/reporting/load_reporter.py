# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, cast

from datashaper import WorkflowCallbacks, WorkflowCallbacksManager
from graphrag.index.config import (
    PipelineBlobReportingConfig,
    PipelineConsoleReportingConfig,
    PipelineFileReportingConfig,
    PipelineReportingConfig,
)
from graphrag.index.reporting import FileWorkflowCallbacks

from src.api.azure_clients import BlobServiceClientSingleton
from src.reporting.application_insights_workflow_callbacks import (
    ApplicationInsightsWorkflowCallbacks,
)
from src.reporting.blob_workflow_callbacks import BlobWorkflowCallbacks
from src.reporting.console_workflow_callbacks import ConsoleWorkflowCallbacks
from src.reporting.typing import (
    PipelineAppInsightsReportingConfig,
    Reporters,
)


def load_pipeline_reporter_from_config(
    root_dir: str | None, config: PipelineReportingConfig | None
) -> WorkflowCallbacks:
    """Create a reporter for the given pipeline config."""
    reporting_config = config or PipelineConsoleReportingConfig(type="console")
    match reporting_config.type.lower():
        case Reporters.BLOB.name:
            reporting_config = cast(PipelineBlobReportingConfig, reporting_config)
            return BlobWorkflowCallbacks(
                storage_account_blob_url=reporting_config.storage_account_blob_url,
                container_name=reporting_config.container_name,
            )
        case Reporters.FILE.name:
            reporting_config = cast(PipelineFileReportingConfig, reporting_config)
            reporting_dir = os.path.join(root_dir or "", reporting_config.base_dir)
            return FileWorkflowCallbacks(reporting_dir)
        case Reporters.APP_INSIGHTS.name:
            reporting_config = cast(
                PipelineAppInsightsReportingConfig, reporting_config
            )
            return ApplicationInsightsWorkflowCallbacks(
                connection_string=reporting_config.connection_string,
                logger_name=reporting_config.logger_name,
                logger_level=reporting_config.logger_level,
            )
        case Reporters.CONSOLE.name:
            return ConsoleWorkflowCallbacks()
        case _:
            raise ValueError(f"Unknown reporting type: {reporting_config.type}")


def load_pipeline_reporter_from_list(
    reporting_dir: str | None,
    reporters: List[Reporters] | None = [],
    index_name: str = "",
) -> WorkflowCallbacks:
    """Creates a reporter for the given a list of reporting enum."""
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
                        )
                    )
            case _:
                print(f"WARNING: unknown reporter type: {reporter}. Skipping.")
    # always register the console reporter as a fallback
    callback_manager.register(ConsoleWorkflowCallbacks(index_name=index_name))
    return callback_manager


def load_pipeline_reporter(
    index_name: str = "",
    from_config=False,
    config: PipelineReportingConfig | None = None,
    **kwargs: Dict[str, Any],
) -> WorkflowCallbacks:
    if from_config:
        return load_pipeline_reporter_from_config(config)
    return load_pipeline_reporter_from_list(index_name=index_name, **kwargs)
