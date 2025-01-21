# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
from typing import (
    Any,
    Dict,
    Optional,
)

from azure.identity import DefaultAzureCredential
from azure.monitor.opentelemetry import configure_azure_monitor
from graphrag.callbacks.noop_workflow_callbacks import NoopWorkflowCallbacks


class ApplicationInsightsWorkflowCallbacks(NoopWorkflowCallbacks):
    """A logger that writes to an AppInsights Workspace."""

    _logger: logging.Logger
    _logger_name: str
    _logger_level: int
    _properties: Dict[str, Any]
    _workflow_name: str
    _index_name: str
    _num_workflow_steps: int
    _processed_workflow_steps: list[str] = []

    def __init__(
        self,
        logger_name: str = "graphrag-accelerator",
        index_name: str = "",
        num_workflow_steps: int = 0,
        properties: Dict[str, Any] = {},
    ):
        """
        Initialize the AppInsightsReporter.

        Args:
            logger_name (str | None, optional): The name of the logger. Defaults to None.
            index_name (str, optional): The name of an index. Defaults to "".
            num_workflow_steps (int): A list of workflow names ordered by their execution. Defaults to [].
            properties (Dict[str, Any], optional): Additional properties to be included in the log. Defaults to {}.
        """
        self._logger: logging.Logger
        self._logger_name = logger_name
        self._index_name = index_name
        self._num_workflow_steps = num_workflow_steps
        self._properties = properties
        self._workflow_name = "N/A"
        self._processed_workflow_steps = []  # if logger is used in a pipeline job, maintain a running list of workflows that are processed
        # initialize a new logger with an AppInsights handler
        self.__init_logger()

    def __init_logger(self, max_logger_init_retries: int = 10):
        # Configure OpenTelemetry to use Azure Monitor with the
        # APPLICATIONINSIGHTS_CONNECTION_STRING environment variable
        configure_azure_monitor(
            logger_name=self._logger_name,
            disable_offline_storage=True,
            enable_live_metrics=True,
            credential=DefaultAzureCredential(),
        )
        self._logger = logging.getLogger(self._logger_name)

    def _format_details(self, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Format the details dictionary to comply with the Application Insights structured
        logging Property column standard.

        Args:
            details (Dict[str, Any] | None): Optional dictionary containing additional details to log.

        Returns:
            Dict[str, Any]: The formatted details dictionary with custom dimensions.
        """
        if not isinstance(details, dict) or (details is None):
            return {}
        return {"custom_dimensions": {**self._properties, **unwrap_dict(details)}}

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
        self._logger.info(
            message, stack_info=False, extra=self._format_details(details=details)
        )

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
        self._logger.info(
            message, stack_info=False, extra=self._format_details(details=details)
        )

    def error(
        self,
        message: str,
        cause: Optional[BaseException] = None,
        stack: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """A call back handler for when an error occurs."""
        details = {} if details is None else details
        details = {"cause": str(cause), "stack": stack, **details}
        self._logger.error(
            message,
            exc_info=True,
            stack_info=False,
            extra=self._format_details(details=details),
        )

    def warning(self, message: str, details: Optional[dict] = None) -> None:
        """A call back handler for when a warning occurs."""
        self._logger.warning(
            message, stack_info=False, extra=self._format_details(details=details)
        )

    def log(self, message: str, details: Optional[dict] = None) -> None:
        """A call back handler for when a log message occurs."""
        self._logger.info(
            message, stack_info=False, extra=self._format_details(details=details)
        )


def unwrap_dict(input_dict, parent_key="", sep="_"):
    """
    Recursively unwraps a nested dictionary by flattening it into a single-level dictionary.

    Args:
        input_dict (dict): The input dictionary to be unwrapped.
        parent_key (str, optional): The parent key to be prepended to the keys of the unwrapped dictionary. Defaults to ''.
        sep (str, optional): The separator to be used between the parent key and the child key. Defaults to '_'.

    Returns:
        dict: The unwrapped dictionary.
    """
    items = []
    for k, v in input_dict.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(unwrap_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)
